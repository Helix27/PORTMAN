from database import get_db, get_cursor

def _clean_empty(data):
    """Convert empty strings to None so timestamp/date columns get NULL."""
    for k in data:
        if data[k] == '':
            data[k] = None
    return data

def get_next_doc_num():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("SELECT MAX(CAST(SUBSTR(doc_num, 5) AS INTEGER)) FROM ldud_header WHERE doc_num LIKE 'LDUD%%'")
    result = cur.fetchone()['max']
    conn.close()
    next_num = (result or 0) + 1
    return f"LDUD{next_num}"

def _build_vcn_list(rows):
    result = []
    for r in rows:
        doc_date = r.get('doc_date') or ''
        op_type = r.get('operation_type') or ''
        display = f"{r['vcn_doc_num']} / {r['vessel_name']}"
        if doc_date:
            display += f" / {doc_date}"
        if op_type:
            display += f" / {op_type}"
        result.append({
            'value': display,
            'vcn_id': r['id'],
            'vcn_doc_num': r['vcn_doc_num'],
            'vessel_name': r['vessel_name'],
            'anchored_datetime': r.get('anchorage_arrival'),
            'doc_date': doc_date,
            'operation_type': op_type
        })
    return result

def get_vcn_list():
    """Get all approved VCN entries with doc date and operation type for dropdown"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT h.id, h.vcn_doc_num, h.vessel_name, h.doc_date, h.operation_type, a.anchorage_arrival
        FROM vcn_header h
        LEFT JOIN vcn_anchorage a ON a.vcn_id = h.id
        WHERE h.doc_status = 'Approved'
        ORDER BY h.vcn_doc_num DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return _build_vcn_list(rows)

def get_data(page=1, size=20, filters=None):
    conn = get_db()
    cur = get_cursor(conn)

    allowed = {'doc_num','vessel_name','doc_status','doc_date','vcn_doc_num',
               'operation_type','cargo_type'}
    where_clauses, params = [], []
    for f in (filters or []):
        field = f.get('field', '')
        if field not in allowed:
            continue
        ftype = f.get('type')
        if ftype == 'contains' and f.get('value'):
            where_clauses.append(f"{field} ILIKE %s")
            params.append(f"%{f['value']}%")
        elif ftype == 'multi' and f.get('values'):
            ph = ','.join(['%s'] * len(f['values']))
            where_clauses.append(f"{field} IN ({ph})")
            params.extend(f['values'])
        elif ftype == 'range':
            if f.get('from'):
                where_clauses.append(f"{field} >= %s")
                params.append(f['from'])
            if f.get('to'):
                where_clauses.append(f"{field} <= %s")
                params.append(f['to'])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    try:
        cur.execute(f'SELECT COUNT(*) FROM ldud_header {where_sql}', params)
        total = cur.fetchone()['count']
        cur.execute(f'SELECT * FROM ldud_header {where_sql} ORDER BY id DESC LIMIT %s OFFSET %s',
                    params + [size, (page - 1) * size])
        rows = [dict(r) for r in cur.fetchall()]

        # Collect vcn_ids to batch-fetch computed fields
        vcn_ids = list(set(r['vcn_id'] for r in rows if r.get('vcn_id')))
        ldud_ids = [r['id'] for r in rows if r.get('id')]

        vcn_cargo = {}   # vcn_id -> {cargo_names, bl_quantities}
        vcn_agents = {}  # vcn_id -> {agent_name, stevedore_name}
        vcn_meta = {}    # vcn_id -> {doc_date}
        vo_by_cargo = {} # ldud_id -> {cargo_name: total_qty}
        vo_times = {}    # ldud_id -> {first_start, last_end}

        if vcn_ids:
            # Fetch doc_date for display
            cur.execute('SELECT id, doc_date FROM vcn_header WHERE id = ANY(%s)', (vcn_ids,))
            for v in cur.fetchall():
                vcn_meta[v['id']] = {'doc_date': v['doc_date'] or ''}

            # Cargo names, BL quantities and UOM from VCN cargo declarations (Import + Export)
            cur.execute('''SELECT vcn_id, cargo_name, bl_quantity, quantity_uom FROM vcn_cargo_declaration
                           WHERE vcn_id = ANY(%s) AND cargo_name IS NOT NULL''', (vcn_ids,))
            import_cargo = cur.fetchall()
            cur.execute('''SELECT vcn_id, cargo_name, bl_quantity, quantity_uom FROM vcn_export_cargo_declaration
                           WHERE vcn_id = ANY(%s) AND cargo_name IS NOT NULL''', (vcn_ids,))
            export_cargo = cur.fetchall()
            for row_list in [import_cargo, export_cargo]:
                for c in row_list:
                    vid = c['vcn_id']
                    if vid not in vcn_cargo:
                        vcn_cargo[vid] = {'names': [], 'quantities': [], 'uoms': []}
                    name = c['cargo_name']
                    qty = float(c['bl_quantity'] or 0)
                    uom = c['quantity_uom'] or ''
                    if name not in vcn_cargo[vid]['names']:
                        vcn_cargo[vid]['names'].append(name)
                        vcn_cargo[vid]['quantities'].append(qty)
                        vcn_cargo[vid]['uoms'].append(uom)
                    else:
                        idx = vcn_cargo[vid]['names'].index(name)
                        vcn_cargo[vid]['quantities'][idx] += qty
                        if not vcn_cargo[vid]['uoms'][idx] and uom:
                            vcn_cargo[vid]['uoms'][idx] = uom

            # Agent, Stevedore and meta from VCN header
            cur.execute('''SELECT id, vessel_agent_name, importer_exporter_name
                           FROM vcn_header WHERE id = ANY(%s)''', (vcn_ids,))
            for v in cur.fetchall():
                vcn_agents[v['id']] = {
                    'agent_name': v['vessel_agent_name'],
                    'stevedore_name': v['importer_exporter_name']
                }

        if ldud_ids:
            # Quantity from vessel_operations per ldud, grouped by cargo_name
            cur.execute('''SELECT ldud_id, cargo_name, SUM(quantity) as total_qty
                           FROM ldud_vessel_operations WHERE ldud_id = ANY(%s)
                           GROUP BY ldud_id, cargo_name''', (ldud_ids,))
            for v in cur.fetchall():
                lid = v['ldud_id']
                if lid not in vo_by_cargo:
                    vo_by_cargo[lid] = {}
                cn = v['cargo_name'] or ''
                vo_by_cargo[lid][cn] = float(v['total_qty'] or 0)

            # Earliest discharge_started and latest discharge_commenced from anchorage recording
            cur.execute('''SELECT ldud_id, MIN(discharge_started) as first_start, MAX(discharge_commenced) as last_end
                           FROM ldud_anchorage WHERE ldud_id = ANY(%s)
                           GROUP BY ldud_id''', (ldud_ids,))
            for v in cur.fetchall():
                vo_times[v['ldud_id']] = {
                    'first_start': str(v['first_start']).replace(' ', 'T') if v['first_start'] else None,
                    'last_end': str(v['last_end']).replace(' ', 'T') if v['last_end'] else None
                }

        # Enrich rows
        for r in rows:
            vid = r.get('vcn_id')
            lid = r.get('id')

            # Cargo info from VCN
            ci = vcn_cargo.get(vid, {'names': [], 'quantities': [], 'uoms': []})
            uoms = ci.get('uoms', [])
            r['cargo_names_display'] = ', '.join(ci['names']) if ci['names'] else ''
            bl_parts = []
            for i, q in enumerate(ci['quantities']):
                uom = uoms[i] if i < len(uoms) else ''
                bl_parts.append(f"{int(round(q))} {uom}".strip())
            r['bl_quantities_display'] = ', '.join(bl_parts) if bl_parts else ''

            # Per-cargo balance: BL qty - ops qty for each cargo
            cargo_ops = vo_by_cargo.get(lid, {})
            balances = []
            for i, name in enumerate(ci['names']):
                bl_qty = ci['quantities'][i]
                ops_qty = cargo_ops.get(name, 0)
                uom = uoms[i] if i < len(uoms) else ''
                bal = int(round(bl_qty - ops_qty))
                balances.append(f"{bal} {uom}".strip())
            r['balance_display'] = ', '.join(balances) if balances else ''

            # VCN doc date for display
            vm = vcn_meta.get(vid, {})
            r['vcn_doc_date'] = vm.get('doc_date', '')

            # Agent and Stevedore
            ai = vcn_agents.get(vid, {})
            r['agent_name'] = ai.get('agent_name', '')
            r['stevedore_name'] = ai.get('stevedore_name', '')

            # Discharge/Loading Started and Completed from vessel_operations
            vt = vo_times.get(lid, {})
            r['ops_started'] = vt.get('first_start')
            r['ops_completed'] = vt.get('last_end')

        return rows, total
    finally:
        conn.close()

def save_header(data):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')

    # Convert empty strings to None so timestamp/date columns get NULL
    for k in data:
        if data[k] == '':
            data[k] = None

    if row_id:
        _computed = {'id', 'doc_num', 'vcn_display', 'vcn_doc_date', 'cargo_names_display', 'bl_quantities_display',
                     'balance_display', 'agent_name', 'stevedore_name', 'ops_started', 'ops_completed'}
        cols = [k for k in data if k not in _computed]
        cur.execute(f"UPDATE ldud_header SET {', '.join([f'{c}=%s' for c in cols])} WHERE id=%s",
                   [data[c] for c in cols] + [row_id])
    else:
        data['doc_num'] = get_next_doc_num()
        _computed = {'id', 'vcn_display', 'cargo_names_display', 'bl_quantities_display',
                     'balance_display', 'agent_name', 'stevedore_name', 'ops_started', 'ops_completed'}
        cols = [k for k in data if k not in _computed]
        cur.execute(f"INSERT INTO ldud_header ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING id",
                   [data[c] for c in cols])
        row_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return row_id, data.get('doc_num')

def delete_header(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_header WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Delays sub-table operations
def get_delays(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM ldud_delays WHERE ldud_id=%s ORDER BY id DESC', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_delay(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)

    # Calculate total time
    total_mins = None
    total_hrs = None
    if data.get('start_datetime') and data.get('end_datetime'):
        from datetime import datetime
        try:
            start = datetime.fromisoformat(data['start_datetime'])
            end = datetime.fromisoformat(data['end_datetime'])
            diff = (end - start).total_seconds()
            total_mins = round(diff / 60, 2)
            total_hrs = round(diff / 3600, 2)
        except:
            pass

    if data.get('id'):
        cur.execute('''UPDATE ldud_delays SET delay_name=%s,
                      start_datetime=%s, end_datetime=%s, total_time_mins=%s, total_time_hrs=%s,
                      minus_delay_hours=%s, crane_number=%s WHERE id=%s''',
                   [data.get('delay_name'),
                    data.get('start_datetime'), data.get('end_datetime'), total_mins, total_hrs,
                    data.get('minus_delay_hours'), data.get('crane_number'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO ldud_delays (ldud_id, delay_name,
                      start_datetime, end_datetime, total_time_mins, total_time_hrs, minus_delay_hours, crane_number)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], data.get('delay_name'),
                    data.get('start_datetime'), data.get('end_datetime'), total_mins, total_hrs,
                    data.get('minus_delay_hours'), data.get('crane_number')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id, total_mins, total_hrs

def delete_delay(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_delays WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Barge Lines sub-table operations
def get_barge_lines(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM ldud_barge_lines WHERE ldud_id=%s ORDER BY trip_number, id DESC', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_next_trip_number(ldud_id, barge_name):
    """Get the next trip number for a barge in this LDUD"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''SELECT MAX(trip_number) FROM ldud_barge_lines
                            WHERE ldud_id=%s AND barge_name=%s''', (ldud_id, barge_name))
    result = cur.fetchone()['max']
    conn.close()
    return (result or 0) + 1

def save_barge_line(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)

    if data.get('id'):
        # Check if barge_name changed, if so recalculate trip number
        cur.execute('SELECT barge_name FROM ldud_barge_lines WHERE id=%s', (data['id'],))
        existing = cur.fetchone()
        trip_number = data.get('trip_number')
        if existing and existing['barge_name'] != data.get('barge_name') and data.get('barge_name'):
            trip_number = get_next_trip_number(data.get('ldud_id'), data.get('barge_name'))

        cur.execute('''UPDATE ldud_barge_lines SET trip_number=%s, hold_name=%s, barge_name=%s, contractor_name=%s, cargo_name=%s,
                      bpt_bfl=%s, along_side_vessel=%s, commenced_loading=%s, completed_loading=%s, cast_off_mv=%s,
                      anchored_gull_island=%s, aweigh_gull_island=%s, along_side_berth=%s, commence_discharge_berth=%s,
                      completed_discharge_berth=%s, cast_off_berth=%s, cast_off_berth_nt=%s, discharge_quantity=%s,
                      crane_loaded_from=%s, trip_start=%s, amf_at_port=%s, cast_off_port=%s, port_crane=%s,
                      cast_off_loading_berth=%s, anchored_gull_island_empty=%s, aweigh_gull_island_empty=%s WHERE id=%s''',
                   [trip_number, data.get('hold_name'), data.get('barge_name'), data.get('contractor_name'), data.get('cargo_name'),
                    data.get('bpt_bfl'), data.get('along_side_vessel'), data.get('commenced_loading'),
                    data.get('completed_loading'), data.get('cast_off_mv'), data.get('anchored_gull_island'),
                    data.get('aweigh_gull_island'), data.get('along_side_berth'), data.get('commence_discharge_berth'),
                    data.get('completed_discharge_berth'), data.get('cast_off_berth'), data.get('cast_off_berth_nt'),
                    data.get('discharge_quantity'), data.get('crane_loaded_from'), data.get('trip_start'),
                    data.get('amf_at_port'), data.get('cast_off_port'), data.get('port_crane'),
                    data.get('cast_off_loading_berth'), data.get('anchored_gull_island_empty'),
                    data.get('aweigh_gull_island_empty'), data['id']])
        row_id = data['id']
    else:
        # Use explicit trip_number if provided (e.g. cloning a row for multiple cargo on same trip)
        trip_number = data.get('trip_number')
        if not trip_number:
            trip_number = 1
            if data.get('barge_name'):
                trip_number = get_next_trip_number(data['ldud_id'], data.get('barge_name'))

        cur.execute('''INSERT INTO ldud_barge_lines (ldud_id, trip_number, hold_name, barge_name, contractor_name, cargo_name,
                      bpt_bfl, along_side_vessel, commenced_loading, completed_loading, cast_off_mv,
                      anchored_gull_island, aweigh_gull_island, along_side_berth, commence_discharge_berth,
                      completed_discharge_berth, cast_off_berth, cast_off_berth_nt, discharge_quantity,
                      crane_loaded_from, trip_start, amf_at_port, cast_off_port, port_crane,
                      cast_off_loading_berth, anchored_gull_island_empty, aweigh_gull_island_empty)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], trip_number, data.get('hold_name'), data.get('barge_name'), data.get('contractor_name'), data.get('cargo_name'),
                    data.get('bpt_bfl'), data.get('along_side_vessel'), data.get('commenced_loading'),
                    data.get('completed_loading'), data.get('cast_off_mv'), data.get('anchored_gull_island'),
                    data.get('aweigh_gull_island'), data.get('along_side_berth'), data.get('commence_discharge_berth'),
                    data.get('completed_discharge_berth'), data.get('cast_off_berth'), data.get('cast_off_berth_nt'),
                    data.get('discharge_quantity'), data.get('crane_loaded_from'), data.get('trip_start'),
                    data.get('amf_at_port'), data.get('cast_off_port'), data.get('port_crane'),
                    data.get('cast_off_loading_berth'), data.get('anchored_gull_island_empty'),
                    data.get('aweigh_gull_island_empty')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id, trip_number

def delete_barge_line(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_barge_lines WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Anchorage Recording sub-table operations
def get_anchorage(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM ldud_anchorage WHERE ldud_id=%s ORDER BY id DESC', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_anchorage(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE ldud_anchorage SET anchorage_name=%s, anchored=%s, discharge_started=%s,
                      discharge_commenced=%s, anchor_aweigh=%s, cargo_quantity=%s, cargo_name=%s WHERE id=%s''',
                   [data.get('anchorage_name'), data.get('anchored'), data.get('discharge_started'),
                    data.get('discharge_commenced'), data.get('anchor_aweigh'), data.get('cargo_quantity'),
                    data.get('cargo_name'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO ldud_anchorage (ldud_id, anchorage_name, anchored, discharge_started,
                      discharge_commenced, anchor_aweigh, cargo_quantity, cargo_name)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], data.get('anchorage_name'), data.get('anchored'), data.get('discharge_started'),
                    data.get('discharge_commenced'), data.get('anchor_aweigh'), data.get('cargo_quantity'),
                    data.get('cargo_name')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

def delete_anchorage(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_anchorage WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Vessel Operations sub-table operations
def get_vessel_operations(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM ldud_vessel_operations WHERE ldud_id=%s ORDER BY id DESC', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_vessel_operation(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE ldud_vessel_operations SET hold_name=%s, start_time=%s, end_time=%s,
                      cargo_name=%s, quantity=%s WHERE id=%s''',
                   [data.get('hold_name'), data.get('start_time'), data.get('end_time'),
                    data.get('cargo_name'), data.get('quantity'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO ldud_vessel_operations (ldud_id, hold_name, start_time, end_time, cargo_name, quantity)
                      VALUES (%s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], data.get('hold_name'), data.get('start_time'), data.get('end_time'),
                    data.get('cargo_name'), data.get('quantity')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_vessel_operation(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_vessel_operations WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Barge Cleaning Lines sub-table operations
def get_barge_cleaning(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM ldud_barge_cleaning WHERE ldud_id=%s ORDER BY id DESC', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_barge_cleaning(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE ldud_barge_cleaning SET barge_name=%s, payloader_name=%s,
                      hmr_start=%s, hmr_end=%s, diesel_start=%s, diesel_end=%s,
                      start_time=%s, end_time=%s WHERE id=%s''',
                   [data.get('barge_name'), data.get('payloader_name'),
                    data.get('hmr_start'), data.get('hmr_end'),
                    data.get('diesel_start'), data.get('diesel_end'),
                    data.get('start_time'), data.get('end_time'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO ldud_barge_cleaning (ldud_id, barge_name, payloader_name,
                      hmr_start, hmr_end, diesel_start, diesel_end, start_time, end_time)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], data.get('barge_name'), data.get('payloader_name'),
                    data.get('hmr_start'), data.get('hmr_end'),
                    data.get('diesel_start'), data.get('diesel_end'),
                    data.get('start_time'), data.get('end_time')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_barge_cleaning(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_barge_cleaning WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Hold Completion sub-table operations
def get_hold_completion(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM ldud_hold_completion WHERE ldud_id=%s ORDER BY id ASC', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_hold_completion(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE ldud_hold_completion SET hold_name=%s, commenced=%s, completed=%s WHERE id=%s''',
                   [data.get('hold_name'), data.get('commenced'), data.get('completed'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO ldud_hold_completion (ldud_id, hold_name, commenced, completed)
                      VALUES (%s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], data.get('hold_name'), data.get('commenced'), data.get('completed')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_hold_completion(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM ldud_hold_completion WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Hold Cargo Config operations
def get_hold_cargo(ldud_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT hold_name, cargo_name FROM ldud_hold_cargo WHERE ldud_id=%s', (ldud_id,))
    rows = cur.fetchall()
    conn.close()
    return {r['hold_name']: r['cargo_name'] or '' for r in rows}


# Approval functions
def get_doc_status(record_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT doc_status FROM ldud_header WHERE id=%s', (record_id,))
    row = cur.fetchone()
    conn.close()
    return row['doc_status'] if row else None


def approve_record(record_id, username):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("UPDATE ldud_header SET doc_status='Approved' WHERE id=%s", (record_id,))
    cur.execute("""INSERT INTO approval_log (module_code, record_id, action, comment, actioned_by)
                   VALUES ('LDUD01', %s, 'Approved', NULL, %s)""", (record_id, username))
    conn.commit()
    conn.close()


def reject_record(record_id, comment, username):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("UPDATE ldud_header SET doc_status='Rejected' WHERE id=%s", (record_id,))
    cur.execute("""INSERT INTO approval_log (module_code, record_id, action, comment, actioned_by)
                   VALUES ('LDUD01', %s, 'Rejected', %s, %s)""", (record_id, comment, username))
    conn.commit()
    conn.close()


def get_approval_log(record_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("""SELECT action, comment, actioned_by,
                          to_char(actioned_at, 'DD-MM-YYYY HH24:MI') AS actioned_at
                   FROM approval_log WHERE module_code='LDUD01' AND record_id=%s
                   ORDER BY actioned_at DESC""", (record_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_hold_cargo(ldud_id, hold_name, cargo_name):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        INSERT INTO ldud_hold_cargo (ldud_id, hold_name, cargo_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (ldud_id, hold_name) DO UPDATE SET cargo_name = EXCLUDED.cargo_name
    ''', (ldud_id, hold_name, cargo_name or None))
    conn.commit()
    conn.close()

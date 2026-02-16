from database import get_db, get_cursor

def get_next_doc_num():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("SELECT MAX(CAST(SUBSTR(doc_num, 5) AS INTEGER)) FROM ldud_header WHERE doc_num LIKE 'LDUD%%'")
    result = cur.fetchone()['max']
    conn.close()
    next_num = (result or 0) + 1
    return f"LDUD{next_num}"

def get_vcn_list():
    """Get VCN entries with anchored datetime for dropdown"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT h.id, h.vcn_doc_num, h.vessel_name, a.anchorage_arrival
        FROM vcn_header h
        LEFT JOIN vcn_anchorage a ON a.vcn_id = h.id
        WHERE h.doc_status = 'Approved'
        ORDER BY h.vcn_doc_num DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        display = f"{r['vcn_doc_num']} / {r['vessel_name']}"
        if r['anchorage_arrival']:
            display += f" / {r['anchorage_arrival'].replace('T', ' ')}"
        result.append({
            'value': display,
            'vcn_id': r['id'],
            'vcn_doc_num': r['vcn_doc_num'],
            'vessel_name': r['vessel_name'],
            'anchored_datetime': r['anchorage_arrival']
        })
    return result

def get_data(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) FROM ldud_header')
    total = cur.fetchone()['count']
    cur.execute('SELECT * FROM ldud_header ORDER BY id DESC LIMIT %s OFFSET %s', (size, (page-1)*size))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total

def save_header(data):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')

    if row_id:
        cols = [k for k in data if k not in ['id', 'doc_num']]
        cur.execute(f"UPDATE ldud_header SET {', '.join([f'{c}=%s' for c in cols])} WHERE id=%s",
                   [data[c] for c in cols] + [row_id])
    else:
        data['doc_num'] = get_next_doc_num()
        cols = [k for k in data if k != 'id']
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
        cur.execute('''UPDATE ldud_delays SET delay_name=%s, delay_account_type=%s, equipment_name=%s,
                      start_datetime=%s, end_datetime=%s, total_time_mins=%s, total_time_hrs=%s,
                      delays_to_sof=%s, invoiceable=%s, minus_delay_hours=%s WHERE id=%s''',
                   [data.get('delay_name'), data.get('delay_account_type'), data.get('equipment_name'),
                    data.get('start_datetime'), data.get('end_datetime'), total_mins, total_hrs,
                    data.get('delays_to_sof'), data.get('invoiceable'), data.get('minus_delay_hours'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO ldud_delays (ldud_id, delay_name, delay_account_type, equipment_name,
                      start_datetime, end_datetime, total_time_mins, total_time_hrs, delays_to_sof, invoiceable, minus_delay_hours)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], data.get('delay_name'), data.get('delay_account_type'), data.get('equipment_name'),
                    data.get('start_datetime'), data.get('end_datetime'), total_mins, total_hrs,
                    data.get('delays_to_sof'), data.get('invoiceable'), data.get('minus_delay_hours')])
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
                      completed_discharge_berth=%s, cast_off_berth=%s, cast_off_berth_nt=%s, discharge_quantity=%s WHERE id=%s''',
                   [trip_number, data.get('hold_name'), data.get('barge_name'), data.get('contractor_name'), data.get('cargo_name'),
                    data.get('bpt_bfl'), data.get('along_side_vessel'), data.get('commenced_loading'),
                    data.get('completed_loading'), data.get('cast_off_mv'), data.get('anchored_gull_island'),
                    data.get('aweigh_gull_island'), data.get('along_side_berth'), data.get('commence_discharge_berth'),
                    data.get('completed_discharge_berth'), data.get('cast_off_berth'), data.get('cast_off_berth_nt'),
                    data.get('discharge_quantity'), data['id']])
        row_id = data['id']
    else:
        trip_number = 1
        if data.get('barge_name'):
            trip_number = get_next_trip_number(data['ldud_id'], data.get('barge_name'))

        cur.execute('''INSERT INTO ldud_barge_lines (ldud_id, trip_number, hold_name, barge_name, contractor_name, cargo_name,
                      bpt_bfl, along_side_vessel, commenced_loading, completed_loading, cast_off_mv,
                      anchored_gull_island, aweigh_gull_island, along_side_berth, commence_discharge_berth,
                      completed_discharge_berth, cast_off_berth, cast_off_berth_nt, discharge_quantity)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['ldud_id'], trip_number, data.get('hold_name'), data.get('barge_name'), data.get('contractor_name'), data.get('cargo_name'),
                    data.get('bpt_bfl'), data.get('along_side_vessel'), data.get('commenced_loading'),
                    data.get('completed_loading'), data.get('cast_off_mv'), data.get('anchored_gull_island'),
                    data.get('aweigh_gull_island'), data.get('along_side_berth'), data.get('commence_discharge_berth'),
                    data.get('completed_discharge_berth'), data.get('cast_off_berth'), data.get('cast_off_berth_nt'),
                    data.get('discharge_quantity')])
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

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
    cur.execute("SELECT MAX(CAST(SUBSTR(vcn_doc_num, 4) AS INTEGER)) FROM vcn_header WHERE vcn_doc_num LIKE 'VCN%%'")
    result = cur.fetchone()['max']
    conn.close()
    next_num = (result or 0) + 1
    return f"VCN{next_num}"

def get_vessels():
    """Get vessels from VC01 for dropdown"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT doc_num, vessel_name FROM vessels ORDER BY doc_num')
    rows = cur.fetchall()
    conn.close()
    return [{'value': f"{r['doc_num']}/{r['vessel_name']}", 'doc_num': r['doc_num'], 'vessel_name': r['vessel_name']} for r in rows]

def get_data(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) FROM vcn_header')
    total = cur.fetchone()['count']
    cur.execute('SELECT * FROM vcn_header ORDER BY id DESC LIMIT %s OFFSET %s', (size, (page-1)*size))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total

def save_header(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')

    if row_id:
        cols = [k for k in data if k not in ['id', 'vcn_doc_num']]
        cur.execute(f"UPDATE vcn_header SET {', '.join([f'{c}=%s' for c in cols])} WHERE id=%s",
                   [data[c] for c in cols] + [row_id])
    else:
        data['vcn_doc_num'] = get_next_doc_num()
        cols = [k for k in data if k != 'id']
        cur.execute(f"INSERT INTO vcn_header ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING id",
                   [data[c] for c in cols])
        row_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return row_id, data.get('vcn_doc_num')

def delete_header(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vcn_header WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Nomination sub-table operations
def get_nominations(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vcn_nominations WHERE vcn_id=%s ORDER BY id DESC', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_nomination(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE vcn_nominations SET eta=%s, etd=%s, vessel_run_type=%s,
                       arrival_fore_draft=%s, arrival_after_draft=%s WHERE id=%s''',
                   [data.get('eta'), data.get('etd'), data.get('vessel_run_type'),
                    data.get('arrival_fore_draft'), data.get('arrival_after_draft'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO vcn_nominations (vcn_id, eta, etd, vessel_run_type, arrival_fore_draft, arrival_after_draft)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['vcn_id'], data.get('eta'), data.get('etd'), data.get('vessel_run_type'),
                    data.get('arrival_fore_draft'), data.get('arrival_after_draft')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

def delete_nomination(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vcn_nominations WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Delays sub-table operations
def get_delays(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vcn_delays WHERE vcn_id=%s ORDER BY id DESC', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_delay(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('UPDATE vcn_delays SET delay_name=%s, delay_start=%s, delay_end=%s WHERE id=%s',
                   [data.get('delay_name'), data.get('delay_start'), data.get('delay_end'), data['id']])
        row_id = data['id']
    else:
        cur.execute('INSERT INTO vcn_delays (vcn_id, delay_name, delay_start, delay_end) VALUES (%s, %s, %s, %s) RETURNING id',
                   [data['vcn_id'], data.get('delay_name'), data.get('delay_start'), data.get('delay_end')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

def delete_delay(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vcn_delays WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Cargo Declaration sub-table operations (updated)
def get_cargo_declarations(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vcn_cargo_declaration WHERE vcn_id=%s ORDER BY id DESC', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cargo_names_for_vcn(vcn_id):
    """Get cargo names from cargo declaration for a specific VCN (for stowage plan dropdown)"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT DISTINCT cargo_name FROM vcn_cargo_declaration WHERE vcn_id=%s AND cargo_name IS NOT NULL', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [r['cargo_name'] for r in rows if r['cargo_name']]

def save_cargo_declaration(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE vcn_cargo_declaration SET cargo_name=%s, bl_no=%s, bl_date=%s, bl_quantity=%s,
                       quantity_uom=%s, customer_name=%s, igm_number=%s, igm_manual_number=%s, igm_date=%s WHERE id=%s''',
                   [data.get('cargo_name'), data.get('bl_no'), data.get('bl_date'), data.get('bl_quantity'),
                    data.get('quantity_uom'), data.get('customer_name'),
                    data.get('igm_number'), data.get('igm_manual_number'), data.get('igm_date'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO vcn_cargo_declaration (vcn_id, cargo_name, bl_no, bl_date, bl_quantity,
                       quantity_uom, customer_name, igm_number, igm_manual_number, igm_date)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['vcn_id'], data.get('cargo_name'), data.get('bl_no'), data.get('bl_date'), data.get('bl_quantity'),
                    data.get('quantity_uom'), data.get('customer_name'),
                    data.get('igm_number'), data.get('igm_manual_number'), data.get('igm_date')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

# Export Cargo Declaration sub-table operations
def get_export_cargo_declarations(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vcn_export_cargo_declaration WHERE vcn_id=%s ORDER BY id DESC', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_export_cargo_declaration(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('''UPDATE vcn_export_cargo_declaration SET egm_shipping_bill_number=%s, egm_shipping_bill_date=%s,
                       cargo_name=%s, customer_name=%s, bl_no=%s, bl_date=%s, bl_quantity=%s, quantity_uom=%s WHERE id=%s''',
                   [data.get('egm_shipping_bill_number'), data.get('egm_shipping_bill_date'),
                    data.get('cargo_name'), data.get('customer_name'),
                    data.get('bl_no'), data.get('bl_date'), data.get('bl_quantity'),
                    data.get('quantity_uom'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO vcn_export_cargo_declaration (vcn_id, egm_shipping_bill_number, egm_shipping_bill_date,
                       cargo_name, customer_name, bl_no, bl_date, bl_quantity, quantity_uom)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['vcn_id'], data.get('egm_shipping_bill_number'), data.get('egm_shipping_bill_date'),
                    data.get('cargo_name'), data.get('customer_name'),
                    data.get('bl_no'), data.get('bl_date'), data.get('bl_quantity'),
                    data.get('quantity_uom')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

def delete_export_cargo_declaration(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vcn_export_cargo_declaration WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

def get_export_cargo_names_for_vcn(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT DISTINCT cargo_name FROM vcn_export_cargo_declaration WHERE vcn_id=%s AND cargo_name IS NOT NULL', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [r['cargo_name'] for r in rows if r['cargo_name']]

def get_export_cargo_total_quantity(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT SUM(bl_quantity) FROM vcn_export_cargo_declaration WHERE vcn_id=%s', (vcn_id,))
    result = cur.fetchone()['sum']
    conn.close()
    return result or 0

def delete_cargo_declaration(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vcn_cargo_declaration WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

def get_cargo_total_quantity(vcn_id):
    """Get total BL quantity from cargo declarations for a VCN (replaces IGM total)"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT SUM(bl_quantity) FROM vcn_cargo_declaration WHERE vcn_id=%s', (vcn_id,))
    result = cur.fetchone()['sum']
    conn.close()
    return result or 0

# Stowage Plan sub-table operations
def get_stowage_plan(vcn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vcn_stowage_plan WHERE vcn_id=%s ORDER BY id ASC', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stowage_total_quantity(vcn_id):
    """Get total stowage quantity for a VCN"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT SUM(hatchwise_quantity) FROM vcn_stowage_plan WHERE vcn_id=%s', (vcn_id,))
    result = cur.fetchone()['sum']
    conn.close()
    return result or 0

def save_stowage_plan(data):
    _clean_empty(data)
    conn = get_db()
    cur = get_cursor(conn)

    # Validate that hatchwise quantity doesn't exceed cargo BL total
    vcn_id = data.get('vcn_id')
    if vcn_id:
        # Check operation_type to use correct cargo total
        cur.execute('SELECT operation_type FROM vcn_header WHERE id=%s', (vcn_id,))
        header_row = cur.fetchone()
        op_type = header_row['operation_type'] if header_row else None
        if op_type == 'Export':
            igm_total = get_export_cargo_total_quantity(vcn_id)
        else:
            igm_total = get_cargo_total_quantity(vcn_id)
        current_stowage_total = get_stowage_total_quantity(vcn_id)
        new_quantity = data.get('hatchwise_quantity') or 0

        # If updating, subtract the old quantity
        if data.get('id'):
            cur.execute('SELECT hatchwise_quantity FROM vcn_stowage_plan WHERE id=%s', (data['id'],))
            old_row = cur.fetchone()
            if old_row:
                current_stowage_total -= (old_row['hatchwise_quantity'] or 0)

        # Check if new total would exceed IGM quantity
        if current_stowage_total + new_quantity > igm_total:
            conn.close()
            return None, f"Total stowage quantity ({current_stowage_total + new_quantity}) cannot exceed cargo BL quantity ({igm_total})"

    if data.get('id'):
        cur.execute('UPDATE vcn_stowage_plan SET cargo_name=%s, hold_name=%s, hatchwise_quantity=%s, hatch_completion_time=%s WHERE id=%s',
                   [data.get('cargo_name'), data.get('hold_name'), data.get('hatchwise_quantity'), data.get('hatch_completion_time'), data['id']])
        row_id = data['id']
    else:
        cur.execute('INSERT INTO vcn_stowage_plan (vcn_id, cargo_name, hold_name, hatchwise_quantity, hatch_completion_time) VALUES (%s, %s, %s, %s, %s) RETURNING id',
                   [data['vcn_id'], data.get('cargo_name'), data.get('hold_name'), data.get('hatchwise_quantity'), data.get('hatch_completion_time')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id, None

def delete_stowage_plan(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vcn_stowage_plan WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

def get_export_loading_totals(vcn_id):
    """Get loading totals from LDUD MV Anchorage Loading for a VCN, grouped by cargo_name for BL quantity"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''SELECT vo.cargo_name, SUM(vo.quantity) as total_qty
                   FROM ldud_vessel_operations vo
                   JOIN ldud_header h ON vo.ldud_id = h.id
                   WHERE h.vcn_id=%s AND vo.cargo_name IS NOT NULL
                   GROUP BY vo.cargo_name''', (vcn_id,))
    rows = cur.fetchall()
    conn.close()
    return {r['cargo_name']: float(r['total_qty'] or 0) for r in rows}

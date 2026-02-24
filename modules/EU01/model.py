from database import get_db, get_cursor


def get_all_lines(page=1, size=20, equipment_name=None):
    conn = get_db()
    cur = get_cursor(conn)
    offset = (page - 1) * size

    if equipment_name:
        cur.execute('SELECT COUNT(*) as cnt FROM eu_lines WHERE equipment_name = %s', [equipment_name])
        total = cur.fetchone()['cnt']
        cur.execute('SELECT * FROM eu_lines WHERE equipment_name = %s ORDER BY id DESC LIMIT %s OFFSET %s',
                    [equipment_name, size, offset])
    else:
        cur.execute('SELECT COUNT(*) as cnt FROM eu_lines')
        total = cur.fetchone()['cnt']
        cur.execute('SELECT * FROM eu_lines ORDER BY id DESC LIMIT %s OFFSET %s', [size, offset])

    rows = cur.fetchall()
    conn.close()

    return {
        'data': [dict(r) for r in rows],
        'last_page': (total + size - 1) // size,
        'total': total
    }


def save_line(data):
    conn = get_db()
    cur = get_cursor(conn)

    line_id = data.get('id')

    if line_id:
        cur.execute('''
            UPDATE eu_lines SET
                source_type = %s, source_id = %s, source_display = %s, barge_name = %s,
                equipment_name = %s, operator_name = %s, delay_name = %s, cargo_name = %s,
                operation_type = %s, quantity = %s, quantity_uom = %s, route_name = %s,
                start_time = %s, end_time = %s, entry_date = %s,
                shift = %s, from_time = %s, to_time = %s, system_name = %s,
                berth_name = %s, shift_incharge = %s, remarks = %s
            WHERE id = %s
        ''', [
            data.get('source_type'), data.get('source_id'), data.get('source_display'),
            data.get('barge_name'), data.get('equipment_name'), data.get('operator_name'),
            data.get('delay_name'), data.get('cargo_name'), data.get('operation_type'),
            data.get('quantity'), data.get('quantity_uom'), data.get('route_name'),
            data.get('start_time'), data.get('end_time'), data.get('entry_date'),
            data.get('shift'), data.get('from_time'), data.get('to_time'), data.get('system_name'),
            data.get('berth_name'), data.get('shift_incharge'), data.get('remarks'), line_id
        ])
    else:
        from datetime import datetime
        cur.execute('''
            INSERT INTO eu_lines
            (source_type, source_id, source_display, barge_name, equipment_name, operator_name,
             delay_name, cargo_name, operation_type, quantity, quantity_uom, route_name,
             start_time, end_time, entry_date, created_by, created_date,
             shift, from_time, to_time, system_name, berth_name, shift_incharge, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', [
            data.get('source_type'), data.get('source_id'), data.get('source_display'),
            data.get('barge_name'), data.get('equipment_name'), data.get('operator_name'),
            data.get('delay_name'), data.get('cargo_name'), data.get('operation_type'),
            data.get('quantity'), data.get('quantity_uom'), data.get('route_name'),
            data.get('start_time'), data.get('end_time'), data.get('entry_date'),
            data.get('created_by'), datetime.now().strftime('%Y-%m-%d'),
            data.get('shift'), data.get('from_time'), data.get('to_time'), data.get('system_name'),
            data.get('berth_name'), data.get('shift_incharge'), data.get('remarks')
        ])
        line_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return line_id


def delete_lines(ids):
    conn = get_db()
    cur = get_cursor(conn)
    for line_id in ids:
        cur.execute('DELETE FROM eu_lines WHERE id = %s', [line_id])
    conn.commit()
    conn.close()


def get_vcn_options():
    """Get VCN entries with vessel name and anchored time for dropdown"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT h.id, h.vcn_doc_num, h.vessel_name, a.anchorage_arrival
        FROM vcn_header h
        LEFT JOIN vcn_anchorage a ON h.id = a.vcn_id
        ORDER BY h.vcn_doc_num DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mbc_options():
    """Get MBC entries for dropdown with doc_date"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT id, doc_num, mbc_name, doc_date FROM mbc_header ORDER BY doc_num DESC')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vcn_barges(vcn_id):
    """Get barges from a specific VCN's LDUD barge lines"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT id FROM ldud_header WHERE vcn_id = %s', [vcn_id])
    ldud = cur.fetchone()
    if ldud:
        cur.execute('''
            SELECT DISTINCT barge_name FROM ldud_barge_lines WHERE ldud_id = %s AND barge_name IS NOT NULL AND barge_name != ''
        ''', [ldud['id']])
        rows = cur.fetchall()
        conn.close()
        return [r['barge_name'] for r in rows]
    conn.close()
    return []


def get_mbc_names():
    """Get all MBC names from master"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT mbc_name FROM mbc_master ORDER BY mbc_name')
    rows = cur.fetchall()
    conn.close()
    return [r['mbc_name'] for r in rows]


def get_barge_cargos(vcn_id, barge_name):
    """Get cargo names for a specific barge from a VCN's LDUD"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT id FROM ldud_header WHERE vcn_id = %s', [vcn_id])
    ldud = cur.fetchone()
    cargos = []
    if ldud:
        cur.execute('''
            SELECT DISTINCT cargo FROM ldud_barge_lines
            WHERE ldud_id = %s AND barge_name = %s AND cargo IS NOT NULL AND cargo != ''
        ''', [ldud['id'], barge_name])
        cargos = [r['cargo'] for r in cur.fetchall()]
    conn.close()
    return cargos

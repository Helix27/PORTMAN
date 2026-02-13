from database import get_db, get_cursor


def get_all_lines(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    offset = (page - 1) * size

    cur.execute('SELECT * FROM eu_lines ORDER BY id DESC LIMIT %s OFFSET %s', [size, offset])
    rows = cur.fetchall()

    cur.execute('SELECT COUNT(*) as cnt FROM eu_lines')
    total = cur.fetchone()['cnt']
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
        # Update existing
        cur.execute('''
            UPDATE eu_lines SET
                source_type = %s, source_id = %s, source_display = %s, barge_name = %s,
                equipment_name = %s, operator_name = %s, delay_name = %s, cargo_name = %s,
                operation_type = %s, quantity = %s, quantity_uom = %s, route_name = %s,
                start_time = %s, end_time = %s, entry_date = %s
            WHERE id = %s
        ''', [
            data.get('source_type'), data.get('source_id'), data.get('source_display'),
            data.get('barge_name'), data.get('equipment_name'), data.get('operator_name'),
            data.get('delay_name'), data.get('cargo_name'), data.get('operation_type'),
            data.get('quantity'), data.get('quantity_uom'), data.get('route_name'),
            data.get('start_time'), data.get('end_time'), data.get('entry_date'), line_id
        ])
    else:
        # Insert new
        from datetime import datetime
        cur.execute('''
            INSERT INTO eu_lines
            (source_type, source_id, source_display, barge_name, equipment_name, operator_name,
             delay_name, cargo_name, operation_type, quantity, quantity_uom, route_name,
             start_time, end_time, entry_date, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', [
            data.get('source_type'), data.get('source_id'), data.get('source_display'),
            data.get('barge_name'), data.get('equipment_name'), data.get('operator_name'),
            data.get('delay_name'), data.get('cargo_name'), data.get('operation_type'),
            data.get('quantity'), data.get('quantity_uom'), data.get('route_name'),
            data.get('start_time'), data.get('end_time'), data.get('entry_date'),
            data.get('created_by'), datetime.now().strftime('%Y-%m-%d')
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
        SELECT h.id, h.vcn_doc_num, h.vessel_name, a.anchored_time
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
    # Get the LDUD for this VCN
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


def get_vex_options():
    """Get VEX entries for dropdown with bill_of_coastal_goods_date"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT id, vex_doc_num, vessel_name, bill_of_coastal_goods_date
        FROM vex_header
        ORDER BY vex_doc_num DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vex_barges(vex_id):
    """Get barges from a specific VEX's barge lines"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT DISTINCT barge_name FROM vex_barge_lines
        WHERE vex_id = %s AND barge_name IS NOT NULL AND barge_name != ''
    ''', [vex_id])
    rows = cur.fetchall()
    conn.close()
    return [r['barge_name'] for r in rows]


def get_vex_mbcs(vex_id):
    """Get MBCs from a specific VEX's MBC lines"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT DISTINCT mbc_name FROM vex_mbc_lines
        WHERE vex_id = %s AND mbc_name IS NOT NULL AND mbc_name != ''
    ''', [vex_id])
    rows = cur.fetchall()
    conn.close()
    return [r['mbc_name'] for r in rows]

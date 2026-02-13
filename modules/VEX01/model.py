from database import get_db, get_cursor

def get_next_doc_num():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("SELECT MAX(CAST(SUBSTR(vex_doc_num, 4) AS INTEGER)) FROM vex_header WHERE vex_doc_num LIKE 'VEX%%'")
    result = cur.fetchone()['max']
    conn.close()
    next_num = (result or 0) + 1
    return f"VEX{next_num}"

def get_data(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) FROM vex_header')
    total = cur.fetchone()['count']
    cur.execute('SELECT * FROM vex_header ORDER BY id DESC LIMIT %s OFFSET %s', (size, (page-1)*size))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total

def save_header(data):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')

    if row_id:
        cols = [k for k in data if k not in ['id', 'vex_doc_num']]
        cur.execute(f"UPDATE vex_header SET {', '.join([f'{c}=%s' for c in cols])} WHERE id=%s",
                   [data[c] for c in cols] + [row_id])
    else:
        data['vex_doc_num'] = get_next_doc_num()
        cols = [k for k in data if k != 'id']
        cur.execute(f"INSERT INTO vex_header ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING id",
                   [data[c] for c in cols])
        row_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return row_id, data.get('vex_doc_num')

def delete_header(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vex_header WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# Barge Lines sub-table operations
def get_barge_lines(vex_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vex_barge_lines WHERE vex_id=%s ORDER BY id DESC', (vex_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_barge_line(data):
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('UPDATE vex_barge_lines SET barge_name=%s WHERE id=%s',
                   [data.get('barge_name'), data['id']])
        row_id = data['id']
    else:
        cur.execute('INSERT INTO vex_barge_lines (vex_id, barge_name) VALUES (%s, %s) RETURNING id',
                   [data['vex_id'], data.get('barge_name')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

def delete_barge_line(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vex_barge_lines WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

# MBC Lines sub-table operations
def get_mbc_lines(vex_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM vex_mbc_lines WHERE vex_id=%s ORDER BY id DESC', (vex_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_mbc_line(data):
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute('UPDATE vex_mbc_lines SET mbc_name=%s WHERE id=%s',
                   [data.get('mbc_name'), data['id']])
        row_id = data['id']
    else:
        cur.execute('INSERT INTO vex_mbc_lines (vex_id, mbc_name) VALUES (%s, %s) RETURNING id',
                   [data['vex_id'], data.get('mbc_name')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id

def delete_mbc_line(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM vex_mbc_lines WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

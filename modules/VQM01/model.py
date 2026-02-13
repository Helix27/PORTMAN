from database import get_db, get_cursor

def get_all():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("SELECT name FROM quantity_uom ORDER BY name")
    result = [row['name'] for row in cur.fetchall()]
    conn.close()
    return result

def get_data(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    offset = (page - 1) * size
    cur.execute("SELECT COUNT(*) FROM quantity_uom")
    total = cur.fetchone()['count']
    cur.execute("SELECT * FROM quantity_uom ORDER BY id DESC LIMIT %s OFFSET %s", [size, offset])
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"data": rows, "last_page": (total + size - 1) // size, "total": total}

def save_data(data):
    conn = get_db()
    cur = get_cursor(conn)
    if data.get('id'):
        cur.execute("UPDATE quantity_uom SET name=%s WHERE id=%s", [data.get('name'), data['id']])
    else:
        cur.execute("INSERT INTO quantity_uom (name) VALUES (%s) RETURNING id", [data.get('name')])
        data['id'] = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return data

def delete_data(id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("DELETE FROM quantity_uom WHERE id=%s", [id])
    conn.commit()
    conn.close()

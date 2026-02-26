from database import get_db, get_cursor
from datetime import datetime


def get_credit_notes(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM credit_note_header')
    total = cur.fetchone()['cnt']
    cur.execute('''
        SELECT cn.*, i.invoice_number
        FROM credit_note_header cn
        LEFT JOIN invoice_header i ON cn.invoice_id = i.id
        ORDER BY cn.id DESC LIMIT %s OFFSET %s
    ''', [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_credit_note(cn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT cn.*, i.invoice_number
        FROM credit_note_header cn
        LEFT JOIN invoice_header i ON cn.invoice_id = i.id
        WHERE cn.id = %s
    ''', [cn_id])
    header = cur.fetchone()
    if not header:
        conn.close()
        return None, []
    header = dict(header)
    cur.execute('SELECT * FROM credit_note_lines WHERE credit_note_id = %s ORDER BY id', [cn_id])
    lines = [dict(r) for r in cur.fetchall()]
    conn.close()
    return header, lines


def save_credit_note(data, username=None):
    conn = get_db()
    cur = get_cursor(conn)
    cn_id = data.get('id')
    now = datetime.now().strftime('%Y-%m-%d')

    if cn_id:
        cur.execute('''UPDATE credit_note_header SET
            invoice_id=%s, cn_number=%s, cn_date=%s, reason=%s,
            total_amount=%s, cgst_amount=%s, sgst_amount=%s, igst_amount=%s,
            grand_total=%s, status=%s, sap_document_number=%s, sap_fiscal_year=%s
            WHERE id=%s''', [
            data.get('invoice_id'), data.get('cn_number'), data.get('cn_date'),
            data.get('reason'), data.get('total_amount', 0),
            data.get('cgst_amount', 0), data.get('sgst_amount', 0),
            data.get('igst_amount', 0), data.get('grand_total', 0),
            data.get('status', 'Draft'),
            data.get('sap_document_number'), data.get('sap_fiscal_year'),
            cn_id
        ])
    else:
        cur.execute('''INSERT INTO credit_note_header
            (invoice_id, cn_number, cn_date, reason, total_amount,
             cgst_amount, sgst_amount, igst_amount, grand_total,
             status, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id''', [
            data.get('invoice_id'), data.get('cn_number'), data.get('cn_date'),
            data.get('reason'), data.get('total_amount', 0),
            data.get('cgst_amount', 0), data.get('sgst_amount', 0),
            data.get('igst_amount', 0), data.get('grand_total', 0),
            'Draft', username, now
        ])
        cn_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return cn_id


def save_credit_note_line(data):
    conn = get_db()
    cur = get_cursor(conn)
    line_id = data.get('id')

    if line_id:
        cur.execute('''UPDATE credit_note_lines SET
            invoice_line_id=%s, service_name=%s, description=%s,
            quantity=%s, rate=%s, amount=%s, gst_rate=%s,
            cgst_amount=%s, sgst_amount=%s, igst_amount=%s,
            gl_code=%s, sap_tax_code=%s
            WHERE id=%s''', [
            data.get('invoice_line_id'), data.get('service_name'),
            data.get('description'), data.get('quantity'), data.get('rate'),
            data.get('amount', 0), data.get('gst_rate'),
            data.get('cgst_amount', 0), data.get('sgst_amount', 0),
            data.get('igst_amount', 0), data.get('gl_code'),
            data.get('sap_tax_code'), line_id
        ])
    else:
        cur.execute('''INSERT INTO credit_note_lines
            (credit_note_id, invoice_line_id, service_name, description,
             quantity, rate, amount, gst_rate,
             cgst_amount, sgst_amount, igst_amount, gl_code, sap_tax_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id''', [
            data.get('credit_note_id'), data.get('invoice_line_id'),
            data.get('service_name'), data.get('description'),
            data.get('quantity'), data.get('rate'), data.get('amount', 0),
            data.get('gst_rate'), data.get('cgst_amount', 0),
            data.get('sgst_amount', 0), data.get('igst_amount', 0),
            data.get('gl_code'), data.get('sap_tax_code')
        ])
        line_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return line_id


def delete_credit_note(cn_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM credit_note_lines WHERE credit_note_id = %s', [cn_id])
    cur.execute('DELETE FROM credit_note_header WHERE id = %s', [cn_id])
    conn.commit()
    conn.close()


def delete_credit_note_line(line_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM credit_note_lines WHERE id = %s', [line_id])
    conn.commit()
    conn.close()


def get_invoices_for_dropdown():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''SELECT id, invoice_number, invoice_date, customer_name, grand_total
        FROM invoice_header WHERE status != 'Cancelled'
        ORDER BY id DESC LIMIT 200''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

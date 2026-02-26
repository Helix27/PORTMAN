from database import get_db, get_cursor
from datetime import datetime


# ===== ADVANCE RECEIPTS =====

def get_advance_receipts(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM advance_receipts')
    total = cur.fetchone()['cnt']
    cur.execute('SELECT * FROM advance_receipts ORDER BY id DESC LIMIT %s OFFSET %s',
                [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def save_advance_receipt(data, username=None):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')
    now = datetime.now().strftime('%Y-%m-%d')
    if row_id:
        cur.execute('''UPDATE advance_receipts SET
            party_type=%s, party_id=%s, party_name=%s,
            receipt_number=%s, receipt_date=%s, amount=%s, currency=%s,
            sap_document_number=%s, sap_fiscal_year=%s,
            payment_method=%s, bank_reference=%s, remarks=%s, status=%s
            WHERE id=%s''', [
            data.get('party_type'), data.get('party_id'), data.get('party_name'),
            data.get('receipt_number'), data.get('receipt_date'),
            data.get('amount', 0), data.get('currency', 'INR'),
            data.get('sap_document_number'), data.get('sap_fiscal_year'),
            data.get('payment_method'), data.get('bank_reference'),
            data.get('remarks'), data.get('status', 'Pending'), row_id
        ])
    else:
        cur.execute('''INSERT INTO advance_receipts
            (party_type, party_id, party_name, receipt_number, receipt_date,
             amount, currency, payment_method, bank_reference, remarks,
             status, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id''', [
            data.get('party_type'), data.get('party_id'), data.get('party_name'),
            data.get('receipt_number'), data.get('receipt_date'),
            data.get('amount', 0), data.get('currency', 'INR'),
            data.get('payment_method'), data.get('bank_reference'),
            data.get('remarks'), 'Pending', username, now
        ])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_advance_receipt(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM advance_receipts WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# ===== INCOMING PAYMENTS =====

def get_incoming_payments(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM customer_incoming_payments')
    total = cur.fetchone()['cnt']
    cur.execute('SELECT * FROM customer_incoming_payments ORDER BY id DESC LIMIT %s OFFSET %s',
                [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def save_incoming_payment(data, username=None):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')
    now = datetime.now().strftime('%Y-%m-%d')
    if row_id:
        cur.execute('''UPDATE customer_incoming_payments SET
            party_type=%s, party_id=%s, party_name=%s,
            invoice_id=%s, payment_number=%s, payment_date=%s,
            amount=%s, currency=%s, sap_document_number=%s, sap_fiscal_year=%s,
            payment_method=%s, bank_reference=%s, remarks=%s, status=%s
            WHERE id=%s''', [
            data.get('party_type'), data.get('party_id'), data.get('party_name'),
            data.get('invoice_id'), data.get('payment_number'), data.get('payment_date'),
            data.get('amount', 0), data.get('currency', 'INR'),
            data.get('sap_document_number'), data.get('sap_fiscal_year'),
            data.get('payment_method'), data.get('bank_reference'),
            data.get('remarks'), data.get('status', 'Pending'), row_id
        ])
    else:
        cur.execute('''INSERT INTO customer_incoming_payments
            (party_type, party_id, party_name, invoice_id,
             payment_number, payment_date, amount, currency,
             payment_method, bank_reference, remarks, status,
             created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id''', [
            data.get('party_type'), data.get('party_id'), data.get('party_name'),
            data.get('invoice_id'), data.get('payment_number'), data.get('payment_date'),
            data.get('amount', 0), data.get('currency', 'INR'),
            data.get('payment_method'), data.get('bank_reference'),
            data.get('remarks'), 'Pending', username, now
        ])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_incoming_payment(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM customer_incoming_payments WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# ===== GL JOURNAL VOUCHERS =====

def get_gl_jvs(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM gl_journal_vouchers')
    total = cur.fetchone()['cnt']
    cur.execute('SELECT * FROM gl_journal_vouchers ORDER BY id DESC LIMIT %s OFFSET %s',
                [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def save_gl_jv(data, username=None):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')
    now = datetime.now().strftime('%Y-%m-%d')
    if row_id:
        cur.execute('''UPDATE gl_journal_vouchers SET
            jv_number=%s, jv_date=%s, description=%s,
            total_debit=%s, total_credit=%s,
            sap_document_number=%s, sap_fiscal_year=%s, status=%s
            WHERE id=%s''', [
            data.get('jv_number'), data.get('jv_date'), data.get('description'),
            data.get('total_debit', 0), data.get('total_credit', 0),
            data.get('sap_document_number'), data.get('sap_fiscal_year'),
            data.get('status', 'Draft'), row_id
        ])
    else:
        cur.execute('''INSERT INTO gl_journal_vouchers
            (jv_number, jv_date, description, total_debit, total_credit,
             status, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id''', [
            data.get('jv_number'), data.get('jv_date'), data.get('description'),
            data.get('total_debit', 0), data.get('total_credit', 0),
            'Draft', username, now
        ])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_gl_jv(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM gl_jv_lines WHERE jv_id=%s', (row_id,))
    cur.execute('DELETE FROM gl_journal_vouchers WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

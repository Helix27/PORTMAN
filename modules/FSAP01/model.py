from database import get_db, get_cursor


def get_sap_invoice_logs(page=1, size=50):
    """Invoices with SAP posting data."""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM invoice_header')
    total = cur.fetchone()['cnt']
    cur.execute('''
        SELECT id, invoice_number, invoice_date, financial_year,
               customer_name, customer_type,
               total_amount, invoice_status,
               sap_document_number, sap_posting_date, sap_fiscal_year, sap_company_code,
               created_by, created_date, posted_by, posted_date
        FROM invoice_header
        ORDER BY id DESC LIMIT %s OFFSET %s
    ''', [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_sap_cn_logs(page=1, size=50):
    """Credit notes with SAP posting data."""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM credit_note_header')
    total = cur.fetchone()['cnt']
    cur.execute('''
        SELECT cn.id, cn.credit_note_number, cn.credit_note_date, cn.financial_year,
               cn.party_name, cn.total_amount, cn.credit_note_status,
               cn.sap_document_number, cn.sap_posting_date,
               i.invoice_number AS original_invoice_number,
               cn.created_by, cn.created_date
        FROM credit_note_header cn
        LEFT JOIN invoice_header i ON cn.original_invoice_id = i.id
        ORDER BY cn.id DESC LIMIT %s OFFSET %s
    ''', [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def get_gst_logs(page=1, size=50):
    """Invoices with GST IRN / e-invoice data."""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) as cnt FROM invoice_header')
    total = cur.fetchone()['cnt']
    cur.execute('''
        SELECT id, invoice_number, invoice_date, financial_year,
               customer_name, customer_type,
               total_amount, invoice_status,
               gst_irn, gst_ack_number, gst_ack_date,
               created_by, created_date
        FROM invoice_header
        ORDER BY id DESC LIMIT %s OFFSET %s
    ''', [size, (page - 1) * size])
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total

from flask import render_template, request, redirect, url_for, session, jsonify
from . import bp
from . import model
from database import get_user_permissions, get_db, get_cursor, get_module_config

@bp.route('/module/FIN01/')
def index():
    """Main FIN01 index - redirect to bills"""
    return redirect(url_for('FIN01.bills'))


@bp.route('/module/FIN01/invoices')
def legacy_invoices():
    """Legacy invoice list route; moved to FINV01"""
    return redirect(url_for('FINV01.invoices'))


@bp.route('/module/FIN01/invoice/generate')
def legacy_generate_invoice():
    """Legacy invoice generation route; moved to FINV01"""
    return redirect(url_for('FINV01.generate_invoice'))


@bp.route('/module/FIN01/invoice/print/<int:invoice_id>')
def legacy_print_invoice(invoice_id):
    """Legacy invoice print route; moved to FINV01"""
    return redirect(url_for('FINV01.print_invoice', invoice_id=invoice_id))


@bp.route('/module/FIN01/bills')
def bills():
    """List all bills"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    perms = get_user_permissions(session['user_id'], 'FIN01')
    page = int(request.args.get('page', 1))
    status_filter = request.args.get('status')
    data, total = model.get_bill_data(page, status_filter=status_filter)

    return render_template('bills.html',
                         data=data,
                         page=page,
                         last_page=(total + 19) // 20,
                         status_filter=status_filter,
                         perms=perms,
                         username=session.get('username'))


@bp.route('/module/FIN01/bill/<int:bill_id>')
def view_bill(bill_id):
    """View bill details"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    perms = get_user_permissions(session['user_id'], 'FIN01')

    # Get bill header
    bill = model.get_bill_by_id(bill_id)
    if not bill:
        return "Bill not found", 404

    # Get bill lines
    bill_lines = model.get_bill_lines(bill_id)

    return render_template('bill_view.html',
                         bill=bill,
                         bill_lines=bill_lines,
                         perms=perms,
                         username=session.get('username'))


@bp.route('/module/FIN01/bill/generate')
def generate_bill():
    """Generate bill from EU lines"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    perms = get_user_permissions(session['user_id'], 'FIN01')

    # Import other module models
    from modules.VCN01 import model as vcn_model
    from modules.MBC01 import model as mbc_model
    from modules.LUEU01 import model as eu_model
    from modules.VCUM01 import model as vcum_model

    # Get source options with dates for better identification
    conn = get_db()
    cur = get_cursor(conn)

    # VCN with anchorage_arrival from anchorage
    cur.execute('''
        SELECT h.id, h.vcn_doc_num, h.vessel_name, a.anchorage_arrival
        FROM vcn_header h
        LEFT JOIN vcn_anchorage a ON h.id = a.vcn_id
        ORDER BY h.id DESC
    ''')
    vcn_options = cur.fetchall()

    # MBC with doc_date
    cur.execute('''
        SELECT id, doc_num, mbc_name, doc_date
        FROM mbc_header
        ORDER BY id DESC
    ''')
    mbc_options = cur.fetchall()

    conn.close()

    # Convert to list of dicts for template
    vcn_options = [dict(r) for r in vcn_options]
    mbc_options = [dict(r) for r in mbc_options]

    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')

    return render_template('generate_bill.html',
                         vcn_options=vcn_options,
                         mbc_options=mbc_options,
                         current_date=current_date,
                         perms=perms,
                         username=session.get('username'))


@bp.route('/api/module/FIN01/bill/save', methods=['POST'])
def save_bill():
    """Save bill header"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    perms = get_user_permissions(session['user_id'], 'FIN01')
    if not perms['can_add'] and not perms['can_edit']:
        return jsonify({'success': False, 'error': 'No permission'})

    data = request.json

    # Extract lines from data before saving header (lines belong to bill_lines table, not bill_header)
    lines = data.pop('lines', [])

    data['created_by'] = session.get('username')
    data['created_date'] = __import__('datetime').datetime.now().strftime('%Y-%m-%d')

    # Set bill status based on approval config
    config = get_module_config('FIN01')
    user_id = session.get('user_id')
    is_approver = str(config.get('approver_id', '')) == str(user_id)
    is_admin = session.get('is_admin')

    if is_approver or is_admin:
        data['bill_status'] = 'Approved'
        data['approved_by'] = session.get('username')
        data['approved_date'] = data['created_date']
    elif config.get('approval_add'):
        data['bill_status'] = 'Pending Approval'
    else:
        data['bill_status'] = 'Draft'

    # Get source display name if not provided
    if not data.get('source_display') and data.get('source_type') and data.get('source_id'):
        conn = get_db()
        cur = get_cursor(conn)
        if data['source_type'] == 'VCN':
            cur.execute('SELECT vcn_doc_num FROM vcn_header WHERE id=%s', (data['source_id'],))
            row = cur.fetchone()
            data['source_display'] = row['vcn_doc_num'] if row else ''
        elif data['source_type'] == 'MBC':
            cur.execute('SELECT doc_num FROM mbc_header WHERE id=%s', (data['source_id'],))
            row = cur.fetchone()
            data['source_display'] = row['doc_num'] if row else ''
        conn.close()

    row_id, bill_number = model.save_bill_header(data)

    # Save bill lines and calculate totals
    subtotal = 0
    cgst_total = 0
    sgst_total = 0
    igst_total = 0

    for line in lines:
        line['bill_id'] = row_id
        model.save_bill_line(line)
        subtotal += line.get('line_amount', 0)
        cgst_total += line.get('cgst_amount', 0)
        sgst_total += line.get('sgst_amount', 0)
        igst_total += line.get('igst_amount', 0)

    # Update bill header with calculated totals
    total_amount = subtotal + cgst_total + sgst_total + igst_total
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''UPDATE bill_header
        SET subtotal=%s, cgst_amount=%s, sgst_amount=%s, igst_amount=%s, total_amount=%s
        WHERE id=%s''',
        [subtotal, cgst_total, sgst_total, igst_total, total_amount, row_id])
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'id': row_id, 'bill_number': bill_number})


@bp.route('/api/module/FIN01/bill/approve', methods=['POST'])
def approve_bill():
    """Approve a bill - only approver or admin"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    config = get_module_config('FIN01')
    user_id = session.get('user_id')
    is_approver = str(config.get('approver_id', '')) == str(user_id)
    is_admin = session.get('is_admin')

    if not is_approver and not is_admin:
        return jsonify({'success': False, 'error': 'Only approver or admin can approve bills'})

    bill_id = request.json.get('id')
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''UPDATE bill_header
        SET bill_status='Approved', approved_by=%s, approved_date=%s
        WHERE id=%s''',
        [session.get('username'), __import__('datetime').datetime.now().strftime('%Y-%m-%d'), bill_id])
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@bp.route('/api/module/FIN01/bill/submit', methods=['POST'])
def submit_bill():
    """Submit bill for approval"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    bill_id = request.json.get('id')
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''UPDATE bill_header
        SET bill_status='Pending Approval'
        WHERE id=%s''', [bill_id])
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@bp.route('/api/module/FIN01/bill/reject', methods=['POST'])
def reject_bill():
    """Reject a bill - only approver or admin"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    config = get_module_config('FIN01')
    user_id = session.get('user_id')
    is_approver = str(config.get('approver_id', '')) == str(user_id)
    is_admin = session.get('is_admin')

    if not is_approver and not is_admin:
        return jsonify({'success': False, 'error': 'Only approver or admin can reject bills'})

    bill_id = request.json.get('id')
    reason = request.json.get('reason', '')
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''UPDATE bill_header
        SET bill_status='Rejected', rejection_reason=%s
        WHERE id=%s''', [reason, bill_id])
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@bp.route('/api/module/FIN01/bill-lines/<int:bill_id>')
def get_bill_lines_api(bill_id):
    """Get bill lines for a specific bill (used in invoice generation page)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    lines = model.get_bill_lines(bill_id)
    return jsonify({'lines': lines})


@bp.route('/api/module/FIN01/eu-lines/<source_type>/<int:source_id>')
def get_lueu_lines(source_type, source_id):
    """Get all EU lines for a specific source (both billed and unbilled)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT el.*, st.service_name
        FROM lueu_lines el
        LEFT JOIN finance_service_types st ON el.service_type_id = st.id
        WHERE el.source_type = %s AND el.source_id = %s
        ORDER BY el.is_billed ASC, el.id
    ''', [source_type, source_id])
    rows = cur.fetchall()
    conn.close()

    return jsonify({'data': [dict(r) for r in rows]})


@bp.route('/api/module/FIN01/service-types')
def get_service_types():
    """Get all active service types with GST rate details"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT s.id, s.service_name, s.service_code, s.sac_code, s.uom, s.gl_code,
               s.gst_rate_id,
               COALESCE(g.cgst_rate, 0) as cgst_rate,
               COALESCE(g.sgst_rate, 0) as sgst_rate,
               COALESCE(g.igst_rate, 0) as igst_rate,
               g.rate_name as gst_rate_name
        FROM finance_service_types s
        LEFT JOIN gst_rates g ON s.gst_rate_id = g.id
        WHERE s.is_active = 1
        ORDER BY s.service_name
    ''')
    rows = cur.fetchall()
    conn.close()

    return jsonify({'data': [dict(r) for r in rows]})


@bp.route('/api/module/FIN01/port-config')
def get_port_config():
    """Get port GST config (state code, GSTIN) from FIN01 module config"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    config = get_module_config('FIN01')
    return jsonify({
        'port_gst_state_code': config.get('port_gst_state_code', ''),
        'port_gstin': config.get('port_gstin', ''),
        'seller_gstin': config.get('seller_gstin', ''),
        'seller_legal_name': config.get('seller_legal_name', ''),
        'seller_address': config.get('seller_address', ''),
        'seller_location': config.get('seller_location', ''),
        'seller_pincode': config.get('seller_pincode', ''),
        'seller_phone': config.get('seller_phone', ''),
        'seller_email': config.get('seller_email', '')
    })


@bp.route('/api/module/FIN01/customer-agreements/<int:customer_id>')
def get_customer_agreements(customer_id):
    """Get all valid active approved agreements for a customer"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')

    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT id, agreement_code, agreement_name, currency_code, valid_from, valid_to
        FROM customer_agreements
        WHERE customer_id = %s
        AND is_active = 1
        AND agreement_status = 'Approved'
        AND valid_from <= %s
        AND (valid_to IS NULL OR valid_to >= %s)
        ORDER BY valid_from DESC
    ''', [customer_id, today, today])
    rows = cur.fetchall()
    conn.close()

    return jsonify({'data': [dict(r) for r in rows]})


@bp.route('/api/module/FIN01/agreement-rate/<int:customer_id>/<int:service_type_id>')
def get_agreement_rate(customer_id, service_type_id):
    """Get rate from active customer agreement. Optionally filter by agreement_id."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    from datetime import datetime

    conn = get_db()
    cur = get_cursor(conn)
    today = datetime.now().strftime('%Y-%m-%d')
    agreement_id = request.args.get('agreement_id')

    if agreement_id:
        # Fetch rate from a specific agreement
        cur.execute('''
            SELECT cal.rate, cal.uom, cal.currency_code,
                   ca.agreement_code, ca.agreement_name
            FROM customer_agreement_lines cal
            INNER JOIN customer_agreements ca ON cal.agreement_id = ca.id
            WHERE ca.id = %s
            AND cal.service_type_id = %s
        ''', [agreement_id, service_type_id])
    else:
        # Fall back to latest valid agreement
        cur.execute('''
            SELECT cal.rate, cal.uom, cal.currency_code,
                   ca.agreement_code, ca.agreement_name
            FROM customer_agreement_lines cal
            INNER JOIN customer_agreements ca ON cal.agreement_id = ca.id
            WHERE ca.customer_id = %s
            AND cal.service_type_id = %s
            AND ca.is_active = 1
            AND ca.agreement_status = 'Approved'
            AND ca.valid_from <= %s
            AND (ca.valid_to IS NULL OR ca.valid_to >= %s)
            ORDER BY ca.valid_from DESC
            LIMIT 1
        ''', [customer_id, service_type_id, today, today])
    row = cur.fetchone()
    conn.close()

    if row:
        return jsonify({'success': True, 'data': dict(row)})
    else:
        return jsonify({'success': False, 'error': 'No valid agreement found'})


@bp.route('/api/module/FIN01/service-records/<source_type>/<int:source_id>')
def get_service_records(source_type, source_id):
    """Get approved, unbilled service records for a source"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    from modules.SRV01 import model as srv_model
    records = srv_model.get_unbilled_records_for_source(source_type, source_id)

    # For each record, also get the field values for display
    for rec in records:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''
            SELECT sfd.field_label, srv.field_value
            FROM service_record_values srv
            JOIN service_field_definitions sfd ON srv.field_definition_id = sfd.id
            WHERE srv.service_record_id = %s
            ORDER BY sfd.display_order, sfd.id
        ''', [rec['id']])
        rec['field_values'] = [dict(r) for r in cur.fetchall()]
        conn.close()

    return jsonify({'data': records})


@bp.route('/api/module/FIN01/customers/<path:customer_type>')
def get_customers_for_billing(customer_type):
    """Get customers with full details for billing"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    # Determine which table to query
    if customer_type == 'Customer':
        table = 'vessel_customers'
    elif customer_type == 'Agent':
        table = 'vessel_agents'
    else:
        return jsonify({'error': 'Invalid customer type'}), 400

    conn = get_db()
    cur = get_cursor(conn)
    cur.execute(f'''
        SELECT id, name, gstin, gst_state_code, gl_code, pan,
               billing_address, city, pincode, contact_phone, contact_email
        FROM {table}
        ORDER BY name
    ''')
    rows = cur.fetchall()
    conn.close()

    return jsonify({'data': [dict(r) for r in rows]})

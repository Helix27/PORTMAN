from flask import render_template, request, redirect, url_for, session, jsonify
from . import bp
from modules.FIN01 import model  # reuse FIN01 model for invoice functions
from database import get_user_permissions, get_db, get_cursor, get_module_config
import sap_builder
import sap_client
import einvoice_builder
import gsp_client

MODULE_CODE = 'FINV01'


def get_perms():
    if session.get('is_admin'):
        return {'can_read': 1, 'can_add': 1, 'can_edit': 1, 'can_delete': 1}
    # Fall back to FIN01 permissions if FINV01 not set up yet
    perms = get_user_permissions(session.get('user_id'), MODULE_CODE)
    if not perms.get('can_read'):
        perms = get_user_permissions(session.get('user_id'), 'FIN01')
    return perms


# ===== Invoice List =====

@bp.route('/module/FINV01/')
def index():
    return redirect(url_for('FINV01.invoices'))


@bp.route('/module/FINV01/invoices')
def invoices():
    """List all invoices"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    perms = get_perms()
    page = int(request.args.get('page', 1))
    status_filter = request.args.get('status')
    data, total = model.get_invoice_data(page, status_filter=status_filter)

    return render_template('invoices.html',
                         data=data,
                         page=page,
                         last_page=(total + 19) // 20,
                         status_filter=status_filter,
                         perms=perms,
                         username=session.get('username'),
                         module_code='FINV01')


# ===== Generate Invoice from Bills =====

@bp.route('/module/FINV01/generate')
def generate_invoice():
    """Generate invoice from approved bills"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    perms = get_perms()

    # Get all approved bills not yet invoiced
    approved_bills, _ = model.get_bill_data(page=1, size=1000, status_filter='Approved')

    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')

    return render_template('generate_invoice.html',
                         approved_bills=approved_bills,
                         current_date=current_date,
                         perms=perms,
                         username=session.get('username'),
                         module_code='FINV01')


@bp.route('/api/module/FINV01/invoice/create', methods=['POST'])
def create_invoice():
    """Create invoice from selected bills"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})

    perms = get_perms()
    if not perms.get('can_add'):
        return jsonify({'success': False, 'error': 'No permission'})

    data = request.json
    bill_ids = data.get('bill_ids', [])

    invoice_data = {
        'invoice_date': data.get('invoice_date'),
        'invoice_series': data.get('invoice_series', 'INV'),
        'customer_type': data.get('customer_type'),
        'customer_id': data.get('customer_id'),
        'customer_name': data.get('customer_name'),
        'customer_gstin': data.get('customer_gstin'),
        'customer_gst_state_code': data.get('customer_gst_state_code'),
        'customer_gl_code': data.get('customer_gl_code'),
        'customer_pan': data.get('customer_pan'),
        'billing_address': data.get('billing_address'),
        'customer_city': data.get('customer_city'),
        'customer_pincode': data.get('customer_pincode'),
        'customer_phone': data.get('customer_phone'),
        'customer_email': data.get('customer_email'),
        'currency_code': data.get('currency_code', 'INR'),
        'exchange_rate': data.get('exchange_rate', 1.0),
        'subtotal': data.get('subtotal'),
        'cgst_amount': data.get('cgst_amount'),
        'sgst_amount': data.get('sgst_amount'),
        'igst_amount': data.get('igst_amount'),
        'tds_amount': data.get('tds_amount', 0),
        'round_off': data.get('round_off', 0),
        'total_amount': data.get('total_amount'),
        'amount_in_words': data.get('amount_in_words'),
        'payment_terms': data.get('payment_terms'),
        'due_date': data.get('due_date'),
        'created_by': session.get('username'),
        'created_date': __import__('datetime').datetime.now().strftime('%Y-%m-%d'),
        'remarks': data.get('remarks')
    }

    invoice_id, invoice_number = model.create_invoice_from_bills(bill_ids, invoice_data)
    return jsonify({'success': True, 'id': invoice_id, 'invoice_number': invoice_number})


# ===== Bill lines (for generate invoice page) =====

@bp.route('/api/module/FINV01/bill-lines/<int:bill_id>')
def get_bill_lines_api(bill_id):
    """Get bill lines for expand in invoice generation page"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    lines = model.get_bill_lines(bill_id)
    return jsonify({'lines': lines})


# ===== Print Invoice =====

@bp.route('/module/FINV01/invoice/print/<int:invoice_id>')
def print_invoice(invoice_id):
    """Print invoice"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403

    invoice = model.get_invoice_by_id(invoice_id)
    if not invoice:
        return "Invoice not found", 404

    invoice_lines = model.get_invoice_lines(invoice_id)
    sac_summary = model.get_invoice_sac_summary(invoice_id)

    from datetime import datetime
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return render_template('invoice_print.html',
                         invoice=invoice,
                         invoice_lines=invoice_lines,
                         sac_summary=sac_summary,
                         current_datetime=current_datetime)


# ===== GSTR-1 B2B Export =====

@bp.route('/api/module/FINV01/export/gstr1-b2b', methods=['POST'])
def export_gstr1_b2b():
    """Export selected invoices as GSTR-1 B2B JSON"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    from datetime import datetime
    data = request.json
    invoice_ids = data.get('invoice_ids', [])
    supplier_gstin = data.get('supplier_gstin', '')
    filing_period = data.get('filing_period', '')

    if not invoice_ids:
        return jsonify({'error': 'No invoices selected'}), 400

    b2b = {}
    for inv_id in invoice_ids:
        invoice = model.get_invoice_by_id(inv_id)
        if not invoice:
            continue
        lines = model.get_invoice_lines(inv_id)
        ctin = invoice.get('customer_gstin', '')
        if not ctin:
            continue

        if ctin not in b2b:
            b2b[ctin] = {'ctin': ctin, 'inv': []}

        rate_groups = {}
        for line in lines:
            cgst = float(line.get('cgst_rate') or 0)
            sgst = float(line.get('sgst_rate') or 0)
            igst = float(line.get('igst_rate') or 0)
            rt = igst if igst > 0 else (cgst + sgst)
            if rt not in rate_groups:
                rate_groups[rt] = {'txval': 0, 'camt': 0, 'samt': 0, 'iamt': 0, 'csamt': 0}
            rate_groups[rt]['txval'] += float(line.get('line_amount') or 0)
            rate_groups[rt]['camt'] += float(line.get('cgst_amount') or 0)
            rate_groups[rt]['samt'] += float(line.get('sgst_amount') or 0)
            rate_groups[rt]['iamt'] += float(line.get('igst_amount') or 0)

        itms = [{'num': i+1, 'itm_det': {
            'rt': round(rt, 2), 'txval': round(v['txval'], 2),
            'camt': round(v['camt'], 2), 'samt': round(v['samt'], 2),
            'iamt': round(v['iamt'], 2), 'csamt': round(v['csamt'], 2)
        }} for i, (rt, v) in enumerate(rate_groups.items())]

        inv_date = invoice.get('invoice_date')
        if hasattr(inv_date, 'strftime'):
            inv_date = inv_date.strftime('%d-%m-%Y')
        else:
            inv_date = str(inv_date or '')
            if '-' in inv_date:
                parts = inv_date.split('-')
                if len(parts) == 3 and len(parts[0]) == 4:
                    inv_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

        b2b[ctin]['inv'].append({
            'inum': invoice.get('invoice_number', ''),
            'idt': inv_date,
            'val': round(float(invoice.get('total_amount') or 0), 2),
            'pos': invoice.get('customer_gst_state_code', ''),
            'rchrg': 'N', 'inv_typ': 'R', 'itms': itms
        })

    return jsonify({'gstin': supplier_gstin, 'fp': filing_period, 'b2b': list(b2b.values())})


# ===== e-Invoice Export =====

@bp.route('/api/module/FINV01/export/einvoice', methods=['POST'])
def export_einvoice():
    """Export invoices as e-Invoice JSON"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    data = request.json
    invoice_ids = data.get('invoice_ids', [])

    if not invoice_ids:
        return jsonify({'error': 'No invoices selected'}), 400

    einvoices = []
    for inv_id in invoice_ids:
        invoice = model.get_invoice_by_id(inv_id)
        if not invoice:
            continue
        inv_lines = model.get_invoice_lines(inv_id)
        einvoice_json = einvoice_builder.build_einvoice_from_invoice(invoice, inv_lines)
        einvoices.append(einvoice_json)

    return jsonify({'einvoices': einvoices})


# ===== SAP Integration =====

@bp.route('/api/module/FINV01/invoice/post-sap', methods=['POST'])
def post_invoice_sap():
    """Post an invoice to SAP via DynaportInvoice REST API"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    perms = get_perms()
    if not perms.get('can_edit'):
        return jsonify({'success': False, 'error': 'No permission'}), 403

    invoice_id = request.json.get('invoice_id')
    invoice = model.get_invoice_by_id(invoice_id)
    if not invoice:
        return jsonify({'success': False, 'error': 'Invoice not found'}), 404

    if invoice.get('sap_document_number'):
        return jsonify({'success': False, 'error': 'Invoice already posted to SAP'})

    invoice_lines = model.get_invoice_lines(invoice_id)
    payload = sap_builder.build_invoice_payload(invoice, invoice_lines)
    result = sap_client.post_invoice_to_sap(
        payload, 'Invoice', invoice_id,
        invoice['invoice_number'], session.get('username')
    )

    if result['ok']:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''UPDATE invoice_header
            SET sap_document_number=%s, invoice_status='Posted'
            WHERE id=%s''',
            [result['sap_document_number'], invoice_id])
        conn.commit()
        conn.close()

    return jsonify({
        'success': result['ok'],
        'sap_document_number': result.get('sap_document_number'),
        'message': result['message'],
        'log_id': result['log_id']
    })


# ===== GST IRN Integration =====

@bp.route('/api/module/FINV01/invoice/generate-irn', methods=['POST'])
def generate_irn():
    """Generate IRN for an invoice via IRP e-invoice API"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    perms = get_perms()
    if not perms.get('can_edit'):
        return jsonify({'success': False, 'error': 'No permission'}), 403

    invoice_id = request.json.get('invoice_id')
    invoice = model.get_invoice_by_id(invoice_id)
    if not invoice:
        return jsonify({'success': False, 'error': 'Invoice not found'}), 404

    if invoice.get('gst_irn'):
        return jsonify({'success': False, 'error': 'IRN already generated for this invoice'})

    invoice_lines = model.get_invoice_lines(invoice_id)
    einvoice_json = einvoice_builder.build_einvoice_from_invoice(invoice, invoice_lines)
    result = gsp_client.generate_irn(
        einvoice_json, 'Invoice', invoice_id,
        invoice['invoice_number'], session.get('username')
    )

    if result['ok']:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''UPDATE invoice_header
            SET gst_irn=%s, gst_ack_number=%s
            WHERE id=%s''',
            [result['irn'], result['ack_number'], invoice_id])
        conn.commit()
        conn.close()

    return jsonify({
        'success': result['ok'],
        'irn': result.get('irn'),
        'ack_number': result.get('ack_number'),
        'message': result['message'],
        'log_id': result['log_id']
    })


@bp.route('/api/module/FINV01/invoice/cancel-irn', methods=['POST'])
def cancel_irn():
    """Cancel an IRN for an invoice"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    perms = get_perms()
    if not perms.get('can_edit'):
        return jsonify({'success': False, 'error': 'No permission'}), 403

    data = request.json
    invoice_id = data.get('invoice_id')
    invoice = model.get_invoice_by_id(invoice_id)
    if not invoice:
        return jsonify({'success': False, 'error': 'Invoice not found'}), 404

    if not invoice.get('gst_irn'):
        return jsonify({'success': False, 'error': 'No IRN to cancel'})

    result = gsp_client.cancel_irn(
        invoice['gst_irn'], data.get('reason_code', 1),
        data.get('remark', 'Cancelled'),
        'Invoice', invoice_id, invoice['invoice_number'],
        session.get('username')
    )

    if result['ok']:
        conn = get_db()
        cur = get_cursor(conn)
        cur.execute('''UPDATE invoice_header
            SET gst_irn=NULL, gst_ack_number=NULL, gst_ack_date=NULL, gst_qr_code=NULL
            WHERE id=%s''', [invoice_id])
        conn.commit()
        conn.close()

    return jsonify({
        'success': result['ok'],
        'message': result['message'],
        'log_id': result['log_id']
    })


# ===== Port Config (shared) =====

@bp.route('/api/module/FINV01/port-config')
def get_port_config():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    config = get_module_config('FIN01')
    return jsonify({
        'port_gst_state_code': config.get('port_gst_state_code', ''),
        'port_gstin': config.get('port_gstin', ''),
        'seller_gstin': config.get('seller_gstin', ''),
        'seller_legal_name': config.get('seller_legal_name', ''),
    })

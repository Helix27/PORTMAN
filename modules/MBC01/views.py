import json as _json
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions, get_module_config

bp = Blueprint('MBC01', __name__, template_folder='.')
MODULE_CODE = 'MBC01'
MODULE_INFO = {'code': 'MBC01', 'name': 'MBC Operation'}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_perms():
    if session.get('is_admin'):
        return {'can_read': 1, 'can_add': 1, 'can_edit': 1, 'can_delete': 1}
    return get_user_permissions(session.get('user_id'), MODULE_CODE)

@bp.route('/module/MBC01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('mbc01.html', permissions=perms)

@bp.route('/api/module/MBC01/data')
@login_required
def get_data():
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
    except (ValueError, TypeError):
        page, size = 1, 20
    try:
        filters = _json.loads(request.args.get('filters', '[]'))
    except _json.JSONDecodeError:
        filters = []
    rows, total = model.get_data(page, size, filters)
    return jsonify({'data': rows, 'last_page': (total + size - 1) // size, 'total': total})

@bp.route('/api/module/MBC01/save', methods=['POST'])
@login_required
def save():
    perms = get_perms()
    data = request.json
    is_new = not data.get('id')
    if is_new and not perms.get('can_add'):
        return jsonify({'error': 'No permission to add'}), 403
    if not is_new and not perms.get('can_edit'):
        return jsonify({'error': 'No permission to edit'}), 403

    config = get_module_config('MBC01')
    is_approver = str(config.get('approver_id', '')) == str(session.get('user_id')) or session.get('is_admin')

    if not is_new:
        current_status = model.get_doc_status(data['id'])
        if current_status == 'Approved':
            if not is_approver:
                return jsonify({'error': 'Cannot edit an approved record'}), 403
            data['doc_status'] = 'Approved'
        else:
            data['doc_status'] = 'Draft'
    else:
        data['doc_status'] = 'Draft'

    row_id, doc_num = model.save_header(data)
    return jsonify({'id': row_id, 'doc_num': doc_num, 'doc_status': data.get('doc_status', 'Draft')})


@bp.route('/api/module/MBC01/approval_check/<int:record_id>')
@login_required
def approval_check(record_id):
    return jsonify(model.get_approval_eligibility(record_id))


@bp.route('/api/module/MBC01/approve', methods=['POST'])
@login_required
def approve():
    config = get_module_config('MBC01')
    is_approver = str(config.get('approver_id', '')) == str(session.get('user_id')) or session.get('is_admin')
    if not is_approver:
        return jsonify({'error': 'No permission to approve'}), 403
    record_id = request.json.get('id')
    if not record_id:
        return jsonify({'error': 'Missing id'}), 400
    eligibility = model.get_approval_eligibility(record_id)
    if not eligibility['eligible']:
        return jsonify({'error': 'Record not eligible for approval', 'missing': eligibility['missing']}), 400
    model.approve_record(record_id, session.get('username'))
    return jsonify({'doc_status': 'Approved'})


@bp.route('/api/module/MBC01/send_back', methods=['POST'])
@login_required
def send_back():
    config = get_module_config('MBC01')
    is_approver = str(config.get('approver_id', '')) == str(session.get('user_id')) or session.get('is_admin')
    if not is_approver:
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    record_id = data.get('id')
    comment = (data.get('comment') or '').strip()
    if not record_id:
        return jsonify({'error': 'Missing id'}), 400
    if not comment:
        return jsonify({'error': 'A reason is required when sending back to Draft'}), 400
    model.send_back_to_draft(record_id, comment, session.get('username'))
    return jsonify({'doc_status': 'Draft'})


@bp.route('/api/module/MBC01/approval-log/<int:record_id>')
@login_required
def approval_log(record_id):
    return jsonify(model.get_approval_log(record_id))


@bp.route('/api/module/MBC01/delete', methods=['POST'])
@login_required
def delete():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_header(request.json['id'])
    return jsonify({'success': True})

# Load Port Lines sub-table endpoints
@bp.route('/api/module/MBC01/load_port/<int:mbc_id>')
@login_required
def get_load_port_lines(mbc_id):
    return jsonify(model.get_load_port_lines(mbc_id))

@bp.route('/api/module/MBC01/load_port/save', methods=['POST'])
@login_required
def save_load_port_line():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id = model.save_load_port_line(data)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/MBC01/load_port/delete', methods=['POST'])
@login_required
def delete_load_port_line():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_load_port_line(request.json['id'])
    return jsonify({'success': True})

# Discharge Port Lines sub-table endpoints
@bp.route('/api/module/MBC01/discharge_port/<int:mbc_id>')
@login_required
def get_discharge_port_lines(mbc_id):
    return jsonify(model.get_discharge_port_lines(mbc_id))

@bp.route('/api/module/MBC01/discharge_port/save', methods=['POST'])
@login_required
def save_discharge_port_line():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id = model.save_discharge_port_line(data)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/MBC01/discharge_port/delete', methods=['POST'])
@login_required
def delete_discharge_port_line():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_discharge_port_line(request.json['id'])
    return jsonify({'success': True})

# Cleaning Details sub-table endpoints
@bp.route('/api/module/MBC01/cleaning/<int:mbc_id>')
@login_required
def get_cleaning_details(mbc_id):
    return jsonify(model.get_cleaning_details(mbc_id))

@bp.route('/api/module/MBC01/cleaning/save', methods=['POST'])
@login_required
def save_cleaning_detail():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id = model.save_cleaning_detail(data)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/MBC01/cleaning/delete', methods=['POST'])
@login_required
def delete_cleaning_detail():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_cleaning_detail(request.json['id'])
    return jsonify({'success': True})

# Export Load Port Lines sub-table endpoints
@bp.route('/api/module/MBC01/export_load_port/<int:mbc_id>')
@login_required
def get_export_load_port_lines(mbc_id):
    return jsonify(model.get_export_load_port_lines(mbc_id))

@bp.route('/api/module/MBC01/export_load_port/save', methods=['POST'])
@login_required
def save_export_load_port_line():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id = model.save_export_load_port_line(data)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/MBC01/export_load_port/delete', methods=['POST'])
@login_required
def delete_export_load_port_line():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_export_load_port_line(request.json['id'])
    return jsonify({'success': True})

# Customer Details sub-table endpoints
@bp.route('/api/module/MBC01/customer_details/<int:mbc_id>')
@login_required
def get_customer_details(mbc_id):
    return jsonify(model.get_customer_details(mbc_id))

@bp.route('/api/module/MBC01/customer_details/save', methods=['POST'])
@login_required
def save_customer_detail():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id = model.save_customer_detail(data)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/MBC01/customer_details/delete', methods=['POST'])
@login_required
def delete_customer_detail():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_customer_detail(request.json['id'])
    return jsonify({'success': True})

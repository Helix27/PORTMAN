from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions

bp = Blueprint('LDUD01', __name__, template_folder='.')
MODULE_CODE = 'LDUD01'

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

@bp.route('/module/LDUD01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('ldud01.html', permissions=perms)

@bp.route('/api/module/LDUD01/data')
@login_required
def get_data():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    rows, total = model.get_data(page, size)
    return jsonify({'data': rows, 'last_page': (total + size - 1) // size, 'total': total})

@bp.route('/api/module/LDUD01/vcn_list')
@login_required
def get_vcn_list():
    return jsonify(model.get_vcn_list())

@bp.route('/api/module/LDUD01/vcn_list/export')
@login_required
def get_export_vcn_list():
    return jsonify(model.get_vcn_list())

@bp.route('/api/module/LDUD01/save', methods=['POST'])
@login_required
def save():
    perms = get_perms()
    data = request.json
    is_new = not data.get('id')
    if is_new and not perms.get('can_add'):
        return jsonify({'error': 'No permission to add'}), 403
    if not is_new and not perms.get('can_edit'):
        return jsonify({'error': 'No permission to edit'}), 403
    row_id, doc_num = model.save_header(data)
    return jsonify({'id': row_id, 'doc_num': doc_num, 'doc_status': data.get('doc_status', 'Pending')})

@bp.route('/api/module/LDUD01/delete', methods=['POST'])
@login_required
def delete():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_header(request.json['id'])
    return jsonify({'success': True})

# Delays sub-table endpoints
@bp.route('/api/module/LDUD01/delays/<int:ldud_id>')
@login_required
def get_delays(ldud_id):
    return jsonify(model.get_delays(ldud_id))

@bp.route('/api/module/LDUD01/delays/save', methods=['POST'])
@login_required
def save_delay():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id, total_mins, total_hrs = model.save_delay(data)
    return jsonify({'id': row_id, 'success': True, 'total_time_mins': total_mins, 'total_time_hrs': total_hrs})

@bp.route('/api/module/LDUD01/delays/delete', methods=['POST'])
@login_required
def delete_delay():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_delay(request.json['id'])
    return jsonify({'success': True})

# Barge Lines sub-table endpoints
@bp.route('/api/module/LDUD01/barge_lines/<int:ldud_id>')
@login_required
def get_barge_lines(ldud_id):
    return jsonify(model.get_barge_lines(ldud_id))

@bp.route('/api/module/LDUD01/barge_lines/save', methods=['POST'])
@login_required
def save_barge_line():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    row_id, trip_number = model.save_barge_line(data)
    return jsonify({'id': row_id, 'success': True, 'trip_number': trip_number})

@bp.route('/api/module/LDUD01/barge_lines/delete', methods=['POST'])
@login_required
def delete_barge_line():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_barge_line(request.json['id'])
    return jsonify({'success': True})

# Anchorage Recording sub-table endpoints
@bp.route('/api/module/LDUD01/anchorage/<int:ldud_id>')
@login_required
def get_anchorage(ldud_id):
    return jsonify(model.get_anchorage(ldud_id))

@bp.route('/api/module/LDUD01/anchorage/save', methods=['POST'])
@login_required
def save_anchorage():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_anchorage(request.json)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/LDUD01/anchorage/delete', methods=['POST'])
@login_required
def delete_anchorage():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_anchorage(request.json['id'])
    return jsonify({'success': True})

# Vessel Operations sub-table endpoints
@bp.route('/api/module/LDUD01/vessel_ops/<int:ldud_id>')
@login_required
def get_vessel_operations(ldud_id):
    return jsonify(model.get_vessel_operations(ldud_id))

@bp.route('/api/module/LDUD01/vessel_ops/save', methods=['POST'])
@login_required
def save_vessel_operation():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_vessel_operation(request.json)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/LDUD01/vessel_ops/delete', methods=['POST'])
@login_required
def delete_vessel_operation():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_vessel_operation(request.json['id'])
    return jsonify({'success': True})

# Barge Cleaning Lines sub-table endpoints
@bp.route('/api/module/LDUD01/barge_cleaning/<int:ldud_id>')
@login_required
def get_barge_cleaning(ldud_id):
    return jsonify(model.get_barge_cleaning(ldud_id))

@bp.route('/api/module/LDUD01/barge_cleaning/save', methods=['POST'])
@login_required
def save_barge_cleaning():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_barge_cleaning(request.json)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/LDUD01/barge_cleaning/delete', methods=['POST'])
@login_required
def delete_barge_cleaning():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_barge_cleaning(request.json['id'])
    return jsonify({'success': True})

# Hold Completion sub-table endpoints
@bp.route('/api/module/LDUD01/hold_completion/<int:ldud_id>')
@login_required
def get_hold_completion(ldud_id):
    return jsonify(model.get_hold_completion(ldud_id))

@bp.route('/api/module/LDUD01/hold_completion/save', methods=['POST'])
@login_required
def save_hold_completion():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_hold_completion(request.json)
    return jsonify({'id': row_id, 'success': True})

@bp.route('/api/module/LDUD01/hold_completion/delete', methods=['POST'])
@login_required
def delete_hold_completion():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_hold_completion(request.json['id'])
    return jsonify({'success': True})

# Hold Cargo Config endpoints
@bp.route('/api/module/LDUD01/hold_cargo/<int:ldud_id>')
@login_required
def get_hold_cargo(ldud_id):
    return jsonify(model.get_hold_cargo(ldud_id))

@bp.route('/api/module/LDUD01/hold_cargo/save', methods=['POST'])
@login_required
def save_hold_cargo():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    data = request.json
    model.save_hold_cargo(data['ldud_id'], data['hold_name'], data.get('cargo_name', ''))
    return jsonify({'success': True})

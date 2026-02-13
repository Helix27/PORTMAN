from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions, get_module_config

bp = Blueprint('VCN01', __name__, template_folder='.')
MODULE_CODE = 'VCN01'

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

@bp.route('/module/VCN01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('vcn01.html', permissions=perms)

@bp.route('/api/module/VCN01/data')
@login_required
def get_data():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    data, total = model.get_data(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})

@bp.route('/api/module/VCN01/vessels')
@login_required
def get_vessels():
    return jsonify(model.get_vessels())

@bp.route('/api/module/VCN01/save', methods=['POST'])
@login_required
def save():
    perms = get_perms()
    data = request.json
    is_new = not data.get('id')

    if is_new and not perms.get('can_add'):
        return jsonify({'error': 'No permission to add'}), 403
    if not is_new and not perms.get('can_edit'):
        return jsonify({'error': 'No permission to edit'}), 403

    config = get_module_config('VCN01')
    user_id = session.get('user_id')
    is_approver = str(config.get('approver_id')) == str(user_id)

    if is_approver:
        pass
    else:
        if is_new:
            data['doc_status'] = 'Pending'
        elif config.get('approval_edit'):
            data['doc_status'] = 'Pending'

    row_id, doc_num = model.save_header(data)
    return jsonify({'success': True, 'id': row_id, 'vcn_doc_num': doc_num, 'doc_status': data.get('doc_status')})

@bp.route('/api/module/VCN01/delete', methods=['POST'])
@login_required
def delete():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_header(request.json.get('id'))
    return jsonify({'success': True})

# Nomination endpoints
@bp.route('/api/module/VCN01/nominations/<int:vcn_id>')
@login_required
def get_nominations(vcn_id):
    return jsonify(model.get_nominations(vcn_id))

@bp.route('/api/module/VCN01/nominations/save', methods=['POST'])
@login_required
def save_nomination():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_nomination(request.json)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VCN01/nominations/delete', methods=['POST'])
@login_required
def delete_nomination():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_nomination(request.json.get('id'))
    return jsonify({'success': True})

# Anchorage endpoints
@bp.route('/api/module/VCN01/anchorage/<int:vcn_id>')
@login_required
def get_anchorage(vcn_id):
    return jsonify(model.get_anchorage(vcn_id))

@bp.route('/api/module/VCN01/anchorage/save', methods=['POST'])
@login_required
def save_anchorage():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_anchorage(request.json)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VCN01/anchorage/delete', methods=['POST'])
@login_required
def delete_anchorage():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_anchorage(request.json.get('id'))
    return jsonify({'success': True})

# Delays endpoints
@bp.route('/api/module/VCN01/delays/<int:vcn_id>')
@login_required
def get_delays(vcn_id):
    return jsonify(model.get_delays(vcn_id))

@bp.route('/api/module/VCN01/delays/save', methods=['POST'])
@login_required
def save_delay():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_delay(request.json)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VCN01/delays/delete', methods=['POST'])
@login_required
def delete_delay():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_delay(request.json.get('id'))
    return jsonify({'success': True})

# Cargo Declaration endpoints
@bp.route('/api/module/VCN01/cargo/<int:vcn_id>')
@login_required
def get_cargo(vcn_id):
    return jsonify(model.get_cargo_declarations(vcn_id))

@bp.route('/api/module/VCN01/cargo/save', methods=['POST'])
@login_required
def save_cargo():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_cargo_declaration(request.json)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VCN01/cargo/delete', methods=['POST'])
@login_required
def delete_cargo():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_cargo_declaration(request.json.get('id'))
    return jsonify({'success': True})

# Get cargo names for a specific VCN (for stowage plan dropdown)
@bp.route('/api/module/VCN01/cargo_names/<int:vcn_id>')
@login_required
def get_cargo_names(vcn_id):
    return jsonify(model.get_cargo_names_for_vcn(vcn_id))

# IGM endpoints
@bp.route('/api/module/VCN01/igm/<int:vcn_id>')
@login_required
def get_igm(vcn_id):
    return jsonify(model.get_igm(vcn_id))

@bp.route('/api/module/VCN01/igm/save', methods=['POST'])
@login_required
def save_igm():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id, igm_number = model.save_igm(request.json)
    return jsonify({'success': True, 'id': row_id, 'igm_number': igm_number})

@bp.route('/api/module/VCN01/igm/delete', methods=['POST'])
@login_required
def delete_igm():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_igm(request.json.get('id'))
    return jsonify({'success': True})

@bp.route('/api/module/VCN01/igm/total/<int:vcn_id>')
@login_required
def get_igm_total(vcn_id):
    return jsonify({'total': model.get_igm_total_quantity(vcn_id)})

# Stowage Plan endpoints
@bp.route('/api/module/VCN01/stowage/<int:vcn_id>')
@login_required
def get_stowage(vcn_id):
    return jsonify(model.get_stowage_plan(vcn_id))

@bp.route('/api/module/VCN01/stowage/save', methods=['POST'])
@login_required
def save_stowage():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id, error = model.save_stowage_plan(request.json)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VCN01/stowage/delete', methods=['POST'])
@login_required
def delete_stowage():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_stowage_plan(request.json.get('id'))
    return jsonify({'success': True})

@bp.route('/api/module/VCN01/stowage/total/<int:vcn_id>')
@login_required
def get_stowage_total(vcn_id):
    return jsonify({
        'stowage_total': model.get_stowage_total_quantity(vcn_id),
        'igm_total': model.get_igm_total_quantity(vcn_id)
    })

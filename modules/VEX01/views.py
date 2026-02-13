from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions, get_module_config

bp = Blueprint('VEX01', __name__, template_folder='.')
MODULE_CODE = 'VEX01'

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

@bp.route('/module/VEX01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('vex01.html', permissions=perms)

@bp.route('/api/module/VEX01/data')
@login_required
def get_data():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    data, total = model.get_data(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})

@bp.route('/api/module/VEX01/save', methods=['POST'])
@login_required
def save():
    perms = get_perms()
    data = request.json
    is_new = not data.get('id')

    if is_new and not perms.get('can_add'):
        return jsonify({'error': 'No permission to add'}), 403
    if not is_new and not perms.get('can_edit'):
        return jsonify({'error': 'No permission to edit'}), 403

    config = get_module_config('VEX01')
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
    return jsonify({'success': True, 'id': row_id, 'vex_doc_num': doc_num, 'doc_status': data.get('doc_status')})

@bp.route('/api/module/VEX01/delete', methods=['POST'])
@login_required
def delete():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_header(request.json.get('id'))
    return jsonify({'success': True})

# Barge Lines endpoints
@bp.route('/api/module/VEX01/barge_lines/<int:vex_id>')
@login_required
def get_barge_lines(vex_id):
    return jsonify(model.get_barge_lines(vex_id))

@bp.route('/api/module/VEX01/barge_lines/save', methods=['POST'])
@login_required
def save_barge_line():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_barge_line(request.json)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VEX01/barge_lines/delete', methods=['POST'])
@login_required
def delete_barge_line():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_barge_line(request.json.get('id'))
    return jsonify({'success': True})

# MBC Lines endpoints
@bp.route('/api/module/VEX01/mbc_lines/<int:vex_id>')
@login_required
def get_mbc_lines(vex_id):
    return jsonify(model.get_mbc_lines(vex_id))

@bp.route('/api/module/VEX01/mbc_lines/save', methods=['POST'])
@login_required
def save_mbc_line():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_mbc_line(request.json)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VEX01/mbc_lines/delete', methods=['POST'])
@login_required
def delete_mbc_line():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_mbc_line(request.json.get('id'))
    return jsonify({'success': True})

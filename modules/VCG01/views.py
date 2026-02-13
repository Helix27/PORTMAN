from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions

bp = Blueprint('VCG01', __name__, template_folder='.')
MODULE_CODE = 'VCG01'

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

@bp.route('/module/VCG01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('vcg01.html', permissions=perms)

@bp.route('/api/module/VCG01/data')
@login_required
def get_data():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    data, total = model.get_data(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})

@bp.route('/api/module/VCG01/all')
@login_required
def get_all():
    return jsonify(model.get_all())

@bp.route('/api/module/VCG01/types')
@login_required
def get_types():
    return jsonify(model.get_cargo_types())

@bp.route('/api/module/VCG01/categories')
@login_required
def get_categories():
    cargo_type = request.args.get('cargo_type')
    return jsonify(model.get_cargo_categories(cargo_type))

@bp.route('/api/module/VCG01/names')
@login_required
def get_names():
    cargo_type = request.args.get('cargo_type')
    cargo_category = request.args.get('cargo_category')
    return jsonify(model.get_cargo_names(cargo_type, cargo_category))

@bp.route('/api/module/VCG01/save', methods=['POST'])
@login_required
def save():
    perms = get_perms()
    data = request.json
    is_new = not data.get('id')
    if is_new and not perms.get('can_add'):
        return jsonify({'error': 'No permission to add'}), 403
    if not is_new and not perms.get('can_edit'):
        return jsonify({'error': 'No permission to edit'}), 403
    row_id = model.save_data(data)
    return jsonify({'success': True, 'id': row_id})

@bp.route('/api/module/VCG01/delete', methods=['POST'])
@login_required
def delete():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403
    model.delete_data(request.json.get('id'))
    return jsonify({'success': True})

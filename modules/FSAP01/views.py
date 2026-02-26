from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions

bp = Blueprint('FSAP01', __name__, template_folder='.')
MODULE_CODE = 'FSAP01'


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


@bp.route('/module/FSAP01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('fsap01.html', permissions=perms)


# ===== ADVANCE RECEIPTS =====

@bp.route('/api/module/FSAP01/advance-receipts')
@login_required
def get_advance_receipts():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    data, total = model.get_advance_receipts(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})


@bp.route('/api/module/FSAP01/advance-receipts/save', methods=['POST'])
@login_required
def save_advance_receipt():
    perms = get_perms()
    if not perms.get('can_edit') and not perms.get('can_add'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_advance_receipt(request.json, session.get('username'))
    return jsonify({'success': True, 'id': row_id})


@bp.route('/api/module/FSAP01/advance-receipts/delete', methods=['POST'])
@login_required
def delete_advance_receipt():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission'}), 403
    model.delete_advance_receipt(request.json.get('id'))
    return jsonify({'success': True})


# ===== INCOMING PAYMENTS =====

@bp.route('/api/module/FSAP01/incoming-payments')
@login_required
def get_incoming_payments():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    data, total = model.get_incoming_payments(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})


@bp.route('/api/module/FSAP01/incoming-payments/save', methods=['POST'])
@login_required
def save_incoming_payment():
    perms = get_perms()
    if not perms.get('can_edit') and not perms.get('can_add'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_incoming_payment(request.json, session.get('username'))
    return jsonify({'success': True, 'id': row_id})


@bp.route('/api/module/FSAP01/incoming-payments/delete', methods=['POST'])
@login_required
def delete_incoming_payment():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission'}), 403
    model.delete_incoming_payment(request.json.get('id'))
    return jsonify({'success': True})


# ===== GL JOURNAL VOUCHERS =====

@bp.route('/api/module/FSAP01/gl-jvs')
@login_required
def get_gl_jvs():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    data, total = model.get_gl_jvs(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})


@bp.route('/api/module/FSAP01/gl-jvs/save', methods=['POST'])
@login_required
def save_gl_jv():
    perms = get_perms()
    if not perms.get('can_edit') and not perms.get('can_add'):
        return jsonify({'error': 'No permission'}), 403
    row_id = model.save_gl_jv(request.json, session.get('username'))
    return jsonify({'success': True, 'id': row_id})


@bp.route('/api/module/FSAP01/gl-jvs/delete', methods=['POST'])
@login_required
def delete_gl_jv():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission'}), 403
    model.delete_gl_jv(request.json.get('id'))
    return jsonify({'success': True})

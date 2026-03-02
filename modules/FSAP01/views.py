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


@bp.route('/api/module/FSAP01/sap-invoice-logs')
@login_required
def sap_invoice_logs():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    data, total = model.get_sap_invoice_logs(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})


@bp.route('/api/module/FSAP01/sap-cn-logs')
@login_required
def sap_cn_logs():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    data, total = model.get_sap_cn_logs(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})


@bp.route('/api/module/FSAP01/gst-logs')
@login_required
def gst_logs():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    data, total = model.get_gst_logs(page, size)
    return jsonify({'data': data, 'last_page': (total + size - 1) // size, 'total': total})

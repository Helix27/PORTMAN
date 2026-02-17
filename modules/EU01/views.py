from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from . import model
from database import get_user_permissions, get_db, get_cursor

bp = Blueprint('EU01', __name__, template_folder='.')
MODULE_CODE = 'EU01'
MODULE_INFO = {'code': 'EU01', 'name': 'Equipment Utilization'}

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

@bp.route('/module/EU01/')
@login_required
def view():
    perms = get_perms()
    if not perms.get('can_read'):
        return render_template('no_access.html'), 403
    return render_template('eu01.html', permissions=perms)

# Data endpoints
@bp.route('/api/module/EU01/data')
@login_required
def get_data():
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 20, type=int)
    return jsonify(model.get_all_lines(page, size))

@bp.route('/api/module/EU01/save', methods=['POST'])
@login_required
def save_data():
    perms = get_perms()
    if not perms.get('can_add') and not perms.get('can_edit'):
        return jsonify({'error': 'No permission'}), 403

    data = request.json
    data['created_by'] = session.get('username')
    line_id = model.save_line(data)
    return jsonify({'id': line_id})

@bp.route('/api/module/EU01/delete', methods=['POST'])
@login_required
def delete_data():
    perms = get_perms()
    if not perms.get('can_delete'):
        return jsonify({'error': 'No permission to delete'}), 403

    data = request.json
    ids = data.get('ids', [])
    model.delete_lines(ids)
    return jsonify({'success': True})

# Dropdown data endpoints
@bp.route('/api/module/EU01/vcn-options')
@login_required
def get_vcn_options():
    options = model.get_vcn_options()
    result = []
    for opt in options:
        anchored = opt.get('anchorage_arrival', '')
        if anchored:
            anchored = anchored[:16].replace('T', ' ')
        display = f"{opt['vcn_doc_num']} / {opt['vessel_name']} / {anchored}"
        result.append({
            'value': display,
            'label': display,
            'type': 'VCN',
            'id': opt['id']
        })
    return jsonify(result)

@bp.route('/api/module/EU01/mbc-options')
@login_required
def get_mbc_options():
    options = model.get_mbc_options()
    result = []
    for opt in options:
        doc_date = opt.get('doc_date', '')
        display = f"{opt['doc_num']} / {opt['mbc_name']} / {doc_date}"
        result.append({
            'value': display,
            'label': display,
            'type': 'MBC',
            'id': opt['id']
        })
    return jsonify(result)

@bp.route('/api/module/EU01/equipment')
@login_required
def get_equipment():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT name FROM equipment ORDER BY name')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r['name'] for r in rows])

@bp.route('/api/module/EU01/delays')
@login_required
def get_delays():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT name FROM port_delay_types ORDER BY name')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r['name'] for r in rows])

@bp.route('/api/module/EU01/cargo')
@login_required
def get_cargo():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT cargo_name FROM vessel_cargo ORDER BY cargo_name')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r['cargo_name'] for r in rows])

@bp.route('/api/module/EU01/operation-types')
@login_required
def get_operation_types():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT name FROM vessel_operation_types ORDER BY name')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r['name'] for r in rows])

@bp.route('/api/module/EU01/uom')
@login_required
def get_uom():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT name FROM quantity_uom ORDER BY name')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r['name'] for r in rows])

@bp.route('/api/module/EU01/barges/<int:vcn_id>')
@login_required
def get_barges_for_vcn(vcn_id):
    """Get barges from a specific VCN's LDUD barge lines"""
    barges = model.get_vcn_barges(vcn_id)
    return jsonify(barges)

@bp.route('/api/module/EU01/mbc-names')
@login_required
def get_mbc_names():
    """Get all MBC names from master"""
    names = model.get_mbc_names()
    return jsonify(names)

@bp.route('/api/module/EU01/routes')
@login_required
def get_routes():
    """Get all conveyor routes"""
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT route_name FROM conveyor_routes WHERE is_active = 1 ORDER BY route_name')
    rows = cur.fetchall()
    conn.close()
    return jsonify([r['route_name'] for r in rows])

@bp.route('/api/module/EU01/vex-options')
@login_required
def get_vex_options():
    options = model.get_vex_options()
    result = []
    for opt in options:
        doc_date = opt.get('bill_of_coastal_goods_date', '')
        display = f"{opt['vex_doc_num']} / {opt['vessel_name']} / {doc_date}"
        result.append({
            'value': display,
            'label': display,
            'type': 'VEX',
            'id': opt['id']
        })
    return jsonify(result)

@bp.route('/api/module/EU01/vex-barges/<int:vex_id>')
@login_required
def get_vex_barges(vex_id):
    """Get barges from a specific VEX's barge lines"""
    barges = model.get_vex_barges(vex_id)
    return jsonify(barges)

@bp.route('/api/module/EU01/vex-mbcs/<int:vex_id>')
@login_required
def get_vex_mbcs(vex_id):
    """Get MBCs from a specific VEX's MBC lines"""
    mbcs = model.get_vex_mbcs(vex_id)
    return jsonify(mbcs)

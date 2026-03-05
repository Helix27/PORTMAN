from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from database import get_db, get_cursor, get_module_config, save_module_config
import json

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*args, **kwargs)
    return decorated

@bp.route('/', strict_slashes=False)
@admin_required
def admin_panel():
    return render_template('admin.html')

@bp.route('/api/users')
@admin_required
def get_users():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT id, username, is_admin FROM users')
    users = cur.fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@bp.route('/api/users/add', methods=['POST'])
@admin_required
def add_user():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    is_admin = 1 if data.get('is_admin') else 0

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    conn = get_db()
    cur = get_cursor(conn)
    try:
        cur.execute('INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s) RETURNING id',
                    [username, password, is_admin])
        user_id = cur.fetchone()['id']
        conn.commit()
        conn.close()
        return jsonify({'id': user_id, 'username': username, 'is_admin': is_admin})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400

@bp.route('/api/users/delete', methods=['POST'])
@admin_required
def delete_user():
    data = request.json
    user_id = data.get('id')
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete yourself'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM module_permissions WHERE user_id = %s', [user_id])
    cur.execute('DELETE FROM users WHERE id = %s', [user_id])
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@bp.route('/api/modules')
@admin_required
def get_modules():
    from app import MODULES
    return jsonify([{'code': k, 'name': v['name']} for k, v in MODULES.items() if k != 'ADMIN'])

@bp.route('/api/permissions/<module_code>')
@admin_required
def get_permissions(module_code):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT id, username FROM users')
    users = cur.fetchall()
    cur.execute('''
        SELECT user_id, can_read, can_add, can_edit, can_delete
        FROM module_permissions WHERE module_code = %s
    ''', [module_code])
    permissions = cur.fetchall()
    conn.close()

    perm_map = {p['user_id']: dict(p) for p in permissions}
    result = []
    for u in users:
        p = perm_map.get(u['id'], {'can_read': 0, 'can_add': 0, 'can_edit': 0, 'can_delete': 0})
        result.append({
            'user_id': u['id'],
            'username': u['username'],
            'can_read': p['can_read'],
            'can_add': p['can_add'],
            'can_edit': p['can_edit'],
            'can_delete': p['can_delete']
        })
    return jsonify(result)

@bp.route('/api/permissions/<module_code>/save', methods=['POST'])
@admin_required
def save_permissions(module_code):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    for p in data:
        cur.execute('''
            INSERT INTO module_permissions (user_id, module_code, can_read, can_add, can_edit, can_delete)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id, module_code) DO UPDATE SET
                can_read = %s, can_add = %s, can_edit = %s, can_delete = %s
        ''', [p['user_id'], module_code, p['can_read'], p['can_add'], p['can_edit'], p['can_delete'],
              p['can_read'], p['can_add'], p['can_edit'], p['can_delete']])
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@bp.route('/api/config/<module_code>')
@login_required
def get_config(module_code):
    config = get_module_config(module_code)
    return jsonify(config)

@bp.route('/api/config/<module_code>/save', methods=['POST'])
@admin_required
def save_config(module_code):
    config = request.json
    save_module_config(module_code, config)
    return jsonify({'success': True})


# ── LDUD Vessel Closure Admin ─────────────────────────────────────────────────

@bp.route('/api/ldud/vessels')
@admin_required
def get_ldud_vessels():
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('''
        SELECT id, doc_num, vessel_name, vcn_doc_num, operation_type, doc_status, created_by
        FROM ldud_header
        WHERE doc_status IN ('Closed', 'Partial Close')
        ORDER BY id DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route('/api/ldud/open_vessel', methods=['POST'])
@admin_required
def open_vessel():
    data = request.json
    ldud_id = data.get('id')
    if not ldud_id:
        return jsonify({'error': 'Missing id'}), 400
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute("UPDATE ldud_header SET doc_status='Draft' WHERE id=%s", (ldud_id,))
    cur.execute("""INSERT INTO approval_log (module_code, record_id, action, comment, actioned_by)
                   VALUES ('LDUD01', %s, 'Reopened by Admin', 'Manually reopened via Admin panel', %s)""",
                (ldud_id, session.get('username')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

from flask import render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import date, datetime
import json

from .. import bp
from database import get_db, get_cursor


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def _ensure_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_pivot_reports (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            data_source VARCHAR(100) NOT NULL,
            config      JSONB NOT NULL,
            created_by  INTEGER,
            created_at  TIMESTAMP DEFAULT NOW(),
            updated_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    conn.close()


def _default_dates():
    today = date.today()
    return today.replace(day=1).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def _row_to_dict(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif v is None:
            out[k] = ''
        else:
            out[k] = v
    return out


# ── Main page ────────────────────────────────────────────────────────────────

@bp.route('/module/RP01/custom-report/')
@login_required
def custom_report_index():
    _ensure_table()
    return render_template('custom_report/custom_report.html',
                           username=session.get('username'))


# ── Data sources ─────────────────────────────────────────────────────────────

VALID_SOURCES = {'vessel-ops', 'delays', 'barge-lines', 'financials'}


@bp.route('/api/module/RP01/pivot/data/<source>')
@login_required
def pivot_data(source):
    if source not in VALID_SOURCES:
        return jsonify({'error': 'Unknown data source'}), 400

    from_date, to_date = _default_dates()
    from_date = request.args.get('from_date', from_date)
    to_date   = request.args.get('to_date',   to_date)

    conn = get_db()
    cur  = get_cursor(conn)

    try:
        if source == 'vessel-ops':
            # discharge_commenced / discharge_completed are TEXT columns stored as ISO strings
            cur.execute("""
                SELECT
                    h.doc_num                                        AS "Doc No",
                    h.vcn_doc_num                                    AS "VCN No",
                    h.vessel_name                                    AS "Vessel",
                    COALESCE(v.operation_type, h.operation_type, '') AS "Operation Type",
                    COALESCE(v.vessel_agent_name, '')                AS "Vessel Agent",
                    COALESCE(STRING_AGG(DISTINCT cd.cargo_name, ', '), '') AS "Cargo",
                    COALESCE(ROUND(CAST(SUM(cd.bl_quantity) AS NUMERIC), 0), 0) AS "BL Qty (MT)",
                    LEFT(COALESCE(h.discharge_commenced, ''), 10)    AS "Discharge Date",
                    LEFT(COALESCE(h.discharge_completed,  ''), 10)   AS "Completion Date",
                    CASE
                        WHEN NULLIF(h.discharge_commenced, '') IS NOT NULL
                         AND NULLIF(h.discharge_completed,  '') IS NOT NULL
                        THEN ROUND(CAST(
                            EXTRACT(EPOCH FROM (
                                CAST(h.discharge_completed  AS TIMESTAMP) -
                                CAST(h.discharge_commenced  AS TIMESTAMP)
                            )) / 86400.0 AS NUMERIC
                        ), 2)
                        ELSE NULL
                    END                                              AS "Actual Days",
                    COALESCE(h.doc_status, '')                       AS "Status"
                FROM ldud_header h
                LEFT JOIN vcn_header v ON v.id = h.vcn_id
                LEFT JOIN vcn_cargo_declaration cd ON cd.vcn_id = h.vcn_id
                WHERE NULLIF(h.discharge_commenced, '') IS NOT NULL
                  AND LEFT(h.discharge_commenced, 10) BETWEEN %s AND %s
                GROUP BY h.id, h.doc_num, h.vcn_doc_num, h.vessel_name,
                         v.operation_type, h.operation_type, v.vessel_agent_name,
                         h.discharge_commenced, h.discharge_completed, h.doc_status
                ORDER BY h.discharge_commenced DESC
                LIMIT 10000
            """, (from_date, to_date))

        elif source == 'delays':
            cur.execute("""
                SELECT
                    h.vessel_name                                      AS "Vessel",
                    h.doc_num                                          AS "Doc No",
                    COALESCE(d.delay_name, '')                         AS "Delay Type",
                    COALESCE(d.equipment_name, '')                     AS "Equipment",
                    COALESCE(d.delay_account_type, '')                 AS "Account Type",
                    ROUND(CAST(COALESCE(d.total_time_mins, 0) / 60.0 AS NUMERIC), 2) AS "Hours",
                    LEFT(COALESCE(d.start_datetime, ''), 10)           AS "Delay Date",
                    COALESCE(h.operation_type, '')                     AS "Operation Type"
                FROM ldud_delays d
                JOIN ldud_header h ON h.id = d.ldud_id
                WHERE NULLIF(d.start_datetime, '') IS NOT NULL
                  AND LEFT(d.start_datetime, 10) BETWEEN %s AND %s
                ORDER BY d.start_datetime DESC
                LIMIT 10000
            """, (from_date, to_date))

        elif source == 'barge-lines':
            cur.execute("""
                SELECT
                    h.vessel_name                                      AS "Vessel",
                    h.doc_num                                          AS "Doc No",
                    COALESCE(bl.barge_name, '')                        AS "Barge",
                    COALESCE(bl.cargo_name, '')                        AS "Cargo",
                    COALESCE(bl.trip_number, 0)                        AS "Trip No",
                    COALESCE(bl.discharge_quantity, 0)                 AS "Discharge Qty (MT)",
                    LEFT(COALESCE(bl.completed_discharge_berth,
                                  bl.along_side_vessel, ''), 10)       AS "Discharge Date"
                FROM ldud_barge_lines bl
                JOIN ldud_header h ON h.id = bl.ldud_id
                WHERE NULLIF(COALESCE(bl.completed_discharge_berth,
                                      bl.along_side_vessel), '') IS NOT NULL
                  AND LEFT(COALESCE(bl.completed_discharge_berth,
                                    bl.along_side_vessel), 10) BETWEEN %s AND %s
                ORDER BY bl.along_side_vessel DESC
                LIMIT 10000
            """, (from_date, to_date))

        elif source == 'financials':
            # bill_date is TEXT; bill_lines uses service_name, line_amount, line_total
            cur.execute("""
                SELECT
                    LEFT(COALESCE(b.bill_date, ''), 10)               AS "Bill Date",
                    COALESCE(b.bill_number, '')                        AS "Bill No",
                    COALESCE(b.customer_name, '')                      AS "Customer",
                    COALESCE(b.customer_type, '')                      AS "Customer Type",
                    COALESCE(bl.service_name, '')                      AS "Service",
                    COALESCE(bl.uom, '')                               AS "UOM",
                    COALESCE(bl.quantity, 0)                           AS "Qty",
                    COALESCE(bl.line_amount, 0)                        AS "Amount",
                    COALESCE(bl.cgst_amount, 0)
                      + COALESCE(bl.sgst_amount, 0)
                      + COALESCE(bl.igst_amount, 0)                    AS "GST Amount",
                    COALESCE(bl.line_total, 0)                         AS "Total",
                    COALESCE(b.bill_status, '')                        AS "Status"
                FROM bill_header b
                LEFT JOIN bill_lines bl ON bl.bill_id = b.id
                WHERE NULLIF(b.bill_date, '') IS NOT NULL
                  AND LEFT(b.bill_date, 10) BETWEEN %s AND %s
                ORDER BY b.bill_date DESC
                LIMIT 10000
            """, (from_date, to_date))

        rows = [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    return jsonify(rows)


# ── Saved reports CRUD ───────────────────────────────────────────────────────

@bp.route('/api/module/RP01/pivot/saved-reports', methods=['GET'])
@login_required
def saved_reports_list():
    _ensure_table()
    conn = get_db()
    cur  = get_cursor(conn)
    cur.execute("""
        SELECT id, name, description, data_source, config, created_at
        FROM saved_pivot_reports
        ORDER BY updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get('created_at'), (date, datetime)):
            d['created_at'] = d['created_at'].isoformat()
        result.append(d)
    return jsonify(result)


@bp.route('/api/module/RP01/pivot/saved-reports', methods=['POST'])
@login_required
def saved_reports_create():
    _ensure_table()
    body = request.get_json(force=True) or {}
    name        = (body.get('name') or '').strip()
    description = (body.get('description') or '').strip()
    data_source = (body.get('data_source') or '').strip()
    config      = body.get('config', {})

    if not name or data_source not in VALID_SOURCES:
        return jsonify({'error': 'name and valid data_source are required'}), 400

    conn = get_db()
    cur  = get_cursor(conn)
    cur.execute("""
        INSERT INTO saved_pivot_reports (name, description, data_source, config, created_by)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (name, description, data_source, json.dumps(config), session.get('user_id')))
    new_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return jsonify({'id': new_id, 'name': name}), 201


@bp.route('/api/module/RP01/pivot/saved-reports/<int:report_id>', methods=['PUT'])
@login_required
def saved_reports_update(report_id):
    body = request.get_json(force=True) or {}
    name        = (body.get('name') or '').strip()
    description = (body.get('description') or '').strip()
    config      = body.get('config', {})

    if not name:
        return jsonify({'error': 'name is required'}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE saved_pivot_reports
        SET name = %s, description = %s, config = %s, updated_at = NOW()
        WHERE id = %s
    """, (name, description, json.dumps(config), report_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@bp.route('/api/module/RP01/pivot/saved-reports/<int:report_id>', methods=['DELETE'])
@login_required
def saved_reports_delete(report_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("DELETE FROM saved_pivot_reports WHERE id = %s", (report_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

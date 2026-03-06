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

VALID_SOURCES = {'mbc-ops', 'vessel-ops', 'vessel-barge'}


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
        if source == 'mbc-ops':
            # One row per MBC record. Import uses mbc_load_port_lines + mbc_discharge_port_lines.
            # Export uses mbc_export_load_port_lines; discharge port columns are NULL.
            cur.execute("""
                SELECT
                    -- Header
                    h.doc_num                                           AS "Doc No",
                    COALESCE(h.doc_series, '')                          AS "Doc Series",
                    COALESCE(h.doc_date, '')                            AS "Doc Date",
                    COALESCE(h.mbc_name, '')                            AS "MBC Name",
                    COALESCE(h.operation_type, '')                      AS "Operation Type",
                    COALESCE(h.cargo_type, '')                          AS "Cargo Type",
                    COALESCE(h.cargo_name, '')                          AS "Cargo Name",
                    COALESCE(h.bl_quantity, 0)                          AS "BL Qty",
                    COALESCE(h.quantity_uom, '')                        AS "UOM",
                    COALESCE(h.doc_status, '')                          AS "Status",
                    COALESCE(h.created_by, '')                          AS "Created By",
                    COALESCE(h.created_date, '')                        AS "Created Date",
                    COALESCE(
                        STRING_AGG(DISTINCT cd.customer_name, ', ')
                            FILTER (WHERE cd.customer_name IS NOT NULL),
                    '')                                                 AS "Customer",

                    -- Load Port (Import: mbc_load_port_lines; Export: mbc_export_load_port_lines)
                    COALESCE(lp.eta, '')                                AS "LP ETA",
                    COALESCE(lp.arrived_load_port, elp.arrived_at_port, '')  AS "LP Arrived",
                    COALESCE(lp.alongside_berth, elp.alongside_at_berth, '') AS "LP Alongside Berth",
                    COALESCE(lp.loading_commenced, elp.loading_commenced, '') AS "LP Loading Commenced",
                    COALESCE(lp.loading_completed, elp.loading_completed, '') AS "LP Loading Completed",
                    COALESCE(lp.cast_off_load_port, elp.cast_off_from_berth, '') AS "LP Cast Off",
                    COALESCE(elp.sailed_out_from_port, '')              AS "LP Sailed Out (Export)",
                    COALESCE(elp.eta_at_gull_island, '')                AS "LP ETA Gull Island (Export)",
                    COALESCE(elp.unloaded_by, '')                       AS "LP Unloaded By (Export)",
                    COALESCE(elp.berth_master, '')                      AS "LP Berth Master (Export)",

                    -- Discharge Port (Import only; NULL for Export)
                    COALESCE(dp.sailed_out_load_port::TEXT, '')         AS "DP Sailed Out Load Port",
                    COALESCE(dp.arrived_yellow_crane::TEXT, '')         AS "DP Arrived Yellow Crane",
                    COALESCE(dp.arrival_gull_island, '')                AS "DP Arrival Gull Island",
                    COALESCE(dp.departure_gull_island, '')              AS "DP Departure Gull Island",
                    COALESCE(dp.vessel_arrival_port, '')                AS "DP Vessel Arrival Port",
                    COALESCE(dp.vessel_all_made_fast, '')               AS "DP Vessel All Made Fast",
                    COALESCE(dp.unloading_commenced, '')                AS "DP Unloading Commenced",
                    COALESCE(dp.unloading_completed, '')                AS "DP Unloading Completed",
                    COALESCE(dp.cleaning_commenced, '')                 AS "DP Cleaning Commenced",
                    COALESCE(dp.cleaning_completed, '')                 AS "DP Cleaning Completed",
                    COALESCE(dp.vessel_cast_off, '')                    AS "DP Vessel Cast Off",
                    COALESCE(dp.vessel_unloaded_by, '')                 AS "DP Vessel Unloaded By",
                    COALESCE(dp.vessel_unloading_berth, '')             AS "DP Unloading Berth",
                    COALESCE(dp.discharge_stop_shifting, '')            AS "DP Stop Shifting",
                    COALESCE(dp.discharge_start_shifting, '')           AS "DP Start Shifting"

                FROM mbc_header h
                LEFT JOIN mbc_load_port_lines        lp  ON lp.mbc_id  = h.id
                LEFT JOIN mbc_export_load_port_lines elp ON elp.mbc_id = h.id
                LEFT JOIN mbc_discharge_port_lines   dp  ON dp.mbc_id  = h.id
                LEFT JOIN mbc_customer_details       cd  ON cd.mbc_id  = h.id
                WHERE NULLIF(h.doc_date, '') IS NOT NULL
                  AND h.doc_date BETWEEN %s AND %s
                GROUP BY h.id, lp.id, elp.id, dp.id
                ORDER BY h.doc_date DESC, h.id DESC
                LIMIT 10000
            """, (from_date, to_date))

        elif source == 'vessel-ops':
            cur.execute("""
                SELECT
                    h.doc_num                                           AS "Doc No",
                    h.vcn_doc_num                                       AS "VCN No",
                    COALESCE(h.vessel_name, '')                         AS "Vessel",
                    COALESCE(v.operation_type, h.operation_type, '')    AS "Operation Type",
                    COALESCE(v.vessel_agent_name, '')                   AS "Vessel Agent",
                    COALESCE(STRING_AGG(DISTINCT cd.cargo_name, ', '), '') AS "Cargo",
                    COALESCE(ROUND(CAST(SUM(cd.bl_quantity) AS NUMERIC), 0), 0) AS "BL Qty (MT)",
                    LEFT(COALESCE(h.discharge_commenced, ''), 10)       AS "Discharge Date",
                    LEFT(COALESCE(h.discharge_completed,  ''), 10)      AS "Completion Date",
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
                    END                                                 AS "Actual Days",
                    COALESCE(h.doc_status, '')                          AS "Status"
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

        elif source == 'vessel-barge':
            cur.execute("""
                SELECT
                    -- Header
                    h.doc_num                                               AS "Doc No",
                    COALESCE(h.vcn_doc_num, '')                            AS "VCN No",
                    COALESCE(h.vessel_name, '')                            AS "Vessel",
                    COALESCE(v.operation_type, h.operation_type, '')       AS "Operation Type",
                    COALESCE(v.vessel_agent_name, '')                      AS "Vessel Agent",
                    COALESCE(h.doc_status, '')                             AS "Status",
                    COALESCE(h.created_by, '')                             AS "Created By",
                    COALESCE(h.created_date, '')                           AS "Created Date",

                    -- LDUD Header timestamps
                    COALESCE(h.anchored_datetime::TEXT, '')                AS "Anchored Date/Time",
                    COALESCE(h.arrival_inner_anchorage::TEXT, '')          AS "Arrival Inner Anchorage",
                    COALESCE(h.arrival_outer_anchorage::TEXT, '')          AS "Arrival Outer Anchorage",
                    COALESCE(h.arrived_mbpt::TEXT, '')                     AS "Arrived MBPT",
                    COALESCE(h.arrived_mfl::TEXT, '')                      AS "Arrived MFL",
                    COALESCE(h.free_pratique_granted::TEXT, '')            AS "Free Pratique Granted",
                    COALESCE(h.nor_tendered::TEXT, '')                     AS "NOR Tendered",
                    COALESCE(h.nor_accepted::TEXT, '')                     AS "NOR Accepted",
                    COALESCE(h.discharge_commenced::TEXT, '')              AS "Discharge Commenced",
                    COALESCE(h.discharge_completed::TEXT, '')              AS "Discharge Completed",
                    COALESCE(h.custom_clearance::TEXT, '')                 AS "Custom Clearance",
                    COALESCE(h.agent_stevedore_onboard::TEXT, '')          AS "Agent/Stevedore Onboard",
                    COALESCE(h.initial_draft_survey_from::TEXT, '')        AS "Initial Draft Survey From",
                    COALESCE(h.initial_draft_survey_to::TEXT, '')          AS "Initial Draft Survey To",
                    COALESCE(h.initial_draft_survey_quantity::TEXT, '')    AS "Initial Draft Survey Qty",
                    COALESCE(h.final_draft_survey_from::TEXT, '')          AS "Final Draft Survey From",
                    COALESCE(h.final_draft_survey_to::TEXT, '')            AS "Final Draft Survey To",

                    -- Barge Line
                    COALESCE(bl.trip_number::TEXT, '')                     AS "Trip No",
                    COALESCE(bl.hold_name, '')                             AS "Hold",
                    COALESCE(bl.barge_name, '')                            AS "Barge",
                    COALESCE(bl.contractor_name, '')                       AS "Contractor",
                    COALESCE(bl.cargo_name, '')                            AS "Cargo",
                    COALESCE(bl.bpt_bfl, '')                               AS "BPT/BFL",
                    COALESCE(bl.along_side_vessel::TEXT, '')               AS "Alongside Vessel",
                    COALESCE(bl.commenced_loading::TEXT, '')               AS "Commenced Loading",
                    COALESCE(bl.completed_loading::TEXT, '')               AS "Completed Loading",
                    COALESCE(bl.cast_off_mv::TEXT, '')                     AS "Cast Off MV",
                    COALESCE(bl.anchored_gull_island::TEXT, '')            AS "Anchored Gull Island",
                    COALESCE(bl.aweigh_gull_island::TEXT, '')              AS "Aweigh Gull Island",
                    COALESCE(bl.along_side_berth::TEXT, '')                AS "Alongside Berth",
                    COALESCE(bl.commence_discharge_berth::TEXT, '')        AS "Commence Discharge Berth",
                    COALESCE(bl.completed_discharge_berth::TEXT, '')       AS "Completed Discharge Berth",
                    COALESCE(bl.cast_off_berth::TEXT, '')                  AS "Cast Off Berth",
                    COALESCE(bl.cast_off_berth_nt::TEXT, '')               AS "Cast Off Berth NT",
                    COALESCE(bl.discharge_quantity::TEXT, '')              AS "Discharge Qty",
                    COALESCE(bl.crane_loaded_from, '')                     AS "Crane Loaded From",
                    COALESCE(bl.trip_start::TEXT, '')                      AS "Trip Start",
                    COALESCE(bl.amf_at_port::TEXT, '')                     AS "AMF At Port",
                    COALESCE(bl.cast_off_port::TEXT, '')                   AS "Cast Off Port",
                    COALESCE(bl.port_crane, '')                            AS "Port Crane",
                    COALESCE(bl.cast_off_loading_berth::TEXT, '')          AS "Cast Off Loading Berth",
                    COALESCE(bl.anchored_gull_island_empty::TEXT, '')      AS "Anchored Gull Island (Empty)",
                    COALESCE(bl.aweigh_gull_island_empty::TEXT, '')        AS "Aweigh Gull Island (Empty)"

                FROM ldud_header h
                LEFT JOIN vcn_header v ON v.id = h.vcn_id
                LEFT JOIN ldud_barge_lines bl ON bl.ldud_id = h.id
                WHERE NULLIF(h.discharge_commenced, '') IS NOT NULL
                  AND LEFT(h.discharge_commenced, 10) BETWEEN %s AND %s
                ORDER BY h.discharge_commenced DESC, h.id, bl.trip_number
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

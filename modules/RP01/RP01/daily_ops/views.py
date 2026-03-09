from flask import render_template, request, session, redirect, url_for, Response
from functools import wraps
from datetime import date, datetime, timedelta
import io

from .. import bp
from database import get_db, get_cursor

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Style constants (same as rest of RP01) ──────────────────────────────────
XL_NORM_SZ = 11
_thin  = Side(style='thin',   color='000000')
_bdr   = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
_ctr   = Alignment(horizontal='center', vertical='center', wrap_text=True)
_left  = Alignment(horizontal='left',   vertical='center', wrap_text=True)


def _fill(hex_color):
    return PatternFill('solid', fgColor=hex_color)


def _font(bold=False, size=XL_NORM_SZ):
    return Font(name='Calibri', bold=bold, size=size)


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


def _fmt_dt(val, strfmt='%d-%m-%Y %H:%M'):
    dt = _parse_dt(val)
    return dt.strftime(strfmt) if dt else ''


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/module/RP01/daily-ops/')
@login_required
def daily_ops_index():
    return render_template('daily_ops/daily_ops.html', username=session.get('username'))


def _fetch_data(report_date):
    window_end   = datetime(report_date.year, report_date.month, report_date.day, 7, 0, 0)
    window_start = window_end - timedelta(hours=24)
    ws_str = window_start.strftime('%Y-%m-%d %H:%M:%S')
    we_str = window_end.strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cur  = get_cursor(conn)

    # Active vessels: commenced before window_end, not completed before window_start
    cur.execute("""
        SELECT h.id, h.vcn_id, h.vessel_name, h.operation_type,
               h.nor_tendered, h.discharge_commenced, h.discharge_completed
        FROM ldud_header h
        WHERE h.discharge_commenced IS NOT NULL
          AND h.operation_type IN ('Import', 'Export')
          AND h.discharge_commenced < %s
          AND (h.discharge_completed IS NULL OR h.discharge_completed > %s)
        ORDER BY h.discharge_commenced ASC
        LIMIT 5
    """, (we_str, ws_str))
    vessels = [dict(r) for r in cur.fetchall()]

    ldud_ids = [v['id']     for v in vessels]
    vcn_ids  = [v['vcn_id'] for v in vessels if v.get('vcn_id')]

    bl_import = {}
    bl_export  = {}
    vcn_meta   = {}
    if vcn_ids:
        cur.execute("""
            SELECT vcn_id, COALESCE(SUM(bl_quantity), 0) AS total
            FROM vcn_cargo_declaration WHERE vcn_id = ANY(%s) GROUP BY vcn_id
        """, (vcn_ids,))
        for r in cur.fetchall():
            bl_import[r['vcn_id']] = float(r['total'])

        cur.execute("""
            SELECT vcn_id, COALESCE(SUM(bl_quantity), 0) AS total
            FROM vcn_export_cargo_declaration WHERE vcn_id = ANY(%s) GROUP BY vcn_id
        """, (vcn_ids,))
        for r in cur.fetchall():
            bl_export[r['vcn_id']] = float(r['total'])

        cur.execute("""
            SELECT id, importer_exporter_name FROM vcn_header WHERE id = ANY(%s)
        """, (vcn_ids,))
        vcn_meta = {r['id']: r['importer_exporter_name'] or '' for r in cur.fetchall()}

    ops_24h     = {}
    ops_till    = {}
    barges      = {}
    supervisors = {}

    if ldud_ids:
        cur.execute("""
            SELECT ldud_id, COALESCE(SUM(quantity), 0) AS qty
            FROM ldud_vessel_operations
            WHERE ldud_id = ANY(%s)
              AND start_time >= %s AND start_time < %s
            GROUP BY ldud_id
        """, (ldud_ids, ws_str, we_str))
        for r in cur.fetchall():
            ops_24h[r['ldud_id']] = float(r['qty'])

        cur.execute("""
            SELECT ldud_id, COALESCE(SUM(quantity), 0) AS qty
            FROM ldud_vessel_operations
            WHERE ldud_id = ANY(%s)
              AND start_time < %s
            GROUP BY ldud_id
        """, (ldud_ids, we_str))
        for r in cur.fetchall():
            ops_till[r['ldud_id']] = float(r['qty'])

        cur.execute("""
            SELECT ldud_id, COUNT(DISTINCT barge_name) AS cnt
            FROM ldud_barge_lines
            WHERE ldud_id = ANY(%s)
              AND along_side_vessel >= %s AND along_side_vessel < %s
              AND barge_name IS NOT NULL AND barge_name != ''
            GROUP BY ldud_id
        """, (ldud_ids, ws_str, we_str))
        for r in cur.fetchall():
            barges[r['ldud_id']] = int(r['cnt'])

        cur.execute("""
            SELECT DISTINCT ON (source_id) source_id, shift_incharge
            FROM lueu_lines
            WHERE source_type = 'LDUD'
              AND source_id = ANY(%s)
              AND entry_date = %s
              AND shift_incharge IS NOT NULL AND shift_incharge != ''
            ORDER BY source_id, id DESC
        """, (ldud_ids, report_date.strftime('%Y-%m-%d')))
        for r in cur.fetchall():
            supervisors[r['source_id']] = r['shift_incharge']

    conn.close()

    for v in vessels:
        lid        = v['id']
        vid        = v.get('vcn_id')
        op         = v.get('operation_type', '')
        bl_qty     = (bl_export.get(vid, 0) if op == 'Export' else bl_import.get(vid, 0)) if vid else 0
        discharged = ops_till.get(lid, 0)
        v['stevedore_group'] = vcn_meta.get(vid, '') if vid else ''
        v['bl_qty']          = bl_qty
        v['ops_24h']         = ops_24h.get(lid, 0)
        v['ops_till']        = discharged
        v['balance']         = bl_qty - discharged
        v['supervisor']      = supervisors.get(lid, '')
        v['num_barges']      = barges.get(lid, 0)

    return vessels


def _build_excel(vessels, report_date):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Daily Ops'

    col_widths = {1: 26, 2: 19, 3: 19, 4: 19, 5: 19, 6: 19, 7: 5, 8: 27, 9: 18}
    for ci, w in col_widths.items():
        ws.column_dimensions[get_column_letter(ci)].width = w

    def _cell(r, c, val='', bold=False, fill='FFFFFF', align=_ctr):
        cell = ws.cell(r, c, val)
        cell.font      = _font(bold=bold)
        cell.fill      = _fill(fill)
        cell.alignment = align
        cell.border    = _bdr
        return cell

    def _merge_row(r, c1, c2, val='', bold=False, fill='FFFFFF', align=_ctr):
        ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
        for ci in range(c1, c2 + 1):
            b = Border(
                left   = _thin if ci == c1 else None,
                right  = _thin if ci == c2 else None,
                top    = _thin,
                bottom = _thin,
            )
            try:
                cell        = ws.cell(r, ci)
                cell.fill   = _fill(fill)
                cell.border = b
            except AttributeError:
                pass  # MergedCell stub in some openpyxl versions
        anchor           = ws.cell(r, c1)
        anchor.value     = val
        anchor.font      = _font(bold=bold)
        anchor.alignment = align

    date_str  = f"{report_date.day}.{report_date.month}.{report_date.year}"
    title_str = f'Daily Report of JSW Dharamtar Port Operation : {date_str}'

    # Row 1
    ws.row_dimensions[1].height = 20
    _cell(1, 1, report_date.strftime('%d-%m-%Y'), align=_left)
    _merge_row(1, 2, 7, title_str, align=_ctr)
    _cell(1, 8, 'Doc No. | REV.02 | Issue no. 02', align=_left)
    _cell(1, 9, f'Issue Date: {report_date.strftime("%d-%m-%Y")}', align=_left)

    # Row 2: vessel name headers
    ws.row_dimensions[2].height = 35
    _cell(2, 1, '')
    for i, v in enumerate(vessels):
        _cell(2, 2 + i, f'Vessel {i + 1}: {v["vessel_name"]}', bold=True, align=_ctr)
    for i in range(len(vessels), 5):
        _cell(2, 2 + i, '')
    _cell(2, 7, '')
    _cell(2, 8, '')
    _cell(2, 9, '')

    # Rows 3–13
    ROWS = [
        ('Stevedore/ Barge Group',       'stevedore_group',      None),
        ('BL Qty',                        'bl_qty',               lambda x: int(round(x)) if x else ''),
        ('24 hrs Discharge',              'ops_24h',              lambda x: int(round(x)) if x else ''),
        ('Discharged /Loaded till Date',  'ops_till',             lambda x: int(round(x)) if x else ''),
        ('Balance on Board /to Load',     'balance',              lambda x: int(round(x)) if x else ''),
        ('Vsl Arrived/NOR',               'nor_tendered',         _fmt_dt),
        ('Disch Commenced',               'discharge_commenced',  _fmt_dt),
        ('Disch Completed',               'discharge_completed',  _fmt_dt),
        (None, None, None),
        ('Stevedore Supervisor',          'supervisor',           None),
        ('No of Barges',                  'num_barges',           lambda x: x if x else ''),
    ]

    for idx, (label, field, formatter) in enumerate(ROWS):
        r = 3 + idx
        ws.row_dimensions[r].height = 18

        if label is None:
            for ci in range(1, 10):
                _cell(r, ci, '')
            continue

        _cell(r, 1, label, bold=True, align=_left)
        for i, v in enumerate(vessels):
            raw = v.get(field)
            val = formatter(raw) if (formatter and raw is not None) else (raw or '')
            _cell(r, 2 + i, val, align=_ctr)
        for i in range(len(vessels), 5):
            _cell(r, 2 + i, '')
        _cell(r, 7, '')
        _cell(r, 8, '')
        _cell(r, 9, '')

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@bp.route('/api/module/RP01/daily-ops/download')
@login_required
def daily_ops_download():
    date_str = request.args.get('report_date', date.today().strftime('%Y-%m-%d'))
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response('Invalid date', status=400)

    vessels = _fetch_data(report_date)
    if not vessels:
        return Response('No active vessels on the selected date', status=404)

    buf   = _build_excel(vessels, report_date)
    fname = f'DailyOps_{date_str}.xlsx'
    return Response(
        buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'},
    )

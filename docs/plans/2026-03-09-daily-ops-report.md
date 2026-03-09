# Daily Port Operations Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Daily Port Operations Report" to RP01 that downloads a date-scoped Excel showing up to 5 active vessels (Import + Export) side-by-side with key daily figures.

**Architecture:** New `daily_ops` sub-module inside `modules/RP01/RP01/`, following the exact same pattern as `vessel_discharged`. A single date-picker UI page triggers a download-only Excel API. The Excel builder queries ldud_header, ldud_vessel_operations, ldud_barge_lines, vcn_header, vcn_cargo_declaration, vcn_export_cargo_declaration, and lueu_lines.

**Tech Stack:** Flask, openpyxl, psycopg2, Jinja2, vanilla JS — same as all other RP01 sub-reports.

---

### Task 1: Create the sub-module skeleton

**Files:**
- Create: `modules/RP01/RP01/daily_ops/__init__.py`
- Create: `modules/RP01/RP01/daily_ops/views.py` (stub only)
- Create: `modules/RP01/RP01/daily_ops/daily_ops.html` (stub only)

**Step 1: Create `__init__.py`**

Exact content — empty file, just a module marker:
```python
```
(empty file)

**Step 2: Create stub `views.py`**

```python
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

def _fmt_dt(val, fmt='%d-%m-%y %H:%M'):
    dt = _parse_dt(val)
    return dt.strftime(fmt) if dt else ''


def login_required(f):
    from functools import wraps
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
```

**Step 3: Create stub `daily_ops.html`**

```html
{% extends "base.html" %}
{% block title %}Daily Port Operations Report — RP01{% endblock %}
{% block content %}
<p>Stub — coming soon.</p>
{% endblock %}
```

**Step 4: Wire the sub-module into RP01**

In `modules/RP01/RP01/views.py`, add one import line after the existing imports:
```python
from .daily_ops import views as _daily_ops_views  # noqa: registers daily-ops routes on bp
```

**Step 5: Verify the route loads without error**

Start the app and navigate to `/module/RP01/daily-ops/` — should render the stub page.

---

### Task 2: Data fetch function

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py`

Add `_fetch_data(report_date)` below the helpers. `report_date` is a `datetime.date` object.

The "7am boundary" for the 24hr window:
- `window_end   = datetime(report_date.year, report_date.month, report_date.day, 7, 0, 0)`
- `window_start = window_end - timedelta(hours=24)`

**Step 1: Add the function**

```python
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
          AND h.discharge_commenced < %s
          AND (h.discharge_completed IS NULL OR h.discharge_completed > %s)
        ORDER BY h.discharge_commenced ASC
        LIMIT 5
    """, (we_str, ws_str))
    vessels = [dict(r) for r in cur.fetchall()]

    ldud_ids = [v['id']    for v in vessels]
    vcn_ids  = [v['vcn_id'] for v in vessels if v.get('vcn_id')]

    # BL quantities per vcn_id (import + export separate tables)
    bl_import = {}
    bl_export  = {}
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

        # Stevedore / barge group name
        cur.execute("""
            SELECT id, importer_exporter_name FROM vcn_header WHERE id = ANY(%s)
        """, (vcn_ids,))
        vcn_meta = {r['id']: r['importer_exporter_name'] or '' for r in cur.fetchall()}
    else:
        vcn_meta = {}

    # Per-ldud aggregates
    ops_24h  = {}   # ldud_id -> qty in 24hr window
    ops_till = {}   # ldud_id -> cumulative qty up to window_end
    barges   = {}   # ldud_id -> count of distinct barges in 24hr window
    supervisors = {} # ldud_id -> shift_incharge

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

    # Enrich vessel dicts
    for v in vessels:
        lid    = v['id']
        vid    = v.get('vcn_id')
        op     = v.get('operation_type', '')
        bl_qty = (bl_export.get(vid, 0) if op == 'Export' else bl_import.get(vid, 0)) if vid else 0
        discharged = ops_till.get(lid, 0)
        v['stevedore_group'] = vcn_meta.get(vid, '')   if vid else ''
        v['bl_qty']          = bl_qty
        v['ops_24h']         = ops_24h.get(lid, 0)
        v['ops_till']        = discharged
        v['balance']         = bl_qty - discharged
        v['supervisor']      = supervisors.get(lid, '')
        v['num_barges']      = barges.get(lid, 0)

    return vessels
```

---

### Task 3: Excel builder

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py`

Add `_build_excel(vessels, report_date)` below `_fetch_data`.

Column layout (9 columns):
- A=1 labels, B=2…F=6 vessel data, G=7 spacer, H=8 doc info, I=9 issue date

```python
def _build_excel(vessels, report_date):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Daily Ops'

    # Column widths
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
        _cell(r, c1, val, bold=bold, fill=fill, align=align)
        for ci in range(c1 + 1, c2 + 1):
            c = ws.cell(r, ci)
            c.fill   = _fill(fill)
            c.border = Border(
                left   = None,
                right  = _thin if ci == c2 else None,
                top    = _thin,
                bottom = _thin,
            )

    date_str  = report_date.strftime('%-d.%-m.%Y') if hasattr(report_date, 'strftime') else str(report_date)
    # Windows-safe date formatting (no %-d)
    date_str  = f"{report_date.day}.{report_date.month}.{report_date.year}"
    title_str = f'Daily Report of JSW Dharamtar Port Operation : {date_str}'

    # ── Row 1 ─────────────────────────────────────────────────────────────────
    ws.row_dimensions[1].height = 20
    _cell(1, 1, report_date.strftime('%d-%m-%Y'), align=_left)
    _merge_row(1, 2, 7, title_str, bold=False, align=_ctr)
    _cell(1, 8, 'Doc No. | REV.02 | Issue no. 02', align=_left)
    _cell(1, 9, f'Issue Date: {report_date.strftime("%d-%m-%Y")}', align=_left)

    # ── Row 2: vessel name headers ────────────────────────────────────────────
    ws.row_dimensions[2].height = 35
    _cell(2, 1, '', fill='FFFFFF')
    for i, v in enumerate(vessels):
        _cell(2, 2 + i, f'Vessel {i+1}: {v["vessel_name"]}', bold=True, align=_ctr)
    for i in range(len(vessels), 5):          # blank remaining vessel cols
        _cell(2, 2 + i, '', fill='FFFFFF')
    _cell(2, 7, '', fill='FFFFFF')
    _cell(2, 8, '', fill='FFFFFF')
    _cell(2, 9, '', fill='FFFFFF')

    # ── Rows 3–13: data rows ──────────────────────────────────────────────────
    ROWS = [
        ('Stevedore/ Barge Group',      'stevedore_group', None),
        ('BL Qty',                       'bl_qty',          lambda x: int(round(x)) if x else ''),
        ('24 hrs Discharge',             'ops_24h',         lambda x: int(round(x)) if x else ''),
        ('Discharged /Loaded till Date', 'ops_till',        lambda x: int(round(x)) if x else ''),
        ('Balance on Board /to Load',    'balance',         lambda x: int(round(x)) if x else ''),
        ('Vsl Arrived/NOR',              'nor_tendered',    _fmt_dt),
        ('Disch Commenced',              'discharge_commenced', _fmt_dt),
        ('Disch Completed',              'discharge_completed', _fmt_dt),
        (None, None, None),                    # blank row 11
        ('Stevedore Supervisor',         'supervisor',      None),
        ('No of Barges',                 'num_barges',      lambda x: x if x else ''),
    ]

    for idx, (label, field, fmt) in enumerate(ROWS):
        r = 3 + idx
        ws.row_dimensions[r].height = 18

        if label is None:                      # blank row
            for ci in range(1, 10):
                _cell(r, ci, '', fill='FFFFFF')
            continue

        _cell(r, 1, label, bold=True, align=_left)
        for i, v in enumerate(vessels):
            raw = v.get(field)
            val = fmt(raw) if (fmt and raw is not None) else (raw or '')
            _cell(r, 2 + i, val, align=_ctr)
        for i in range(len(vessels), 5):
            _cell(r, 2 + i, '', fill='FFFFFF')
        _cell(r, 7, '', fill='FFFFFF')
        _cell(r, 8, '', fill='FFFFFF')
        _cell(r, 9, '', fill='FFFFFF')

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
```

---

### Task 4: Download route

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py`

Add below `_build_excel`:

```python
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
```

---

### Task 5: HTML page

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/daily_ops.html`

Replace the stub with the full page (matches `vessel_discharged_list.html` style):

```html
{% extends "base.html" %}

{% block title %}Daily Port Operations Report — RP01{% endblock %}

{% block head %}
<style>
    .page-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--border-color);
    }
    .page-header h2 { margin: 0; font-size: 18px; color: var(--text-primary); }
    .module-badge {
        background: #4a90d9;
        color: #fff;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    .breadcrumb {
        font-size: 11px; color: var(--text-secondary); margin-bottom: 14px;
    }
    .breadcrumb a { color: #4a90d9; text-decoration: none; }
    .breadcrumb a:hover { text-decoration: underline; }
    .filter-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: flex-end;
        margin-bottom: 14px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 12px 14px;
    }
    .filter-group { display: flex; flex-direction: column; gap: 4px; }
    .filter-group label {
        font-size: 10px;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    .filter-group input {
        padding: 5px 9px;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        font-size: 12px;
        background: var(--bg-primary);
        color: var(--text-primary);
        height: 30px;
    }
    .filter-group input:focus { outline: none; border-color: #4a90d9; }
    .filter-btn {
        padding: 0 18px;
        height: 30px;
        border: none;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        align-self: flex-end;
    }
    .filter-btn.primary { background: #4a90d9; color: #fff; }
    .filter-btn.primary:hover { background: #357abd; }
    .filter-btn.primary:disabled { background: #aaa; cursor: not-allowed; }
    .info-text {
        font-size: 11px;
        color: var(--text-secondary);
        margin-top: 4px;
    }
</style>
{% endblock %}

{% block content %}
<div class="page-header">
    <h2>Daily Port Operations Report</h2>
    <span class="module-badge">RP01</span>
</div>
<div class="breadcrumb">
    <a href="/module/RP01/">Reports</a> &rsaquo; Daily Port Operations
</div>

<div class="filter-bar">
    <div class="filter-group">
        <label for="report-date">Report Date</label>
        <input type="date" id="report-date">
    </div>
    <button type="button" class="filter-btn primary" id="dl-btn" onclick="downloadReport()">&#8595; Download Excel</button>
</div>

<p class="info-text">
    Shows all active vessels (Import &amp; Export) on the selected date.<br>
    24-hour window: 07:00 of the previous day to 07:00 of the selected date.
</p>

<script>
document.addEventListener('DOMContentLoaded', function () {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, '0');
    const d = String(today.getDate()).padStart(2, '0');
    document.getElementById('report-date').value = `${y}-${m}-${d}`;
});

function downloadReport() {
    const d   = document.getElementById('report-date').value;
    const btn = document.getElementById('dl-btn');
    if (!d) { alert('Please select a report date.'); return; }

    btn.disabled    = true;
    btn.textContent = 'Preparing…';

    fetch(`/api/module/RP01/daily-ops/download?report_date=${d}`)
        .then(res => {
            if (res.status === 404) throw new Error('No active vessels on the selected date.');
            if (!res.ok) throw new Error('Server error ' + res.status);
            const disposition = res.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="(.+?)"/);
            const filename = match ? match[1] : `DailyOps_${d}.xlsx`;
            return res.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(a.href);
        })
        .catch(err => {
            alert(err.message || 'Download failed. Please try again.');
        })
        .finally(() => {
            btn.disabled    = false;
            btn.textContent = '\u2193 Download Excel';
        });
}
</script>
{% endblock %}
```

---

### Task 6: Add card to RP01 index

**Files:**
- Modify: `modules/RP01/RP01/rp01.html`

Add a new card inside `<div class="report-cards">` after the last existing card:

```html
    <!-- Daily Port Operations Report -->
    <a class="report-card" href="/module/RP01/daily-ops/">
        <div class="card-icon">&#128203;</div>
        <div class="card-title">Daily Port Operations</div>
        <div class="card-desc">
            Date-wise snapshot of all active vessels — BL quantity, 24-hour discharge, cumulative discharge till date, balance, arrival, commencement, and supervisor details.
        </div>
        <div class="card-arrow">Open &rarr;</div>
    </a>
```

---

### Task 7: Verify end-to-end

**Steps:**
1. Start the Flask app.
2. Navigate to `/module/RP01/` — confirm the new "Daily Port Operations" card is visible.
3. Click the card → `/module/RP01/daily-ops/` — confirm the date picker page loads.
4. Select a date that has active vessels and click "Download Excel".
5. Open the downloaded file — verify:
   - Row 1 has the report title and date.
   - Row 2 shows vessel names for active vessels.
   - Rows 3–13 contain correct data (BL qty, 24hr ops, till-date ops, balance, NOR, commenced, completed, supervisor, barges).
   - All cells have thin borders.
   - Up to 5 vessels appear side by side.
6. Select a date with no active vessels — confirm a 404 alert appears in the browser.

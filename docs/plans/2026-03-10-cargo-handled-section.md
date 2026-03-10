# Cargo Handled Section Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Append a "Cargo Handled" section to the existing Daily Ops Excel showing
cargo quantity by receiving route from `lueu_lines`, split into "For the Day" and
"For the Month" windows.

**Architecture:** Single file change — `daily_ops/views.py`. Add a module-level
`ANNUAL_ROUTE_TOTALS` JSON dict (stored, not printed), a `_fetch_cargo_handled`
query function, extend `_build_excel` with a `_merge_col` helper and cargo section
renderer, and thread the data through `daily_ops_download`.

**Tech Stack:** Flask, psycopg2, openpyxl

---

### Current state (read before touching anything)

- File: `modules/RP01/RP01/daily_ops/views.py`
- ROWS list has 18 entries (idx 0–17), so the last data row in Excel is row 20
  (`r = 3 + 17`).
- Cargo Handled section starts at row 21 (blank separator) then row 22 onwards.
- `_build_excel(vessels, report_date, operation_type)` currently ends with
  `buf = io.BytesIO()` at line ~319.

### Time windows

```
window_end   = datetime(report_date.year, report_date.month, report_date.day, 7, 0, 0)
window_start = window_end - timedelta(hours=24)          # daily start
month_start  = datetime(report_date.year, report_date.month, 1, 7, 0, 0)  # monthly start
```

Both periods share `window_end` as their end.

---

### Task 1: Add ANNUAL_ROUTE_TOTALS constant

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py` — insert after the style constants block (after line 17)

**Step 1: Add the constant after the `_left` line**

```python
# Hardcoded annual totals by fiscal year — stored for reference, not printed in report
ANNUAL_ROUTE_TOTALS = {
    "2024-2025": {},
    "2025-2026": {},
}
```

**Step 2: Verify the file still imports without error**

```bash
cd d:/dppl/PORTMAN
python -c "from modules.RP01.RP01.daily_ops import views; print('ok')"
```

Expected: `ok`

---

### Task 2: Add _fetch_cargo_handled function

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py` — insert the new function
  immediately before `_build_excel` (before `def _build_excel`)

**Step 1: Insert the function**

```python
def _fetch_cargo_handled(report_date, operation_type):
    window_end  = datetime(report_date.year, report_date.month, report_date.day, 7, 0, 0)
    window_start = window_end - timedelta(hours=24)
    month_start  = datetime(report_date.year, report_date.month, 1, 7, 0, 0)
    we_str  = window_end.strftime('%Y-%m-%d %H:%M:%S')
    ws_str  = window_start.strftime('%Y-%m-%d %H:%M:%S')
    mth_str = month_start.strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cur  = get_cursor(conn)

    def _period(start, end):
        cur.execute("""
            SELECT route_name, COALESCE(SUM(quantity), 0) AS qty
            FROM lueu_lines
            WHERE route_name IS NOT NULL AND route_name != ''
              AND operation_type = %s
              AND start_time >= %s AND start_time < %s
            GROUP BY route_name
            ORDER BY route_name
        """, (operation_type, start, end))
        return [(r['route_name'], float(r['qty'])) for r in cur.fetchall()]

    day_rows   = _period(ws_str,  we_str)
    month_rows = _period(mth_str, we_str)
    conn.close()
    return day_rows, month_rows
```

**Step 2: Verify the function is importable**

```bash
python -c "
from modules.RP01.RP01.daily_ops.views import _fetch_cargo_handled
from datetime import date
d, m = _fetch_cargo_handled(date(2026, 1, 27), 'Import')
print('day:', d, 'month:', m)
"
```

Expected: `day: [] month: []` (no lueu_lines data yet — that's fine)

---

### Task 3: Add _merge_col helper and cargo section inside _build_excel

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py`

#### Step 1: Add `_merge_col` helper inside `_build_excel`

Insert this function definition immediately after the `_merge_row` function
definition (around line 246, still inside `_build_excel`):

```python
    def _merge_col(r1, r2, c, val='', bold=False, fill='FFFFFF', align=_ctr):
        """Merge cells vertically in column c from row r1 to r2."""
        ws.merge_cells(start_row=r1, start_column=c, end_row=r2, end_column=c)
        for ri in range(r1, r2 + 1):
            b = Border(
                left   = _thin,
                right  = _thin,
                top    = _thin if ri == r1 else None,
                bottom = _thin if ri == r2 else None,
            )
            try:
                cell        = ws.cell(ri, c)
                cell.fill   = _fill(fill)
                cell.border = b
            except AttributeError:
                pass
        anchor           = ws.cell(r1, c)
        anchor.value     = val
        anchor.font      = _font(bold=bold)
        anchor.alignment = align
```

#### Step 2: Add cargo section renderer after the ROWS loop

Replace the `buf = io.BytesIO()` block (currently right after the ROWS loop) with
the cargo section then the buffer save. The insertion point is after the line
`_cell(r, 9, '')` that closes the ROWS loop and before `buf = io.BytesIO()`:

```python
    # ── Cargo Handled section ────────────────────────────────────────────────
    cargo_start = 3 + len(ROWS)   # first row after ROWS (= row 21 currently)

    def _cargo_section(row_start, period_rows, period_label):
        r = row_start
        n = len(period_rows) + 1  # route rows + 1 total row
        # Column A: period label merged vertically over all rows
        _merge_col(r, r + n - 1, 1, period_label, bold=True, align=_ctr)
        # Route rows
        for route_name, qty in period_rows:
            _cell(r, 2, route_name, align=_left)
            _cell(r, 3, int(round(qty)) if qty else '', align=_ctr)
            for ci in range(4, 10):
                _cell(r, ci, '')
            ws.row_dimensions[r].height = 18
            r += 1
        # Total row
        total = sum(q for _, q in period_rows)
        _cell(r, 2, 'Total:', bold=True, align=_left)
        _cell(r, 3, int(round(total)) if total else '', bold=True, align=_ctr)
        for ci in range(4, 10):
            _cell(r, ci, '')
        ws.row_dimensions[r].height = 18
        r += 1
        return r

    if day_rows or month_rows:
        r = cargo_start
        # Blank separator row
        for ci in range(1, 10):
            _cell(r, ci, '')
        ws.row_dimensions[r].height = 18
        r += 1
        # "Cargo Handled" header — A:C merged, D:I bordered
        _merge_row(r, 1, 3, 'Cargo Handled', bold=True, align=_left)
        for ci in range(4, 10):
            _cell(r, ci, '')
        ws.row_dimensions[r].height = 18
        r += 1
        # For the Day
        if day_rows:
            r = _cargo_section(r, day_rows, 'For the Day')
        # For the Month
        if month_rows:
            r = _cargo_section(r, month_rows, 'For the Month')
```

#### Step 3: Update `_build_excel` signature to accept cargo data

Change the function signature from:
```python
def _build_excel(vessels, report_date, operation_type):
```
to:
```python
def _build_excel(vessels, report_date, operation_type, day_rows=None, month_rows=None):
```

And add these two lines at the top of the function body (after `ws.title = 'Daily Ops'`):
```python
    day_rows   = day_rows   or []
    month_rows = month_rows or []
```

**Step 4: Verify the build runs without error (empty cargo)**

```bash
python -c "
from modules.RP01.RP01.daily_ops.views import _fetch_data, _build_excel
from datetime import date
vessels = _fetch_data(date(2026, 1, 27), 'Import')
buf = _build_excel(vessels, date(2026, 1, 27), 'Import')
print('Excel size bytes:', len(buf.getvalue()))
"
```

Expected: prints a byte count (e.g. `Excel size bytes: 8432`), no error.

---

### Task 4: Thread cargo data through daily_ops_download

**Files:**
- Modify: `modules/RP01/RP01/daily_ops/views.py` — update `daily_ops_download`

**Step 1: Update the download route**

Replace:
```python
    vessels = _fetch_data(report_date, operation_type)
    if not vessels:
        return Response(f'No active {operation_type} vessels on the selected date', status=404)

    buf   = _build_excel(vessels, report_date, operation_type)
```

With:
```python
    vessels = _fetch_data(report_date, operation_type)
    if not vessels:
        return Response(f'No active {operation_type} vessels on the selected date', status=404)

    day_rows, month_rows = _fetch_cargo_handled(report_date, operation_type)
    buf = _build_excel(vessels, report_date, operation_type, day_rows, month_rows)
```

**Step 2: Verify the download route still works end-to-end**

```bash
python -c "
from modules.RP01.RP01.daily_ops.views import _fetch_data, _fetch_cargo_handled, _build_excel
from datetime import date
d = date(2026, 1, 27)
vessels = _fetch_data(d, 'Import')
day_rows, month_rows = _fetch_cargo_handled(d, 'Import')
buf = _build_excel(vessels, d, 'Import', day_rows, month_rows)
print('ok, size:', len(buf.getvalue()))
"
```

Expected: `ok, size: <some number>`

---

### Task 5: Seed lueu_lines test data and verify

**Goal:** Insert sample rows into `lueu_lines` so the Cargo Handled section
renders with real data when the user downloads the 2026-01-27 / Import report.

**Step 1: Check what conveyor routes exist**

```bash
python -c "
from database import get_db, get_cursor
conn = get_db()
cur = get_cursor(conn)
cur.execute('SELECT id, route_name FROM conveyor_routes WHERE is_active=1 ORDER BY id')
print([dict(r) for r in cur.fetchall()])
conn.close()
"
```

If no routes exist, insert two:
```bash
python -c "
from database import get_db, get_cursor
conn = get_db()
cur = get_cursor(conn)
cur.execute(\"INSERT INTO conveyor_routes (route_name, is_active) VALUES ('Conveyor Belt 1', 1), ('Ship Unloader', 1) ON CONFLICT DO NOTHING\")
conn.commit()
conn.close()
print('done')
"
```

**Step 2: Check the operation_type values used in lueu_lines (may differ from 'Import'/'Export')**

After checking conveyor routes, also query vessel_operation_types:
```bash
python -c "
from database import get_db, get_cursor
conn = get_db()
cur = get_cursor(conn)
cur.execute('SELECT DISTINCT name FROM vessel_operation_types ORDER BY name')
print([r['name'] for r in cur.fetchall()])
conn.close()
"
```

If the operation_type values differ from 'Import'/'Export' used as the filter
parameter, update the `_period` query in `_fetch_cargo_handled` to match
(e.g. `ILIKE %s` or remove the filter). Adjust if needed.

**Step 3: Insert sample lueu_lines rows**

Insert rows covering the Jan 26-27 daily window (window_start='2026-01-26 07:00:00',
window_end='2026-01-27 07:00:00') and earlier Jan dates for monthly totals:

```bash
python -c "
from database import get_db, get_cursor
conn = get_db()
cur = get_cursor(conn)

rows = [
    # Daily window rows (2026-01-26 07:00 to 2026-01-27 07:00)
    ('Import', 'Conveyor Belt 1', 3500, '2026-01-26 08:00:00'),
    ('Import', 'Conveyor Belt 1', 2800, '2026-01-26 14:00:00'),
    ('Import', 'Ship Unloader',   4200, '2026-01-26 09:00:00'),
    # Earlier Jan rows (for monthly but not daily)
    ('Import', 'Conveyor Belt 1', 5000, '2026-01-10 08:00:00'),
    ('Import', 'Ship Unloader',   6100, '2026-01-15 10:00:00'),
    ('Import', 'Conveyor Belt 1', 4800, '2026-01-20 11:00:00'),
]
for op, route, qty, st in rows:
    cur.execute('''
        INSERT INTO lueu_lines (operation_type, route_name, quantity, start_time, entry_date)
        VALUES (%s, %s, %s, %s, %s)
    ''', (op, route, qty, st, st[:10]))

conn.commit()
print('Seeded', len(rows), 'rows')
conn.close()
"
```

**Step 4: Verify the fetch returns data**

```bash
python -c "
from modules.RP01.RP01.daily_ops.views import _fetch_cargo_handled
from datetime import date
day_rows, month_rows = _fetch_cargo_handled(date(2026, 1, 27), 'Import')
print('Day rows:  ', day_rows)
print('Month rows:', month_rows)
"
```

Expected:
```
Day rows:   [('Conveyor Belt 1', 6300.0), ('Ship Unloader', 4200.0)]
Month rows: [('Conveyor Belt 1', 16100.0), ('Ship Unloader', 10300.0)]
```

**Step 5: Generate Excel and confirm cargo section appears**

```bash
python -c "
from modules.RP01.RP01.daily_ops.views import _fetch_data, _fetch_cargo_handled, _build_excel
from datetime import date
import os, sys
d = date(2026, 1, 27)
vessels    = _fetch_data(d, 'Import')
day_rows, month_rows = _fetch_cargo_handled(d, 'Import')
buf = _build_excel(vessels, d, 'Import', day_rows, month_rows)
path = 'test_output.xlsx'
open(path, 'wb').write(buf.getvalue())
print('Written to', os.path.abspath(path))
"
```

Open `test_output.xlsx` and confirm:
- Row 21: blank
- Row 22: "Cargo Handled" in column A (merged A:C), columns D-I bordered
- Rows 23+: "For the Day" merged in col A, route names in col B, quantities in col C
- After day rows: "Total:" row
- Then "For the Month" section with monthly totals

**Step 6: Delete test file**

```bash
del test_output.xlsx
```

# Cargo Handled Section — Design Doc
Date: 2026-03-10

## What We're Building

Append a **Cargo Handled** section to the existing Daily Ops Excel (`daily_ops/views.py`)
that shows cargo quantity by receiving route from `lueu_lines`, for two time windows.

## Layout (matches Documentation.xlsx rows 15–23)

```
Row N+1 : blank
Row N+2 : [A:I]  "Cargo Handled"  (merged A:C, bordered A:I)
Row N+3 : [A merged vertically over all day rows]  "For the Day"
           B = route_name  C = quantity  D–I = empty bordered
  ...  (one row per distinct route with data)
Row N+k : B = "Total:"   C = day total
Row N+k+1 : [A merged vertically over all month rows]  "For the Month"
           B = route_name  C = quantity  D–I = empty bordered
  ...
Row last : B = "Total:"   C = month total
```

N = last row used by the vessel section (currently row 20 with 18 data rows).

## Time Windows

Both share the same endpoint:  `window_end = datetime(report_date.year, report_date.month, report_date.day, 7, 0, 0)`

- **Daily**:  `window_start = window_end − 24h`  →  `window_end`
- **Monthly**: `month_start = datetime(report_date.year, report_date.month, 1, 7, 0, 0)` → `window_end`

## Data Query (both periods use same shape)

```sql
SELECT route_name, COALESCE(SUM(quantity), 0) AS qty
FROM lueu_lines
WHERE route_name IS NOT NULL AND route_name != ''
  AND operation_type = %s
  AND start_time >= %s AND start_time < %s
GROUP BY route_name
ORDER BY route_name
```

Parameters: `(operation_type, period_start_str, we_str)`

`start_time` is TEXT stored as ISO datetime — string comparison is valid for ISO format.

## JSON Annual Totals (in views.py, not printed)

```python
# Hardcoded annual totals by fiscal year (stored for reference, not printed)
ANNUAL_ROUTE_TOTALS = {
    "2024-2025": {},   # populate when known
    "2025-2026": {},
}
```

## Styling

Matches existing report: Calibri 11pt, thin borders, `_left` for label cells,
`_ctr` for quantities. Section header bold. "For the Day"/"For the Month" label
merged vertically, bold, center-aligned. Route rows normal weight.

## Files Changed

- `modules/RP01/RP01/daily_ops/views.py`:
  - Add `ANNUAL_ROUTE_TOTALS` dict at module level
  - Add `_fetch_cargo_handled(report_date, operation_type) -> (day_rows, month_rows)`
  - Extend `_build_excel` to append the section after the existing ROWS loop
  - Update `daily_ops_download` to call `_fetch_cargo_handled` and pass data to `_build_excel`

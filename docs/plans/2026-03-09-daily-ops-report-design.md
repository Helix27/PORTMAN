# Daily Port Operations Report — Design

**Date**: 2026-03-09
**Module**: RP01
**Sub-report**: daily_ops

## Overview

A daily Excel report showing all active vessels (Import + Export) at the port for a given date. Vessels are shown side-by-side (up to 5) with key operational figures.

## Excel Layout

- Col A (width 26): Row labels
- Col B–F (width 19 each): One column per active vessel, up to 5
- Col G (width 5): Blank spacer
- Col H (width 27), Col I (width 18): Doc / issue info

| Row | Content |
|-----|---------|
| 1   | Date in A1 \| Title "Daily Report of JSW Dharamtar Port Operation : DD.MM.YYYY" merged B1:G1 \| Doc No in H1 \| Issue Date in I1 |
| 2   | Blank A \| Vessel names "Vessel N: {name}" in B–F |
| 3   | Stevedore / Barge Group |
| 4   | BL Qty |
| 5   | 24 hrs Discharge (7am–7am window) |
| 6   | Discharged / Loaded till Date |
| 7   | Balance on Board / to Load |
| 8   | Vsl Arrived / NOR |
| 9   | Disch Commenced |
| 10  | Disch Completed |
| 11  | Blank row |
| 12  | Stevedore Supervisor |
| 13  | No of Barges |

## Data Logic

**Active vessels** (both Import and Export):
```sql
SELECT h.*, v.importer_exporter_name
FROM ldud_header h
LEFT JOIN vcn_header v ON v.id = h.vcn_id
WHERE h.discharge_commenced IS NOT NULL
  AND h.discharge_commenced < '{report_date} 07:00:00'
  AND (h.discharge_completed IS NULL
       OR h.discharge_completed > '{report_date-1} 07:00:00')
ORDER BY h.discharge_commenced ASC
LIMIT 5
```

- **Stevedore/Barge Group**: `vcn_header.importer_exporter_name`
- **BL Qty**: `SUM(vcn_cargo_declaration.bl_quantity)` for Import, `SUM(vcn_export_cargo_declaration.bl_quantity)` for Export
- **24 hrs Discharge**: `SUM(ldud_vessel_operations.quantity)` where `start_time` in `[(report_date−1) 07:00, report_date 07:00)`
- **Discharged till Date**: `SUM(ldud_vessel_operations.quantity)` where `start_time < report_date 07:00`
- **Balance**: BL Qty − Discharged till Date
- **Vsl Arrived/NOR**: `ldud_header.nor_tendered` formatted `DD-MM-YY HH:MM`
- **Disch Commenced/Completed**: from `ldud_header`
- **Stevedore Supervisor**: `lueu_lines.shift_incharge` for `source_type='LDUD'`, `source_id=ldud_id`, `entry_date=report_date`
- **No of Barges**: `COUNT(DISTINCT barge_name)` from `ldud_barge_lines` where `along_side_vessel` in the 24hr window

## Files

### New
- `modules/RP01/RP01/daily_ops/__init__.py`
- `modules/RP01/RP01/daily_ops/views.py`
- `modules/RP01/RP01/daily_ops/daily_ops.html`

### Modified
- `modules/RP01/RP01/views.py` — add import for daily_ops views
- `modules/RP01/RP01/rp01.html` — add report card

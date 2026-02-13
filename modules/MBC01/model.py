from database import get_db, get_cursor
from datetime import datetime


def get_next_doc_num(doc_series):
    """Get next doc number for given series"""
    conn = get_db()
    cur = get_cursor(conn)
    prefix = doc_series.replace('-', '') if doc_series else 'MBC'
    cur.execute(
        "SELECT MAX(CAST(SUBSTR(doc_num, LENGTH(%s) + 1) AS INTEGER)) FROM mbc_header WHERE doc_num LIKE %s",
        [prefix, f"{prefix}%"]
    )
    result = cur.fetchone()['max']
    conn.close()
    next_num = (result or 0) + 1
    return f"{prefix}{next_num:04d}"


def get_data(page=1, size=20):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT COUNT(*) FROM mbc_header')
    total = cur.fetchone()['count']
    cur.execute('SELECT * FROM mbc_header ORDER BY id DESC LIMIT %s OFFSET %s', (size, (page-1)*size))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def save_header(data):
    conn = get_db()
    cur = get_cursor(conn)
    row_id = data.get('id')

    # Auto-set doc_date if not provided
    if not data.get('doc_date'):
        data['doc_date'] = datetime.now().strftime('%Y-%m-%d')

    if row_id:
        cols = [k for k in data if k not in ['id', 'doc_num']]
        cur.execute(f"UPDATE mbc_header SET {', '.join([f'{c}=%s' for c in cols])} WHERE id=%s",
                   [data[c] for c in cols] + [row_id])
    else:
        data['doc_num'] = get_next_doc_num(data.get('doc_series', ''))
        cols = [k for k in data if k != 'id']
        cur.execute(f"INSERT INTO mbc_header ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING id",
                   [data[c] for c in cols])
        row_id = cur.fetchone()['id']

    conn.commit()
    conn.close()
    return row_id, data.get('doc_num')


def delete_header(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM mbc_header WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Delays sub-table operations
def get_delays(mbc_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM mbc_delays WHERE mbc_id=%s ORDER BY id DESC', (mbc_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_delay(data):
    conn = get_db()
    cur = get_cursor(conn)

    # Calculate total time
    total_mins = None
    total_hrs = None
    if data.get('start_datetime') and data.get('end_datetime'):
        try:
            start = datetime.fromisoformat(data['start_datetime'])
            end = datetime.fromisoformat(data['end_datetime'])
            diff = (end - start).total_seconds()
            total_mins = round(diff / 60, 2)
            total_hrs = round(diff / 3600, 2)
        except:
            pass

    if data.get('id'):
        cur.execute('''UPDATE mbc_delays SET delay_name=%s, delay_account_type=%s, equipment_name=%s,
                      start_datetime=%s, end_datetime=%s, total_time_mins=%s, total_time_hrs=%s,
                      delays_to_sof=%s, invoiceable=%s, minus_delay_hours=%s WHERE id=%s''',
                   [data.get('delay_name'), data.get('delay_account_type'), data.get('equipment_name'),
                    data.get('start_datetime'), data.get('end_datetime'), total_mins, total_hrs,
                    data.get('delays_to_sof'), data.get('invoiceable'), data.get('minus_delay_hours'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO mbc_delays (mbc_id, delay_name, delay_account_type, equipment_name,
                      start_datetime, end_datetime, total_time_mins, total_time_hrs, delays_to_sof, invoiceable, minus_delay_hours)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['mbc_id'], data.get('delay_name'), data.get('delay_account_type'), data.get('equipment_name'),
                    data.get('start_datetime'), data.get('end_datetime'), total_mins, total_hrs,
                    data.get('delays_to_sof'), data.get('invoiceable'), data.get('minus_delay_hours')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id, total_mins, total_hrs


def delete_delay(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM mbc_delays WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Load Port Lines sub-table operations
def get_load_port_lines(mbc_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM mbc_load_port_lines WHERE mbc_id=%s ORDER BY id DESC', (mbc_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_load_port_line(data):
    conn = get_db()
    cur = get_cursor(conn)

    if data.get('id'):
        cur.execute('''UPDATE mbc_load_port_lines SET
                      arrived_load_port=%s, alongside_berth=%s, loading_commenced=%s,
                      loading_completed=%s, cast_off_load_port=%s
                      WHERE id=%s''',
                   [data.get('arrived_load_port'), data.get('alongside_berth'), data.get('loading_commenced'),
                    data.get('loading_completed'), data.get('cast_off_load_port'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO mbc_load_port_lines
                      (mbc_id, arrived_load_port, alongside_berth, loading_commenced, loading_completed, cast_off_load_port)
                      VALUES (%s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['mbc_id'], data.get('arrived_load_port'), data.get('alongside_berth'),
                    data.get('loading_commenced'), data.get('loading_completed'), data.get('cast_off_load_port')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_load_port_line(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM mbc_load_port_lines WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()


# Discharge Port Lines sub-table operations
def get_discharge_port_lines(mbc_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('SELECT * FROM mbc_discharge_port_lines WHERE mbc_id=%s ORDER BY id DESC', (mbc_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_discharge_port_line(data):
    conn = get_db()
    cur = get_cursor(conn)

    if data.get('id'):
        cur.execute('''UPDATE mbc_discharge_port_lines SET
                      arrival_gull_island=%s, departure_gull_island=%s, vessel_arrival_port=%s,
                      vessel_all_made_fast=%s, unloading_commenced=%s, cleaning_commenced=%s,
                      unloading_completed=%s, vessel_cast_off=%s, vessel_unloaded_by=%s,
                      vessel_unloading_berth=%s, discharge_stop_shifting=%s, discharge_start_shifting=%s
                      WHERE id=%s''',
                   [data.get('arrival_gull_island'), data.get('departure_gull_island'), data.get('vessel_arrival_port'),
                    data.get('vessel_all_made_fast'), data.get('unloading_commenced'), data.get('cleaning_commenced'),
                    data.get('unloading_completed'), data.get('vessel_cast_off'), data.get('vessel_unloaded_by'),
                    data.get('vessel_unloading_berth'), data.get('discharge_stop_shifting'),
                    data.get('discharge_start_shifting'), data['id']])
        row_id = data['id']
    else:
        cur.execute('''INSERT INTO mbc_discharge_port_lines
                      (mbc_id, arrival_gull_island, departure_gull_island, vessel_arrival_port,
                       vessel_all_made_fast, unloading_commenced, cleaning_commenced, unloading_completed,
                       vessel_cast_off, vessel_unloaded_by, vessel_unloading_berth,
                       discharge_stop_shifting, discharge_start_shifting)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                   [data['mbc_id'], data.get('arrival_gull_island'), data.get('departure_gull_island'),
                    data.get('vessel_arrival_port'), data.get('vessel_all_made_fast'),
                    data.get('unloading_commenced'), data.get('cleaning_commenced'),
                    data.get('unloading_completed'), data.get('vessel_cast_off'),
                    data.get('vessel_unloaded_by'), data.get('vessel_unloading_berth'),
                    data.get('discharge_stop_shifting'), data.get('discharge_start_shifting')])
        row_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return row_id


def delete_discharge_port_line(row_id):
    conn = get_db()
    cur = get_cursor(conn)
    cur.execute('DELETE FROM mbc_discharge_port_lines WHERE id=%s', (row_id,))
    conn.commit()
    conn.close()

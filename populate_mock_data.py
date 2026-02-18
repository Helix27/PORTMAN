"""
Mock Data Population Script for PORTMAN (PostgreSQL version)
Run this script after running migrations to populate sample data.
Usage: python populate_mock_data.py
"""

import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import random
from config import DATABASE_URL

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def clear_mock_data():
    """Clear all mock/transactional data in correct FK order, preserving seed data from migrations"""
    conn = get_db()
    cur = conn.cursor()

    # Order matters: child tables first, then parents
    tables_to_clear = [
        # Service records (EAV)
        'service_record_values',
        'service_records',
        'service_field_definitions',
        # Invoices → Bills → EU lines
        'invoice_lines',
        'invoice_header',
        'bill_lines',
        'bill_header',
        # EU lines
        'eu_lines',
        # MBC subtables → header
        'mbc_delays',
        'mbc_discharge_port_lines',
        'mbc_load_port_lines',
        'mbc_header',
        # LDUD subtables → header
        'ldud_delays',
        'ldud_barge_lines',
        'ldud_header',
        # VCN subtables → header
        'vcn_delays',
        'vcn_stowage_plan',
        'vcn_igm',
        'vcn_cargo_declaration',
        'vcn_anchorage',
        'vcn_nominations',
        'vcn_header',
        # Agreement lines → header
        'customer_agreement_lines',
        'customer_agreements',
        # Currency exchange rates
        'currency_exchange_rates',
        # Vessels
        'vessels',
        # Master tables (populated by this script, not by migrations)
        'conveyor_routes',
        'port_berth_master',
        'mbc_master',
        'vessel_cargo',
        'vessel_delay_types',
        'vessel_run_types',
        'vessel_type_of_discharge',
        'vessel_call_doc_series',
        'vessel_operation_types',
        'vessel_customers',
        'vessel_importer_exporters',
        'vessel_agents',
        'gears',
        'vessel_categories',
        'vessel_types',
    ]

    cleared = 0
    for table in tables_to_clear:
        try:
            cur.execute(f'DELETE FROM {table}')
            count = cur.rowcount
            if count > 0:
                cleared += count
        except Exception as e:
            conn.rollback()
            print(f"  [WARN] Could not clear {table}: {e}")
            continue

    # Reset has_custom_fields on service types (seed data, just reset the flag)
    try:
        cur.execute("UPDATE finance_service_types SET has_custom_fields = 0")
    except Exception:
        pass

    conn.commit()
    conn.close()
    print(f"[OK] Cleared {cleared} rows of mock data across {len(tables_to_clear)} tables")

def populate_vessel_agents():
    """VAM01 - Vessel Agent Master"""
    agents = [
        'Maersk Agency Services',
        'Mediterranean Shipping Agency',
        'CMA CGM Agencies',
        'Hapag-Lloyd Agency',
        'COSCO Shipping Agency',
        'Evergreen Marine Agency',
        'ONE Ocean Network Agency',
        'Yang Ming Agency',
        'ZIM Integrated Shipping',
        'PIL Pacific International'
    ]
    conn = get_db()
    cur = conn.cursor()
    for agent in agents:
        cur.execute('INSERT INTO vessel_agents (name) VALUES (%s) ON CONFLICT DO NOTHING', [agent])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(agents)} vessel agents")

def populate_importer_exporters():
    """VIEM01 - Vessel Importer/Exporter Master with GST details"""
    companies = [
        ('Amba River Coke Limited', '27AAACAR1234E1ZV', '27', 'Maharashtra', 'AAACAR1234E', 'Amba River Coke Plant, Raigad', 'Raigad', '402125', '02192-245000', 'accounts@ambariver.in'),
        ('JSW Steel Dolvi Limited', '27AAACJ5678D1ZH', '27', 'Maharashtra', 'AAACJ5678D', 'JSW Steel Plant, Dolvi, Raigad', 'Raigad', '402201', '02192-277777', 'finance@jswdolvi.in')
    ]
    conn = get_db()
    cur = conn.cursor()
    for name, gstin, state_code, state_name, pan, address, city, pincode, phone, email in companies:
        cur.execute('''INSERT INTO vessel_importer_exporters
            (name, gstin, gst_state_code, gst_state_name, pan, billing_address, city, pincode, contact_phone, contact_email, gl_code, default_currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING''',
            [name, gstin, state_code, state_name, pan, address, city, pincode, phone, email, f'1200{state_code}', 'INR'])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(companies)} importer/exporters with GST details")

def populate_customers():
    """VCUM01 - Vessel Customer Master with GST details"""
    customers = [
        ('Amba River Coke Limited', '27AAACAR1234E1ZV', '27', 'Maharashtra', 'AAACAR1234E', 'Amba River Coke Plant, Raigad', 'Raigad', '402125', '02192-245000', 'accounts@ambariver.in'),
        ('JSW Steel Dolvi Limited', '27AAACJ5678D1ZH', '27', 'Maharashtra', 'AAACJ5678D', 'JSW Steel Plant, Dolvi, Raigad', 'Raigad', '402201', '02192-277777', 'finance@jswdolvi.in')
    ]
    conn = get_db()
    cur = conn.cursor()
    for name, gstin, state_code, state_name, pan, address, city, pincode, phone, email in customers:
        cur.execute('''INSERT INTO vessel_customers
            (name, gstin, gst_state_code, gst_state_name, pan, billing_address, city, pincode, contact_phone, contact_email, gl_code, default_currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING''',
            [name, gstin, state_code, state_name, pan, address, city, pincode, phone, email, f'1100{state_code}', 'INR'])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(customers)} customers with GST details")

def populate_operation_types():
    """VOT01 - Vessel Operation Type Master"""
    operations = ['Import', 'Export', 'Transshipment', 'Coastal', 'Bunker Only', 'Repair', 'Lay-up', 'STS Transfer']
    conn = get_db()
    cur = conn.cursor()
    for op in operations:
        cur.execute('INSERT INTO vessel_operation_types (name) VALUES (%s) ON CONFLICT DO NOTHING', [op])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(operations)} operation types")

def populate_doc_series():
    """VCDS01 - Vessel Call Doc Series Master"""
    series = ['VCN/24-25', 'VCN/25-26', 'VCN/26-27', 'IMP/24-25', 'EXP/24-25', 'CST/24-25']
    conn = get_db()
    cur = conn.cursor()
    for s in series:
        cur.execute('INSERT INTO vessel_call_doc_series (name) VALUES (%s) ON CONFLICT DO NOTHING', [s])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(series)} doc series")

def populate_discharge_types():
    """VTOD01 - Type of Discharge Master"""
    types = ['Full Discharge', 'Part Discharge', 'Direct Delivery', 'Warehouse Storage', 'Transhipment', 'Lighterage']
    conn = get_db()
    cur = conn.cursor()
    for t in types:
        cur.execute('INSERT INTO vessel_type_of_discharge (name) VALUES (%s) ON CONFLICT DO NOTHING', [t])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(types)} discharge types")

def populate_run_types():
    """VRT01 - Vessel Run Type Master"""
    types = ['Coastal', 'Foreign Going', 'Overseas', 'Domestic', 'International']
    conn = get_db()
    cur = conn.cursor()
    for t in types:
        cur.execute('INSERT INTO vessel_run_types (name) VALUES (%s) ON CONFLICT DO NOTHING', [t])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(types)} run types")

def populate_delay_types():
    """VDM01 - Vessel Delay Master"""
    delays = [
        'Weather Delay', 'Port Congestion', 'Berth Unavailability', 'Tidal Restrictions',
        'Cargo Not Ready', 'Documentation Delay', 'Customs Clearance', 'Equipment Breakdown',
        'Labor Strike', 'Pilotage Delay', 'Tug Unavailability'
    ]
    conn = get_db()
    cur = conn.cursor()
    for d in delays:
        cur.execute('INSERT INTO vessel_delay_types (name) VALUES (%s) ON CONFLICT DO NOTHING', [d])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(delays)} delay types")

def populate_cargo_master():
    """VCG01 - Vessel Cargo Master (Hierarchical)"""
    cargo_data = [
        # Bulk Cargo
        ('Bulk', 'Coal', 'Thermal Coal'), ('Bulk', 'Coal', 'Coking Coal'), ('Bulk', 'Coal', 'Anthracite'),
        ('Bulk', 'Iron Ore', 'Lump Ore'), ('Bulk', 'Iron Ore', 'Iron Ore Fines'), ('Bulk', 'Iron Ore', 'Iron Ore Pellets'),
        ('Bulk', 'Grain', 'Wheat'), ('Bulk', 'Grain', 'Rice'), ('Bulk', 'Grain', 'Corn'), ('Bulk', 'Grain', 'Soybean'),
        ('Bulk', 'Fertilizer', 'Urea'), ('Bulk', 'Fertilizer', 'DAP'), ('Bulk', 'Fertilizer', 'MOP'),
        ('Bulk', 'Minerals', 'Bauxite'), ('Bulk', 'Minerals', 'Limestone'), ('Bulk', 'Minerals', 'Manganese Ore'),
        # Liquid Cargo
        ('Liquid', 'Crude Oil', 'Brent Crude'), ('Liquid', 'Crude Oil', 'WTI Crude'), ('Liquid', 'Crude Oil', 'Dubai Crude'),
        ('Liquid', 'Petroleum Products', 'Diesel'), ('Liquid', 'Petroleum Products', 'Petrol'),
        ('Liquid', 'Petroleum Products', 'Jet Fuel'), ('Liquid', 'Petroleum Products', 'Naphtha'),
        ('Liquid', 'Chemicals', 'Methanol'), ('Liquid', 'Chemicals', 'Caustic Soda'),
        ('Liquid', 'LNG', 'Liquefied Natural Gas'), ('Liquid', 'LPG', 'Liquefied Petroleum Gas'),
        # Container/Break Bulk
        ('Container', 'General', 'Mixed Cargo'), ('Container', 'General', 'Consumer Goods'),
        ('Container', 'Reefer', 'Frozen Food'), ('Container', 'Reefer', 'Pharmaceuticals'),
        ('Break Bulk', 'Steel', 'Steel Coils'), ('Break Bulk', 'Steel', 'Steel Plates'),
        ('Break Bulk', 'Machinery', 'Heavy Equipment'), ('Break Bulk', 'Timber', 'Logs')
    ]
    conn = get_db()
    cur = conn.cursor()
    for cargo_type, cargo_category, cargo_name in cargo_data:
        cur.execute('INSERT INTO vessel_cargo (cargo_type, cargo_category, cargo_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                    [cargo_type, cargo_category, cargo_name])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(cargo_data)} cargo entries")

def populate_vessel_types():
    """VTM01 - Vessel Type Master"""
    types = ['Bulk Carrier', 'Container Ship', 'Tanker', 'General Cargo', 'Ro-Ro', 'LNG Carrier', 'LPG Carrier', 'Chemical Tanker', 'Car Carrier', 'Reefer Vessel']
    conn = get_db()
    cur = conn.cursor()
    for t in types:
        cur.execute('INSERT INTO vessel_types (name) VALUES (%s) ON CONFLICT DO NOTHING', [t])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(types)} vessel types")

def populate_vessel_categories():
    """VCM01 - Vessel Category Master"""
    categories = ['Handysize', 'Handymax', 'Supramax', 'Panamax', 'Capesize', 'VLCC', 'ULCC', 'Aframax', 'Suezmax', 'Post-Panamax']
    conn = get_db()
    cur = conn.cursor()
    for c in categories:
        cur.execute('INSERT INTO vessel_categories (name) VALUES (%s) ON CONFLICT DO NOTHING', [c])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(categories)} vessel categories")

def populate_gears():
    """GM01 - Gear Master"""
    gears = ['Geared', 'Gearless', 'Self-Unloader', 'Crane Equipped']
    conn = get_db()
    cur = conn.cursor()
    for g in gears:
        cur.execute('INSERT INTO gears (name) VALUES (%s) ON CONFLICT DO NOTHING', [g])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(gears)} gear types")

def populate_vessels():
    """VC01 - Vessel Creation"""
    vessels = [
        ('MV Ocean Star', '9441362', 'Bulk Carrier', 'Handymax', 'Geared', 45000, 190, 32, 2015),
        ('MV Pacific Glory', '9523871', 'Bulk Carrier', 'Panamax', 'Gearless', 75000, 225, 32, 2018),
        ('MV Atlantic Dream', '9612384', 'Container Ship', 'Post-Panamax', 'Gearless', 95000, 366, 48, 2020),
        ('MT Crude Pioneer', '9387156', 'Tanker', 'Aframax', 'Gearless', 105000, 250, 44, 2012),
        ('MV Steel Express', '9456723', 'General Cargo', 'Handysize', 'Geared', 28000, 170, 27, 2016),
        ('MV Coastal Runner', '9534126', 'Bulk Carrier', 'Supramax', 'Geared', 58000, 200, 32, 2019),
        ('MT Chemical Star', '9478923', 'Chemical Tanker', 'Handymax', 'Gearless', 40000, 183, 32, 2017),
        ('MV Iron Maiden', '9567234', 'Bulk Carrier', 'Capesize', 'Gearless', 180000, 292, 45, 2021),
        ('MV Green Horizon', '9623451', 'LNG Carrier', 'VLCC', 'Gearless', 160000, 295, 46, 2022),
        ('MV Trade Wind', '9512367', 'Container Ship', 'Panamax', 'Gearless', 65000, 294, 32, 2014)
    ]
    conn = get_db()
    cur = get_cursor(conn)

    for i, (name, imo, vtype, vcat, gear, gt, loa, beam, year) in enumerate(vessels, 1):
        doc_num = f'VM{i}'
        cur.execute('''
            INSERT INTO vessels
            (doc_num, vessel_name, imo_num, vessel_type_name, vessel_category_name, gear, gt, loa, beam, year_of_built, created_by, created_date, doc_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'admin', %s, 'Approved')
            ON CONFLICT DO NOTHING
        ''', [doc_num, name, imo, vtype, vcat, gear, gt, loa, beam, year, datetime.now().strftime('%Y-%m-%d')])

    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(vessels)} vessels")

def populate_mbc_master():
    """MBCM01 - MBC Master"""
    mbcs = [('JSW Raigad', 8200), ('JSW Manikgad', 7800), ('JSW Devgad', 8500)]
    conn = get_db()
    cur = conn.cursor()
    for mbc_name, dwt in mbcs:
        cur.execute('INSERT INTO mbc_master (mbc_name, dwt) VALUES (%s, %s) ON CONFLICT DO NOTHING', [mbc_name, dwt])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(mbcs)} MBC entries")

def populate_port_berths():
    """PBM01 - Port Berth Master"""
    berths = [
        ('Berth 1', 'North Terminal', 'Deep water berth for large vessels'),
        ('Berth 2', 'North Terminal', 'Bulk cargo operations'),
        ('Berth 3', 'South Terminal', 'Container handling'),
        ('Berth 4', 'South Terminal', 'General cargo'),
        ('Berth 5', 'East Terminal', 'Tanker operations'),
        ('Berth 6', 'East Terminal', 'Chemical tankers'),
        ('Berth 7', 'West Terminal', 'Ro-Ro operations'),
        ('Berth 8', 'West Terminal', 'Break bulk cargo')
    ]
    conn = get_db()
    cur = conn.cursor()
    for berth_name, location, remarks in berths:
        cur.execute('INSERT INTO port_berth_master (berth_name, berth_location, remarks) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING',
                    [berth_name, location, remarks])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(berths)} port berths")

def populate_conveyor_routes():
    """CRM01 - Conveyor Route Master"""
    routes = [
        ('Route A - North Berth to Stockyard 1', 'Main conveyor route from north berth'),
        ('Route B - South Berth to Stockyard 2', 'Secondary route from south terminal'),
        ('Route C - East Terminal to Processing', 'Processing plant direct route'),
        ('Route D - West Terminal to Export', 'Export loading route'),
    ]
    conn = get_db()
    cur = conn.cursor()
    for route_name, description in routes:
        cur.execute('''
            INSERT INTO conveyor_routes (route_name, description, is_active, created_by, created_date)
            VALUES (%s, %s, 1, 'admin', %s) ON CONFLICT DO NOTHING
        ''', [route_name, description, datetime.now().strftime('%Y-%m-%d')])
    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(routes)} conveyor routes")

def populate_finance_currencies():
    """FCRM01 - Currency Exchange Rates"""
    conn = get_db()
    cur = conn.cursor()

    base_date = datetime.now()
    rates = [
        ('USD', 'INR', 83.25, (base_date - timedelta(days=1)).strftime('%Y-%m-%d')),
        ('EUR', 'INR', 90.50, (base_date - timedelta(days=1)).strftime('%Y-%m-%d')),
        ('GBP', 'INR', 105.75, (base_date - timedelta(days=1)).strftime('%Y-%m-%d')),
        ('AED', 'INR', 22.65, (base_date - timedelta(days=1)).strftime('%Y-%m-%d')),
        ('INR', 'USD', 0.012, (base_date - timedelta(days=1)).strftime('%Y-%m-%d')),
    ]

    for from_curr, to_curr, rate, eff_date in rates:
        cur.execute('''INSERT INTO currency_exchange_rates
            (from_currency, to_currency, exchange_rate, effective_date, is_active)
            VALUES (%s, %s, %s, %s, 1) ON CONFLICT DO NOTHING''', [from_curr, to_curr, rate, eff_date])

    conn.commit()
    conn.close()
    print(f"[OK] Populated {len(rates)} currency exchange rates")


def populate_customer_agreements():
    """FCAM01 - Customer Agreements with Service Lines"""
    conn = get_db()
    cur = get_cursor(conn)

    # Get customers
    cur.execute("SELECT id, name FROM vessel_customers LIMIT 2")
    customers = cur.fetchall()

    if not customers:
        print("[SKIP] No customers found - run populate_customers() first")
        conn.close()
        return

    # Get service types
    cur.execute("SELECT id, service_code, service_name, uom FROM finance_service_types WHERE is_active = 1")
    service_types = cur.fetchall()

    if not service_types:
        print("[SKIP] No service types found - seed data not loaded")
        conn.close()
        return

    agreement_count = 0
    for idx, customer in enumerate(customers, 1):
        valid_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        valid_to = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

        # Create agreement header
        cur.execute("""
            INSERT INTO customer_agreements (agreement_code, customer_type, customer_id, customer_name,
                                             agreement_name, currency_code, valid_from, valid_to,
                                             is_active, agreement_status, created_by, created_date,
                                             approved_by, approved_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, [f'AGR2526{idx:03d}', 'Customer', customer['id'], customer['name'],
              f'{customer["name"]} - FY 2025-26 Agreement', 'INR', valid_from, valid_to,
              1, 'Approved', 'admin', datetime.now().strftime('%Y-%m-%d'),
              'approver', datetime.now().strftime('%Y-%m-%d')])
        agreement_id = cur.fetchone()['id']

        # Add service lines - cargo handling rates
        service_rates = {
            'CHGL01': 45.00,  # Cargo Handling Loading
            'CHGU01': 42.50,  # Cargo Handling Unloading
            'EQP001': 850.00, # Equipment Rental per hour
            'STO001': 25.00,  # Storage per day
            'CON001': 38.00,  # Conveyor charges per MT
        }

        for service in service_types:
            if service['service_code'] in service_rates:
                rate = service_rates[service['service_code']]
                cur.execute("""
                    INSERT INTO customer_agreement_lines (agreement_id, service_type_id, service_name,
                                                          rate, uom, currency_code, min_charge, max_charge)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, [agreement_id, service['id'], service['service_name'],
                      rate, service['uom'], 'INR', rate * 100, rate * 50000])

        agreement_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {agreement_count} customer agreements with service lines")

def populate_vcn_records():
    """VCN01 - Vessel Call Notifications with subtables"""
    conn = get_db()
    cur = get_cursor(conn)

    # Get vessel IDs from vessels table
    cur.execute('SELECT id, doc_num, vessel_name FROM vessels ORDER BY id LIMIT 3')
    vessels = cur.fetchall()

    if not vessels:
        conn.close()
        print("[SKIP] No vessels found - run populate_vessels() first")
        return

    vcn_count = 0
    for idx, vessel in enumerate(vessels, 1):
        # Create VCN header with correct column names
        vessel_master_doc = f"{vessel['doc_num']}/{vessel['vessel_name']}"
        vessel_name = vessel['vessel_name']
        importer_exporter_name = 'Amba River Coke Limited' if idx % 2 else 'JSW Steel Dolvi Limited'
        doc_date = datetime.now().strftime('%Y-%m-%d')

        cur.execute("""
            INSERT INTO vcn_header (vcn_doc_num, vessel_master_doc, vessel_name, vessel_agent_name,
                                    importer_exporter_name, customer_name, operation_type, cargo_type,
                                    doc_date, doc_status, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, [f'VCN{idx}', vessel_master_doc, vessel_name, 'Maersk Agency Services',
              importer_exporter_name, importer_exporter_name, 'Import', 'Bulk',
              doc_date, 'Approved', 'admin', doc_date])
        vcn_id = cur.fetchone()['id']

        # Add nomination
        base_date = datetime.now() + timedelta(days=idx*5)
        cur.execute("""
            INSERT INTO vcn_nominations (vcn_id, eta, etd, vessel_run_type)
            VALUES (%s, %s, %s, %s)
        """, [vcn_id, base_date.strftime('%Y-%m-%dT10:00'),
              (base_date + timedelta(days=2)).strftime('%Y-%m-%dT18:00'), 'Foreign Going'])

        # Add anchorage
        cur.execute("""
            INSERT INTO vcn_anchorage (vcn_id, latitude, longitude, anchored_time)
            VALUES (%s, %s, %s, %s)
        """, [vcn_id, f'18.{950+idx}', f'72.{830+idx}', base_date.strftime('%Y-%m-%dT08:00')])

        # Add cargo declaration
        cargo_name = ['Thermal Coal', 'Iron Ore Fines', 'Coking Coal'][idx % 3]
        cur.execute("""
            INSERT INTO vcn_cargo_declaration (vcn_id, cargo_name, bl_no, bl_date, bl_quantity, quantity_uom)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [vcn_id, cargo_name, f'BL{idx}001', base_date.strftime('%Y-%m-%d'), 50000 + idx*5000, 'MT'])

        # Add IGM
        cur.execute("""
            INSERT INTO vcn_igm (vcn_id, igm_number, igm_manual_number, igm_date, dwt, bl_quantity)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [vcn_id, f'IGM{idx}', f'IGM/2026/{idx}', base_date.strftime('%Y-%m-%d'),
              75000 + idx*5000, 50000 + idx*5000])

        # Add stowage plan
        for hatch_num in range(1, 4):
            cur.execute("""
                INSERT INTO vcn_stowage_plan (vcn_id, cargo_name, hatch_name, hold_name, hatchwise_quantity)
                VALUES (%s, %s, %s, %s, %s)
            """, [vcn_id, cargo_name, f'Hatch {hatch_num}', f'Hold {hatch_num}',
                  (50000 + idx*5000) // 3])

        # Add delay
        delay_start = base_date + timedelta(hours=12)
        cur.execute("""
            INSERT INTO vcn_delays (vcn_id, delay_name, delay_start, delay_end)
            VALUES (%s, %s, %s, %s)
        """, [vcn_id, 'Weather Delay', delay_start.strftime('%Y-%m-%dT%H:%M'),
              (delay_start + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')])

        vcn_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {vcn_count} VCN records with subtables (nominations, anchorage, cargo, IGM, stowage, delays)")


def populate_ldud_records():
    """LDUD01 - Lighter/Discharge/Unload Data with subtables"""
    conn = get_db()
    cur = get_cursor(conn)

    # Get VCN records
    cur.execute("SELECT id, vcn_doc_num, vessel_name FROM vcn_header WHERE doc_status = 'Approved' LIMIT 2")
    vcns = cur.fetchall()

    if not vcns:
        conn.close()
        print("[SKIP] No approved VCN records found - run populate_vcn_records() first")
        return

    # Get cargo names
    cur.execute("SELECT DISTINCT cargo_name FROM vcn_cargo_declaration LIMIT 2")
    cargos = [r['cargo_name'] for r in cur.fetchall()]

    ldud_count = 0
    for idx, vcn in enumerate(vcns, 1):
        # Create LDUD header with correct columns (no cargo_name in ldud_header)
        base_date = datetime.now() + timedelta(days=idx*7)
        cargo_name = cargos[idx % len(cargos)] if cargos else 'Thermal Coal'

        cur.execute("""
            INSERT INTO ldud_header (doc_num, vcn_id, vcn_doc_num, vessel_name,
                                     doc_status, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, [f'LDUD{idx}', vcn['id'], vcn['vcn_doc_num'], vcn['vessel_name'],
              'Approved', 'admin', datetime.now().strftime('%Y-%m-%d')])
        ldud_id = cur.fetchone()['id']

        # Add barge lines with trip numbers
        barges = ['Radha Krishna 1', 'Radha Krishna 2', 'Aisha 1']
        for trip, barge in enumerate(barges, 1):
            loading_start = base_date + timedelta(hours=trip*8)
            cur.execute("""
                INSERT INTO ldud_barge_lines (ldud_id, trip_number, hold_name, barge_name, contractor_name, cargo_name,
                                              along_side_vessel, commenced_loading, completed_loading, cast_off_mv,
                                              along_side_berth, commence_discharge_berth, completed_discharge_berth,
                                              cast_off_berth, discharge_quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [ldud_id, trip, f'Hold {trip}', barge, 'Marine Services Ltd',
                  cargos[idx % len(cargos)] if cargos else 'Thermal Coal',
                  loading_start.strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=4, minutes=30)).strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=7)).strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=10)).strftime('%Y-%m-%dT%H:%M'),
                  (loading_start + timedelta(hours=10, minutes=30)).strftime('%Y-%m-%dT%H:%M'),
                  2800 + trip*100])

        # Add delays
        delay_start = base_date + timedelta(hours=15)
        cur.execute("""
            INSERT INTO ldud_delays (ldud_id, delay_name, delay_account_type, equipment_name, start_datetime, end_datetime,
                                     total_time_mins, total_time_hrs, delays_to_sof, invoiceable, minus_delay_hours)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [ldud_id, 'Port Congestion', 'Port Account', 'Grab Crane',
              delay_start.strftime('%Y-%m-%dT%H:%M'),
              (delay_start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
              120, 2.0, 1, 0, 0])

        ldud_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {ldud_count} LDUD records with subtables (barge lines, delays)")


def populate_mbc_records():
    """MBC01 - Mother Barge Cargo with subtables"""
    conn = get_db()
    cur = get_cursor(conn)

    # Get MBC master records
    cur.execute("SELECT mbc_name, dwt FROM mbc_master LIMIT 2")
    mbcs = cur.fetchall()

    if not mbcs:
        conn.close()
        print("[SKIP] No MBC master records found - run populate_mbc_master() first")
        return

    mbc_count = 0
    for idx, mbc_master in enumerate(mbcs, 1):
        doc_date = datetime.now() + timedelta(days=idx*10)

        # Create MBC header with correct columns
        cur.execute("""
            INSERT INTO mbc_header (doc_num, doc_series, doc_date, mbc_name, operation_type, cargo_type,
                                    cargo_name, bl_quantity, quantity_uom, doc_status, created_by, created_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, [f'MBC2526000{idx}', 'MBC25-26', doc_date.strftime('%Y-%m-%d'), mbc_master['mbc_name'],
              'Import', 'Bulk', 'Thermal Coal', 5000 + idx*500, 'MT',
              'Approved', 'admin', datetime.now().strftime('%Y-%m-%d')])
        mbc_id = cur.fetchone()['id']

        # Add load port line
        load_start = doc_date + timedelta(hours=6)
        cur.execute("""
            INSERT INTO mbc_load_port_lines (mbc_id, arrived_load_port, alongside_berth, loading_commenced,
                                             loading_completed, cast_off_load_port)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [mbc_id, load_start.strftime('%Y-%m-%dT%H:%M'),
              (load_start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
              (load_start + timedelta(hours=1, minutes=30)).strftime('%Y-%m-%dT%H:%M'),
              (load_start + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M'),
              (load_start + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%dT%H:%M')])

        # Add discharge port line
        discharge_start = load_start + timedelta(hours=8)
        cur.execute("""
            INSERT INTO mbc_discharge_port_lines (mbc_id, arrival_gull_island, departure_gull_island, vessel_arrival_port,
                                                   vessel_all_made_fast, unloading_commenced, unloading_completed,
                                                   vessel_cast_off, vessel_unloaded_by, vessel_unloading_berth)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [mbc_id, discharge_start.strftime('%Y-%m-%dT%H:%M'),
              (discharge_start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
              (discharge_start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
              (discharge_start + timedelta(hours=2, minutes=30)).strftime('%Y-%m-%dT%H:%M'),
              (discharge_start + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'),
              (discharge_start + timedelta(hours=7)).strftime('%Y-%m-%dT%H:%M'),
              (discharge_start + timedelta(hours=7, minutes=30)).strftime('%Y-%m-%dT%H:%M'),
              'Conveyor', 'Berth 1'])

        # Add delay
        delay_start = discharge_start + timedelta(hours=4)
        cur.execute("""
            INSERT INTO mbc_delays (mbc_id, delay_name, delay_account_type, equipment_name, start_datetime, end_datetime,
                                    total_time_mins, total_time_hrs, delays_to_sof, invoiceable, minus_delay_hours)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [mbc_id, 'Equipment Breakdown', 'Port Account', 'Conveyor Belt',
              delay_start.strftime('%Y-%m-%dT%H:%M'),
              (delay_start + timedelta(minutes=45)).strftime('%Y-%m-%dT%H:%M'),
              45, 0.75, 1, 0, 0])

        mbc_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {mbc_count} MBC records with subtables (load port, discharge port, delays)")


def populate_eu_records():
    """EU01 - Equipment Utilization (critical for billing)"""
    conn = get_db()
    cur = get_cursor(conn)
    eu_count = 0

    # Get VCN records
    cur.execute("SELECT id, vcn_doc_num, vessel_name FROM vcn_header WHERE doc_status = 'Approved' LIMIT 3")
    vcns = cur.fetchall()

    # Create EU entries for VCN operations
    for vcn in vcns:
        base_time = datetime.now() + timedelta(days=eu_count*5)

        # Grab crane operations for VCN
        for hour in range(0, 12, 4):
            start = base_time + timedelta(hours=hour)
            end = start + timedelta(hours=4)
            cur.execute("""
                INSERT INTO eu_lines (source_type, source_id, source_display, equipment_name, operator_name,
                                      cargo_name, operation_type, quantity, quantity_uom,
                                      start_time, end_time, entry_date, created_by, created_date, is_billed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ['VCN', vcn['id'], f"{vcn['vcn_doc_num']} - {vcn['vessel_name']}",
                  'Grab Crane', 'Operator A', 'Thermal Coal', 'Unloading',
                  1250, 'MT', start.strftime('%Y-%m-%dT%H:%M'), end.strftime('%Y-%m-%dT%H:%M'),
                  base_time.strftime('%Y-%m-%d'), 'admin', datetime.now().strftime('%Y-%m-%d'), 0])
            eu_count += 1

    # Get LDUD records with barges
    cur.execute("""
        SELECT l.id, l.doc_num, l.vessel_name, b.barge_name, b.cargo_name
        FROM ldud_header l
        LEFT JOIN ldud_barge_lines b ON l.id = b.ldud_id
        WHERE l.doc_status = 'Approved' AND b.barge_name IS NOT NULL
        LIMIT 4
    """)
    lduds = cur.fetchall()

    # Create EU entries for LDUD barge operations
    for ldud in lduds:
        base_time = datetime.now() + timedelta(days=eu_count*2)
        start = base_time + timedelta(hours=8)
        end = start + timedelta(hours=3)

        # Conveyor operations for LDUD
        cur.execute("""
            INSERT INTO eu_lines (source_type, source_id, source_display, barge_name, equipment_name,
                                  operator_name, cargo_name, operation_type, quantity, quantity_uom,
                                  route_name, start_time, end_time, entry_date, created_by, created_date, is_billed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ['LDUD', ldud['id'], f"{ldud['doc_num']} - {ldud['vessel_name']}", ldud['barge_name'],
              'Conveyor Belt', 'Operator B', ldud['cargo_name'] or 'Thermal Coal', 'Discharge',
              2800, 'MT', 'Route A - North Berth to Stockyard 1',
              start.strftime('%Y-%m-%dT%H:%M'), end.strftime('%Y-%m-%dT%H:%M'),
              base_time.strftime('%Y-%m-%d'), 'admin', datetime.now().strftime('%Y-%m-%d'), 0])
        eu_count += 1

    # Get MBC records
    cur.execute("SELECT id, doc_num, mbc_name, cargo_name FROM mbc_header WHERE doc_status = 'Approved' LIMIT 2")
    mbcs = cur.fetchall()

    # Create EU entries for MBC operations
    for mbc in mbcs:
        base_time = datetime.now() + timedelta(days=eu_count*3)
        start = base_time + timedelta(hours=6)
        end = start + timedelta(hours=5)

        # Ship unloader for MBC
        cur.execute("""
            INSERT INTO eu_lines (source_type, source_id, source_display, barge_name, equipment_name,
                                  operator_name, cargo_name, operation_type, quantity, quantity_uom,
                                  start_time, end_time, entry_date, created_by, created_date, is_billed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ['MBC', mbc['id'], f"{mbc['doc_num']} - {mbc['mbc_name']}", mbc['mbc_name'],
              'Ship Unloader', 'Operator C', mbc['cargo_name'] or 'Thermal Coal', 'Loading',
              5000, 'MT', start.strftime('%Y-%m-%dT%H:%M'), end.strftime('%Y-%m-%dT%H:%M'),
              base_time.strftime('%Y-%m-%d'), 'admin', datetime.now().strftime('%Y-%m-%d'), 0])
        eu_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {eu_count} Equipment Utilization (EU) records for billing (VCN, LDUD, MBC)")


def link_service_types_to_gst():
    """Link finance_service_types to GST 18% rate (seed data sets gst_rate_id = NULL)"""
    conn = get_db()
    cur = get_cursor(conn)

    # Find the GST 18% rate
    cur.execute("SELECT id FROM gst_rates WHERE igst_rate = 18 AND is_active = 1 LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("[SKIP] No GST 18% rate found in gst_rates table")
        conn.close()
        return

    gst_18_id = row['id']

    # Update all service types to use GST 18%
    cur.execute("""
        UPDATE finance_service_types
        SET gst_rate_id = %s
        WHERE is_active = 1 AND gst_rate_id IS NULL
    """, [gst_18_id])
    updated = cur.rowcount

    conn.commit()
    conn.close()
    print(f"[OK] Linked {updated} service types to GST 18% rate (id={gst_18_id})")


def populate_fin01_config():
    """FIN01 - Module config with seller/port GST details"""
    conn = get_db()
    cur = get_cursor(conn)

    # Check if FIN01 config already exists
    cur.execute("SELECT id, config_json FROM module_config WHERE module_code = 'FIN01'")
    existing = cur.fetchone()

    seller_config = {
        'approval_add': True,
        'approval_edit': True,
        'port_gst_state_code': '27',
        'seller_gstin': '27AABCP1234H1ZS',
        'seller_legal_name': 'Portman Port Services Pvt Ltd',
        'seller_address': 'Port Administration Building, Dock Road, Raigad',
        'seller_location': 'Raigad',
        'seller_pincode': '402201',
        'seller_phone': '02192-266000',
        'seller_email': 'billing@portmanservices.in'
    }

    if existing:
        # Merge with existing config
        try:
            existing_config = json.loads(existing['config_json']) if existing['config_json'] else {}
        except (json.JSONDecodeError, TypeError):
            existing_config = {}
        existing_config.update(seller_config)
        cur.execute("UPDATE module_config SET config_json = %s WHERE module_code = 'FIN01'",
                    [json.dumps(existing_config)])
    else:
        cur.execute("INSERT INTO module_config (module_code, config_json) VALUES (%s, %s)",
                    ['FIN01', json.dumps(seller_config)])

    conn.commit()
    conn.close()
    print("[OK] Populated FIN01 config with seller/port GST details")


def populate_srv01_permissions():
    """SRV01 - Module permissions for SRV01"""
    conn = get_db()
    cur = get_cursor(conn)

    cur.execute("SELECT id FROM users WHERE username = 'approver'")
    approver = cur.fetchone()
    cur.execute("SELECT id FROM users WHERE username = 'user'")
    regular = cur.fetchone()

    if approver:
        cur.execute("""
            INSERT INTO module_permissions (user_id, module_code, can_read, can_add, can_edit, can_delete)
            VALUES (%s, 'SRV01', 1, 1, 1, 1) ON CONFLICT (user_id, module_code) DO NOTHING
        """, [approver['id']])
    if regular:
        cur.execute("""
            INSERT INTO module_permissions (user_id, module_code, can_read, can_add, can_edit, can_delete)
            VALUES (%s, 'SRV01', 1, 1, 1, 0) ON CONFLICT (user_id, module_code) DO NOTHING
        """, [regular['id']])

    # SRV01 approval config
    if approver:
        config = json.dumps({'approval_add': True, 'approval_edit': True, 'approver_id': str(approver['id'])})
        cur.execute("""
            INSERT INTO module_config (module_code, config_json)
            VALUES ('SRV01', %s) ON CONFLICT (module_code) DO NOTHING
        """, [config])

    conn.commit()
    conn.close()
    print("[OK] Populated SRV01 module permissions and config")


def populate_service_field_definitions():
    """FSTM01 - Custom field definitions for service types with has_custom_fields"""
    conn = get_db()
    cur = get_cursor(conn)

    # Get service type IDs
    cur.execute("SELECT id, service_code, service_name FROM finance_service_types WHERE is_active = 1")
    service_types = {row['service_code']: row for row in cur.fetchall()}

    if not service_types:
        print("[SKIP] No service types found")
        conn.close()
        return

    field_count = 0
    now = datetime.now().strftime('%Y-%m-%d')

    # --- Equipment Rental (EQP001) - Grab Hiring fields ---
    if 'EQP001' in service_types:
        st_id = service_types['EQP001']['id']
        cur.execute("UPDATE finance_service_types SET has_custom_fields = 1 WHERE id = %s", [st_id])

        fields = [
            ('grab_make', 'Grab Make', 'dropdown', '["Nemag","Mitsui","Orts","Peiner"]', None, None, 0, 0, 1),
            ('grab_capacity', 'Grab Capacity (CBM)', 'number', None, None, None, 1, 0, 2),
            ('deployment_start', 'Deployment Start', 'datetime', None, None, None, 1, 0, 3),
            ('deployment_end', 'Deployment End', 'datetime', None, None, None, 1, 0, 4),
            ('total_hours', 'Total Hours', 'calculated', None, 'deployment_end - deployment_start', 'hours', 0, 1, 5),
            ('operator_name', 'Operator Name', 'text', None, None, None, 0, 0, 6),
        ]
        for fname, flabel, ftype, foptions, formula, result_type, is_req, is_billable, order in fields:
            cur.execute("""
                INSERT INTO service_field_definitions
                (service_type_id, field_name, field_label, field_type, field_options,
                 calculation_formula, calculation_result_type, is_required, is_billable_qty,
                 display_order, is_active, created_by, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 'admin', %s)
            """, [st_id, fname, flabel, ftype, foptions, formula, result_type,
                  is_req, is_billable, order, now])
            field_count += 1

    # --- Storage Charges (STO001) - Yard storage fields ---
    if 'STO001' in service_types:
        st_id = service_types['STO001']['id']
        cur.execute("UPDATE finance_service_types SET has_custom_fields = 1 WHERE id = %s", [st_id])

        fields = [
            ('yard_area', 'Yard / Area', 'dropdown', '["Yard A","Yard B","Yard C","Open Storage"]', None, None, 1, 0, 1),
            ('storage_start', 'Storage Start Date', 'date', None, None, None, 1, 0, 2),
            ('storage_end', 'Storage End Date', 'date', None, None, None, 1, 0, 3),
            ('total_days', 'Total Days', 'calculated', None, 'storage_end - storage_start', 'days', 0, 1, 4),
            ('cargo_description', 'Cargo Description', 'text', None, None, None, 0, 0, 5),
            ('quantity_stored', 'Quantity Stored (MT)', 'number', None, None, None, 1, 0, 6),
        ]
        for fname, flabel, ftype, foptions, formula, result_type, is_req, is_billable, order in fields:
            cur.execute("""
                INSERT INTO service_field_definitions
                (service_type_id, field_name, field_label, field_type, field_options,
                 calculation_formula, calculation_result_type, is_required, is_billable_qty,
                 display_order, is_active, created_by, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 'admin', %s)
            """, [st_id, fname, flabel, ftype, foptions, formula, result_type,
                  is_req, is_billable, order, now])
            field_count += 1

    # --- Delay Charges (DEL001) - Delay recording fields ---
    if 'DEL001' in service_types:
        st_id = service_types['DEL001']['id']
        cur.execute("UPDATE finance_service_types SET has_custom_fields = 1 WHERE id = %s", [st_id])

        fields = [
            ('delay_reason', 'Delay Reason', 'dropdown', '["Weather","Equipment Failure","Cargo Not Ready","Port Congestion","Tidal","Labour Strike"]', None, None, 1, 0, 1),
            ('delay_start', 'Delay Start', 'datetime', None, None, None, 1, 0, 2),
            ('delay_end', 'Delay End', 'datetime', None, None, None, 1, 0, 3),
            ('delay_hours', 'Delay Hours', 'calculated', None, 'delay_end - delay_start', 'hours', 0, 1, 4),
            ('account_type', 'Account Type', 'dropdown', '["Vessel Account","Port Account","Shipper Account"]', None, None, 1, 0, 5),
            ('remarks', 'Remarks', 'text', None, None, None, 0, 0, 6),
        ]
        for fname, flabel, ftype, foptions, formula, result_type, is_req, is_billable, order in fields:
            cur.execute("""
                INSERT INTO service_field_definitions
                (service_type_id, field_name, field_label, field_type, field_options,
                 calculation_formula, calculation_result_type, is_required, is_billable_qty,
                 display_order, is_active, created_by, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 'admin', %s)
            """, [st_id, fname, flabel, ftype, foptions, formula, result_type,
                  is_req, is_billable, order, now])
            field_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {field_count} service field definitions for EQP001, STO001, DEL001 (has_custom_fields set)")


def populate_service_records():
    """SRV01 - Service records with EAV field values"""
    conn = get_db()
    cur = get_cursor(conn)

    # Get VCN records as sources
    cur.execute("SELECT id, vcn_doc_num, vessel_name FROM vcn_header WHERE doc_status = 'Approved' LIMIT 3")
    vcns = cur.fetchall()

    if not vcns:
        print("[SKIP] No approved VCN records found")
        conn.close()
        return

    # Get service types with custom fields
    cur.execute("""
        SELECT st.id, st.service_code, st.service_name, st.uom
        FROM finance_service_types st
        WHERE st.has_custom_fields = 1 AND st.is_active = 1
    """)
    service_types = {row['service_code']: row for row in cur.fetchall()}

    # Get field definitions grouped by service type
    cur.execute("""
        SELECT id, service_type_id, field_name, field_type, field_options, is_billable_qty
        FROM service_field_definitions WHERE is_active = 1
        ORDER BY display_order
    """)
    fields_by_type = {}
    for f in cur.fetchall():
        fields_by_type.setdefault(f['service_type_id'], []).append(f)

    now = datetime.now().strftime('%Y-%m-%d')
    record_count = 0

    # --- Equipment Rental records (grab hiring) for each VCN ---
    if 'EQP001' in service_types:
        st = service_types['EQP001']
        fields = fields_by_type.get(st['id'], [])
        grab_makes = ['Nemag', 'Mitsui', 'Orts', 'Peiner']

        for idx, vcn in enumerate(vcns):
            record_num = f"SRV{record_count + 1:04d}"
            base_date = datetime.now() + timedelta(days=idx * 5)
            deploy_start = base_date.replace(hour=6, minute=0, second=0)
            deploy_end = deploy_start + timedelta(hours=8 + idx * 2)
            total_hours = (deploy_end - deploy_start).total_seconds() / 3600

            cur.execute("""
                INSERT INTO service_records
                (record_number, service_type_id, source_type, source_id, source_display,
                 record_date, billable_quantity, billable_uom, doc_status, is_billed,
                 created_by, created_date, approved_by, approved_date, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [record_num, st['id'], 'VCN', vcn['id'],
                  f"{vcn['vcn_doc_num']} - {vcn['vessel_name']}",
                  base_date.strftime('%Y-%m-%d'), round(total_hours, 2), 'Hours',
                  'Approved', 0, 'admin', now, 'approver', now,
                  f"Grab crane deployed for {vcn['vessel_name']} unloading"])
            record_id = cur.fetchone()['id']

            # Insert field values
            field_values = {
                'grab_make': grab_makes[idx % len(grab_makes)],
                'grab_capacity': str(12 + idx * 2),
                'deployment_start': deploy_start.strftime('%Y-%m-%dT%H:%M'),
                'deployment_end': deploy_end.strftime('%Y-%m-%dT%H:%M'),
                'total_hours': str(round(total_hours, 2)),
                'operator_name': f'Operator {chr(65 + idx)}',
            }
            for field in fields:
                if field['field_name'] in field_values:
                    cur.execute("""
                        INSERT INTO service_record_values (service_record_id, field_definition_id, field_value)
                        VALUES (%s, %s, %s) ON CONFLICT (service_record_id, field_definition_id) DO NOTHING
                    """, [record_id, field['id'], field_values[field['field_name']]])

            record_count += 1

    # --- Storage records for first 2 VCNs ---
    if 'STO001' in service_types:
        st = service_types['STO001']
        fields = fields_by_type.get(st['id'], [])
        yards = ['Yard A', 'Yard B', 'Yard C']

        for idx, vcn in enumerate(vcns[:2]):
            record_num = f"SRV{record_count + 1:04d}"
            base_date = datetime.now() + timedelta(days=idx * 7)
            storage_start = base_date
            storage_end = storage_start + timedelta(days=5 + idx * 3)
            total_days = (storage_end - storage_start).days

            cur.execute("""
                INSERT INTO service_records
                (record_number, service_type_id, source_type, source_id, source_display,
                 record_date, billable_quantity, billable_uom, doc_status, is_billed,
                 created_by, created_date, approved_by, approved_date, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [record_num, st['id'], 'VCN', vcn['id'],
                  f"{vcn['vcn_doc_num']} - {vcn['vessel_name']}",
                  base_date.strftime('%Y-%m-%d'), total_days, 'Days',
                  'Approved', 0, 'admin', now, 'approver', now,
                  f"Yard storage for cargo from {vcn['vessel_name']}"])
            record_id = cur.fetchone()['id']

            field_values = {
                'yard_area': yards[idx % len(yards)],
                'storage_start': storage_start.strftime('%Y-%m-%d'),
                'storage_end': storage_end.strftime('%Y-%m-%d'),
                'total_days': str(total_days),
                'cargo_description': 'Thermal Coal (Import)',
                'quantity_stored': str(5000 + idx * 2000),
            }
            for field in fields:
                if field['field_name'] in field_values:
                    cur.execute("""
                        INSERT INTO service_record_values (service_record_id, field_definition_id, field_value)
                        VALUES (%s, %s, %s) ON CONFLICT (service_record_id, field_definition_id) DO NOTHING
                    """, [record_id, field['id'], field_values[field['field_name']]])

            record_count += 1

    # --- Delay charge records for first VCN ---
    if 'DEL001' in service_types and vcns:
        st = service_types['DEL001']
        fields = fields_by_type.get(st['id'], [])
        vcn = vcns[0]

        delays = [
            ('Weather', 4.5, 'Vessel Account', 'Heavy rain stopped operations'),
            ('Equipment Failure', 2.0, 'Port Account', 'Grab crane hydraulic failure'),
        ]

        for delay_reason, hours, acct, remark in delays:
            record_num = f"SRV{record_count + 1:04d}"
            base_date = datetime.now() + timedelta(days=record_count * 2)
            delay_start = base_date.replace(hour=14, minute=0, second=0)
            delay_end = delay_start + timedelta(hours=hours)

            cur.execute("""
                INSERT INTO service_records
                (record_number, service_type_id, source_type, source_id, source_display,
                 record_date, billable_quantity, billable_uom, doc_status, is_billed,
                 created_by, created_date, approved_by, approved_date, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [record_num, st['id'], 'VCN', vcn['id'],
                  f"{vcn['vcn_doc_num']} - {vcn['vessel_name']}",
                  base_date.strftime('%Y-%m-%d'), hours, 'Hours',
                  'Approved', 0, 'admin', now, 'approver', now, remark])
            record_id = cur.fetchone()['id']

            field_values = {
                'delay_reason': delay_reason,
                'delay_start': delay_start.strftime('%Y-%m-%dT%H:%M'),
                'delay_end': delay_end.strftime('%Y-%m-%dT%H:%M'),
                'delay_hours': str(hours),
                'account_type': acct,
                'remarks': remark,
            }
            for field in fields:
                if field['field_name'] in field_values:
                    cur.execute("""
                        INSERT INTO service_record_values (service_record_id, field_definition_id, field_value)
                        VALUES (%s, %s, %s) ON CONFLICT (service_record_id, field_definition_id) DO NOTHING
                    """, [record_id, field['id'], field_values[field['field_name']]])

            record_count += 1

    conn.commit()
    conn.close()
    print(f"[OK] Populated {record_count} service records with EAV field values (grab hiring, storage, delays)")


def main():
    print("\n" + "="*50)
    print("PORTMAN Mock Data Population Script (PostgreSQL)")
    print("="*50 + "\n")

    print("Clearing existing mock data...")
    clear_mock_data()

    print("\nPopulating Master Modules...")
    populate_vessel_types()
    populate_vessel_categories()
    populate_gears()
    populate_vessel_agents()
    populate_importer_exporters()
    populate_customers()
    populate_operation_types()
    populate_doc_series()
    populate_discharge_types()
    populate_run_types()
    populate_delay_types()
    populate_cargo_master()
    populate_mbc_master()
    populate_port_berths()
    populate_conveyor_routes()

    print("\nPopulating Transaction Modules...")
    populate_vessels()
    populate_vcn_records()
    populate_ldud_records()
    populate_mbc_records()
    populate_eu_records()

    print("\nPopulating Finance Modules...")
    populate_finance_currencies()
    populate_customer_agreements()
    link_service_types_to_gst()
    populate_fin01_config()

    print("\nPopulating Service Recording Modules...")
    populate_srv01_permissions()
    populate_service_field_definitions()
    populate_service_records()

    print("\n" + "="*50)
    print("Mock data population complete!")
    print("="*50)
    print("\n** Note: Seed data (UOMs, hatches, holds, GST rates, service types) is auto-populated by Alembic migrations **")
    print("** All transactional modules populated with relational data **")
    print("** Service records with EAV custom fields populated for SRV01/billing integration **\n")

if __name__ == '__main__':
    main()

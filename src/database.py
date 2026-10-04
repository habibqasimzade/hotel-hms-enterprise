import sqlite3
from datetime import datetime

DB_NAME = "hotel_enterprise.db"

def get_connection():
    """Returns a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Multi-Tenant Hotels / Properties
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_name TEXT NOT NULL,
            hotel_code TEXT UNIQUE NOT NULL,
            currency TEXT DEFAULT 'AZN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Staff & System Users (Bound to hotel_id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'reception', 'housekeeping')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 3. Room Categories (Base & Single Rates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            base_price REAL NOT NULL,
            single_price REAL DEFAULT 0.0,
            capacity INTEGER DEFAULT 2,
            UNIQUE(hotel_id, name),
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 4. Rooms Inventory with Housekeeping States
    # Statuses: 'Clean', 'Dirty', 'Inspected', 'Out of Order'
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            room_type TEXT NOT NULL,
            floor INTEGER NOT NULL,
            housekeeping_status TEXT DEFAULT 'Clean' CHECK(housekeeping_status IN ('Clean', 'Dirty', 'Inspected', 'Out of Order')),
            UNIQUE(hotel_id, room_number),
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 5. Guest CRM & History Profiles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guest_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            serial_no TEXT NOT NULL,
            full_name TEXT NOT NULL,
            nationality TEXT NOT NULL,
            phone TEXT,
            is_blacklisted INTEGER DEFAULT 0,
            blacklist_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(hotel_id, serial_no),
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 6. Booking Channels / Guest Types
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guest_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            is_payable INTEGER DEFAULT 1,
            require_serial INTEGER DEFAULT 0,
            UNIQUE(hotel_id, name),
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 7. Surcharge & Supplemental Tariff Rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pricing_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            rule_key TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            UNIQUE(hotel_id, rule_key),
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 8. Master Reservations Table (Folio, Surcharges & Concurrency Audits)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            serial_no TEXT DEFAULT '',
            guest_name TEXT NOT NULL,
            nationality TEXT NOT NULL,
            guest_type TEXT NOT NULL,
            agency TEXT,
            room_number TEXT NOT NULL,
            room_type TEXT NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            adults INTEGER DEFAULT 1,
            kids_6_12 INTEGER DEFAULT 0,
            kids_0_6 INTEGER DEFAULT 0,
            above_12 INTEGER DEFAULT 0,
            daily_rate REAL NOT NULL,
            total_balance REAL NOT NULL,
            paid_amount REAL DEFAULT 0.0,
            payment_method TEXT DEFAULT 'Cash' CHECK(payment_method IN ('Cash', 'Credit Card', 'Bank Transfer', 'Direct Bill')),
            early_checkin_fee REAL DEFAULT 0.0,
            late_checkout_fee REAL DEFAULT 0.0,
            status TEXT DEFAULT 'Confirmed' CHECK(status IN ('Confirmed', 'In-House', 'Checked-Out', 'Cancellation Requested', 'Cancelled')),
            created_by TEXT NOT NULL,
            cancel_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
        )
    """)

    # 9. Cancellation Requests Audit
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cancel_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            reservation_id INTEGER NOT NULL,
            requested_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reservation_id) REFERENCES reservations(id) ON DELETE CASCADE
        )
    """)

    # --- Initial Seed: Default Hotel & Root Admin (Concurrency-Safe) ---
    cursor.execute("""
        INSERT OR IGNORE INTO hotels (id, hotel_name, hotel_code, currency)
        VALUES (1, 'Grand Resort & Spa', 'GR01', 'AZN')
    """)

    cursor.execute("SELECT id FROM hotels WHERE hotel_code = 'GR01'")
    h_row = cursor.fetchone()
    if h_row:
        default_hotel_id = h_row[0]

        # Check and seed default root manager
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            import bcrypt
            salt = bcrypt.gensalt()
            admin_pwd_hash = bcrypt.hashpw(b"admin123", salt).decode('utf-8')
            cursor.execute("""
                INSERT OR IGNORE INTO users (hotel_id, username, password_hash, full_name, role)
                VALUES (?, 'admin', ?, 'General Manager', 'admin')
            """, (default_hotel_id, admin_pwd_hash))

        # Default surcharges
        rules = [
            (default_hotel_id, 'kids_0_6_second', 'Daily surcharge for 2nd child (0-6 yrs)', 47.5),
            (default_hotel_id, 'kids_6_12', 'Daily surcharge for child (6-12 yrs)', 47.5),
            (default_hotel_id, 'above_12', 'Daily surcharge for extra guest (12+ yrs)', 47.5)
        ]
        cursor.executemany("INSERT OR IGNORE INTO pricing_rules (hotel_id, rule_key, title, price) VALUES (?, ?, ?, ?)", rules)

        # Default booking channels
        channels = [
            (default_hotel_id, 'Direct / Self-Pay', 1, 0),
            (default_hotel_id, 'Corporate Voucher', 0, 1)
        ]
        cursor.executemany("INSERT OR IGNORE INTO guest_types (hotel_id, name, is_payable, require_serial) VALUES (?, ?, ?, ?)", channels)

    conn.commit()
    conn.close()

# -------------------------------------------------------------
# CONCURRENCY-SAFE TRANSACTION & OVERBOOKING PREVENTION
# -------------------------------------------------------------
def book_reservation_atomic(reservation_data: dict) -> tuple[bool, str]:
    """
    Executes booking inside an immediate transaction lock.
    Prevents race conditions when two receptionists attempt to book the same room simultaneously.
    """
    conn = get_connection()
    try:
        # BEGIN IMMEDIATE locks the database for write operations from the start
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()

        h_id = reservation_data['hotel_id']
        r_num = reservation_data['room_number']
        c_in = reservation_data['check_in']
        c_out = reservation_data['check_out']

        # 1. Verify that room is Clean or Inspected (Business Rule)
        cursor.execute("SELECT housekeeping_status FROM rooms WHERE hotel_id = ? AND room_number = ?", (h_id, r_num))
        room_row = cursor.fetchone()
        if not room_row:
            conn.rollback()
            return False, f"Room {r_num} does not exist in inventory."

        # 2. Check Overlapping Bookings
        cursor.execute("""
            SELECT id, check_in, check_out FROM reservations
            WHERE hotel_id = ? AND room_number = ? AND status IN ('Confirmed', 'In-House')
        """, (h_id, r_num))
        existing_bookings = cursor.fetchall()

        new_in = datetime.strptime(c_in, "%Y-%m-%d").date()
        new_out = datetime.strptime(c_out, "%Y-%m-%d").date()

        for b in existing_bookings:
            e_in = datetime.strptime(b['check_in'], "%Y-%m-%d").date()
            e_out = datetime.strptime(b['check_out'], "%Y-%m-%d").date()
            if not (new_out <= e_in or new_in >= e_out):
                conn.rollback()
                return False, f"Conflict: Room {r_num} was just reserved by another agent."

        # 3. Insert Master Reservation
        cursor.execute("""
            INSERT INTO reservations (
                hotel_id, serial_no, guest_name, nationality, guest_type, agency,
                room_number, room_type, check_in, check_out,
                adults, kids_6_12, kids_0_6, above_12,
                daily_rate, total_balance, paid_amount, payment_method,
                early_checkin_fee, late_checkout_fee, status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', ?)
        """, (
            h_id, reservation_data.get('serial_no', ''), reservation_data['guest_name'],
            reservation_data['nationality'], reservation_data['guest_type'], reservation_data.get('agency', ''),
            r_num, reservation_data['room_type'], c_in, c_out,
            reservation_data.get('adults', 1), reservation_data.get('kids_6_12', 0),
            reservation_data.get('kids_0_6', 0), reservation_data.get('above_12', 0),
            reservation_data['daily_rate'], reservation_data['total_balance'],
            reservation_data.get('paid_amount', 0.0), reservation_data.get('payment_method', 'Cash'),
            reservation_data.get('early_checkin_fee', 0.0), reservation_data.get('late_checkout_fee', 0.0),
            reservation_data['created_by']
        ))

        # 4. Save/Update Guest Profile in CRM
        if reservation_data.get('serial_no'):
            cursor.execute("""
                INSERT INTO guest_profiles (hotel_id, serial_no, full_name, nationality)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(hotel_id, serial_no) DO UPDATE SET
                    full_name = excluded.full_name,
                    nationality = excluded.nationality
            """, (h_id, reservation_data['serial_no'], reservation_data['guest_name'], reservation_data['nationality']))

        conn.commit()
        return True, "Reservation booked successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# -------------------------------------------------------------
# VACANCY SEARCH WITH HOUSEKEEPING AWARENESS
# -------------------------------------------------------------
def get_available_rooms(hotel_id: int, check_in_str: str, check_out_str: str, room_type=None, exclude_res_id=None):
    """
    Returns only rooms that are not booked for the given date window
    and are not Out of Order.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT room_number, room_type, floor, housekeeping_status FROM rooms WHERE hotel_id = ? AND housekeeping_status != 'Out of Order'"
    params = [hotel_id]

    if room_type and room_type != "All":
        query += " AND room_type = ?"
        params.append(room_type)

    query += " ORDER BY floor, room_number"
    cursor.execute(query, params)
    all_rooms = cursor.fetchall()

    # Query busy rooms
    b_query = """
        SELECT room_number, check_in, check_out FROM reservations
        WHERE hotel_id = ? AND status IN ('Confirmed', 'In-House')
    """
    b_params = [hotel_id]
    if exclude_res_id:
        b_query += " AND id != ?"
        b_params.append(exclude_res_id)

    cursor.execute(b_query, b_params)
    bookings = cursor.fetchall()
    conn.close()

    new_in = datetime.strptime(check_in_str, "%Y-%m-%d").date()
    new_out = datetime.strptime(check_out_str, "%Y-%m-%d").date()

    occupied_set = set()
    for b in bookings:
        exist_in = datetime.strptime(b['check_in'], "%Y-%m-%d").date()
        exist_out = datetime.strptime(b['check_out'], "%Y-%m-%d").date()
        if not (new_out <= exist_in or new_in >= exist_out):
            occupied_set.add(b['room_number'])

    return [r for r in all_rooms if r['room_number'] not in occupied_set]
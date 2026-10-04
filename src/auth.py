import bcrypt
import database as db

def hash_password(plain_password: str) -> str:
    """Hashes a raw password using bcrypt with a generated salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

def check_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def authenticate_user(username: str, password: str) -> dict | None:
    """
    Authenticates user credentials and binds their operational hotel tenant.
    Returns a unified user context dictionary or None if invalid.
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id AS user_id, u.hotel_id, u.username, u.password_hash, u.full_name, u.role,
               h.hotel_name, h.hotel_code, h.currency
        FROM users u
        JOIN hotels h ON u.hotel_id = h.id
        WHERE u.username = ?
    """, (username.strip(),))
    row = cursor.fetchone()
    conn.close()

    if row and check_password(password, row['password_hash']):
        return {
            "user_id": row['user_id'],
            "hotel_id": row['hotel_id'],
            "username": row['username'],
            "full_name": row['full_name'],
            "role": row['role'],
            "hotel_name": row['hotel_name'],
            "hotel_code": row['hotel_code'],
            "currency": row['currency']
        }
    return None

def register_new_hotel(
    hotel_name: str, 
    hotel_code: str, 
    currency: str, 
    admin_username: str, 
    admin_password: str, 
    admin_full_name: str
) -> tuple[bool, str]:
    """
    Onboards a completely new hotel tenant with isolated settings and a root manager account.
    Guarantees atomic multi-tenant isolation.
    """
    conn = db.get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()

        h_code = hotel_code.strip().upper()
        u_name = admin_username.strip()

        # Check unique hotel code
        cursor.execute("SELECT id FROM hotels WHERE hotel_code = ?", (h_code,))
        if cursor.fetchone():
            conn.rollback()
            return False, f"Hotel code '{h_code}' is already registered."

        # Check unique username
        cursor.execute("SELECT id FROM users WHERE username = ?", (u_name,))
        if cursor.fetchone():
            conn.rollback()
            return False, f"Username '{u_name}' is already taken."

        # 1. Insert New Hotel Tenant
        cursor.execute("""
            INSERT INTO hotels (hotel_name, hotel_code, currency)
            VALUES (?, ?, ?)
        """, (hotel_name.strip(), h_code, currency.strip().upper()))
        new_hotel_id = cursor.lastrowid

        # 2. Insert Root Manager Account
        pwd_hash = hash_password(admin_password.strip())
        cursor.execute("""
            INSERT INTO users (hotel_id, username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, 'admin')
        """, (new_hotel_id, u_name, pwd_hash, admin_full_name.strip()))

        # 3. Seed Standard Property Pricing Policies
        default_rules = [
            (new_hotel_id, 'kids_0_6_second', 'Daily surcharge for 2nd child (0-6 yrs)', 47.5),
            (new_hotel_id, 'kids_6_12', 'Daily surcharge for child (6-12 yrs)', 47.5),
            (new_hotel_id, 'above_12', 'Daily surcharge for extra guest (12+ yrs)', 47.5)
        ]
        cursor.executemany("INSERT INTO pricing_rules (hotel_id, rule_key, title, price) VALUES (?, ?, ?, ?)", default_rules)

        # 4. Seed Standard Booking Channels
        default_channels = [
            (new_hotel_id, 'Direct / Self-Pay', 1, 0),
            (new_hotel_id, 'Corporate Voucher', 0, 1)
        ]
        cursor.executemany("INSERT INTO guest_types (hotel_id, name, is_payable, require_serial) VALUES (?, ?, ?, ?)", default_channels)

        conn.commit()
        return True, f"Hotel '{hotel_name}' (Code: {h_code}) registered successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
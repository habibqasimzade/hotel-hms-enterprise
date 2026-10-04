import os
import sys
import pytest
from datetime import datetime

# Inject 'src' directory into module search path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import database as db
from reception_panel import calculate_rate


def test_collision_math_logic():
    """
    Unit test verifying inverted interval collision mathematics.
    Condition: Overlap exists unless (new_out <= exist_in OR new_in >= exist_out).
    """
    exist_in = datetime.strptime("2026-10-10", "%Y-%m-%d").date()
    exist_out = datetime.strptime("2026-10-15", "%Y-%m-%d").date()

    # Scenario 1: Completely before existing stay -> NO collision
    new_in_1 = datetime.strptime("2026-10-05", "%Y-%m-%d").date()
    new_out_1 = datetime.strptime("2026-10-10", "%Y-%m-%d").date()
    has_conflict_1 = not (new_out_1 <= exist_in or new_in_1 >= exist_out)
    assert has_conflict_1 is False

    # Scenario 2: Overlapping in the middle (12th to 14th) -> MUST COLLIDE
    new_in_2 = datetime.strptime("2026-10-12", "%Y-%m-%d").date()
    new_out_2 = datetime.strptime("2026-10-14", "%Y-%m-%d").date()
    has_conflict_2 = not (new_out_2 <= exist_in or new_in_2 >= exist_out)
    assert has_conflict_2 is True

    # Scenario 3: Checking in on previous guest's departure date -> NO collision
    new_in_3 = datetime.strptime("2026-10-15", "%Y-%m-%d").date()
    new_out_3 = datetime.strptime("2026-10-20", "%Y-%m-%d").date()
    has_conflict_3 = not (new_out_3 <= exist_in or new_in_3 >= exist_out)
    assert has_conflict_3 is False


def test_single_vs_double_pricing_calculation():
    """
    Unit test verifying single occupancy rate vs double occupancy base rate.
    """
    # Initialize schema
    db.init_db()
    conn = db.get_connection()
    cursor = conn.cursor()

    # Retrieve default hotel id
    cursor.execute("SELECT id FROM hotels LIMIT 1")
    hotel_id = cursor.fetchone()[0]

    # Insert a designated test category
    cursor.execute("""
        INSERT OR REPLACE INTO room_types (hotel_id, name, base_price, single_price, capacity)
        VALUES (?, 'TestCategory', 200.0, 150.0, 2)
    """, (hotel_id,))
    conn.commit()
    conn.close()

    # 1 Adult, 0 minors -> Expect single occupancy rate (150.0 AZN)
    rate_single = calculate_rate(hotel_id, "TestCategory", "Direct / Self-Pay", adults=1, kids_6_12=0, kids_0_6=0, above_12=0)
    assert rate_single == 150.0

    # 2 Adults, 0 minors -> Expect double base rate (200.0 AZN)
    rate_double = calculate_rate(hotel_id, "TestCategory", "Direct / Self-Pay", adults=2, kids_6_12=0, kids_0_6=0, above_12=0)
    assert rate_double == 200.0

    # Non-billable channel (Corporate Voucher) -> Expect 0.0 AZN
    rate_voucher = calculate_rate(hotel_id, "TestCategory", "Corporate Voucher", adults=2, kids_6_12=0, kids_0_6=0, above_12=0)
    assert rate_voucher == 0.0
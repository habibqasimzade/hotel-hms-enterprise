import streamlit as st
import pandas as pd
from datetime import datetime
import database as db

# -------------------------------------------------------------
# DYNAMIC TARIFF & PRICING ENGINE
# -------------------------------------------------------------
def calculate_rate(hotel_id: int, room_type_name: str, guest_type_name: str, adults: int, kids_6_12: int, kids_0_6: int, above_12: int) -> float:
    conn = db.get_connection()
    cursor = conn.cursor()

    # Check if channel is billable
    cursor.execute("SELECT is_payable FROM guest_types WHERE hotel_id = ? AND name = ?", (hotel_id, guest_type_name))
    row_gt = cursor.fetchone()
    if row_gt and row_gt[0] == 0:
        conn.close()
        return 0.0

    # Retrieve base and single occupancy rates
    cursor.execute("SELECT base_price, single_price FROM room_types WHERE hotel_id = ? AND name = ?", (hotel_id, room_type_name))
    row_rt = cursor.fetchone()
    base_rate = row_rt[0] if row_rt else 0.0
    single_rate = row_rt[1] if (row_rt and row_rt[1] and row_rt[1] > 0) else base_rate

    # Retrieve property surcharges
    cursor.execute("SELECT rule_key, price FROM pricing_rules WHERE hotel_id = ?", (hotel_id,))
    rules = dict(cursor.fetchall())
    conn.close()

    p_kids_0_6_sec = rules.get('kids_0_6_second', 47.5)
    p_kids_6_12 = rules.get('kids_6_12', 47.5)
    p_above_12 = rules.get('above_12', 47.5)

    # Single Occupancy Scenario (1 Adult, no accompanying minors)
    if adults == 1 and kids_6_12 == 0 and kids_0_6 == 0 and above_12 == 0:
        return single_rate

    # Standard / Multi-occupancy Calculation
    extra_adults = max(0, adults - 2) * p_above_12
    extra_0_6 = max(0, kids_0_6 - 1) * p_kids_0_6_sec
    cost_6_12 = kids_6_12 * p_kids_6_12
    cost_above_12 = above_12 * p_above_12

    daily_total = base_rate + extra_adults + extra_0_6 + cost_6_12 + cost_above_12
    return daily_total

# -------------------------------------------------------------
# FRONT DESK OPERATIONS WORKSPACE
# -------------------------------------------------------------
def render_reception_panel(user_context: dict):
    hotel_id = user_context["hotel_id"]
    curr = user_context.get("currency", "AZN")

    tab_map, tab_new_res, tab_active_res, tab_inhouse = st.tabs([
        "Live Room Rack & Housekeeping",
        "New Reservation & Folio",
        "Reservation Queue",
        "In-House Guests & Billing"
    ])

    conn = db.get_connection()
    cursor = conn.cursor()

    # =========================================================
    # TAB 1: LIVE ROOM RACK (HOUSEKEEPING GRID)
    # =========================================================
    with tab_map:
        st.subheader("Live Room Rack & Housekeeping Status")
        st.caption("🟢 Clean (Ready) | 🟡 Dirty (Turnover Required) | 🔴 Occupied | ⚫ Out of Order")

        today_str = datetime.today().strftime("%Y-%m-%d")

        cursor.execute("""
            SELECT room_number, room_type, floor, housekeeping_status 
            FROM rooms 
            WHERE hotel_id = ? 
            ORDER BY floor, room_number
        """, (hotel_id,))
        all_rooms = cursor.fetchall()

        if not all_rooms:
            st.warning("No operational rooms found. Please configure inventory in System Settings.")
        else:
            cursor.execute("""
                SELECT room_number, guest_name, status, check_out 
                FROM reservations 
                WHERE hotel_id = ? AND status IN ('In-House', 'Confirmed') 
                AND check_in <= ? AND check_out > ?
            """, (hotel_id, today_str, today_str))
            busy_map = {row[0]: row for row in cursor.fetchall()}

            floors = sorted(list(set([r['floor'] for r in all_rooms])))
            for fl in floors:
                st.markdown(f"##### Floor {fl}")
                floor_rooms = [r for r in all_rooms if r['floor'] == fl]

                cols = st.columns(6)
                for idx, r in enumerate(floor_rooms):
                    r_num = r['room_number']
                    r_type = r['room_type']
                    hk_stat = r['housekeeping_status']
                    col = cols[idx % 6]

                    is_busy = r_num in busy_map

                    # Color Palette
                    if hk_stat == 'Out of Order':
                        card_bg = "#334155"  # Slate/Gray
                        badge_bg = "#64748B"
                        status_label = "OUT OF ORDER"
                        guest_label = "Maintenance"
                    elif is_busy:
                        card_bg = "#991B1B"  # Crimson/Red
                        badge_bg = "#EF4444"
                        status_label = "OCCUPIED"
                        guest_label = f"{busy_map[r_num][1]}"
                    elif hk_stat == 'Dirty':
                        card_bg = "#92400E"  # Amber/Yellow
                        badge_bg = "#F59E0B"
                        status_label = "DIRTY"
                        guest_label = "Needs Cleaning"
                    else:  # Clean or Inspected
                        card_bg = "#065F46"  # Emerald/Green
                        badge_bg = "#10B981"
                        status_label = "VACANT CLEAN"
                        guest_label = "Ready for Sale"

                    col.markdown(f"""
                        <div style="background-color: {card_bg}; border: 1px solid rgba(255,255,255,0.12); color: #F8FAFC; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">
                            <div style="font-size: 18px; font-weight: 700;">Room {r_num}</div>
                            <div style="font-size: 11px; opacity: 0.85; margin-bottom: 6px;">{r_type}</div>
                            <span style="background-color: {badge_bg}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;">
                                {status_label}
                            </span>
                            <div style="font-size: 11px; margin-top: 6px; opacity: 0.95; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                                {guest_label}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

            # Quick Housekeeping Turnover Toggle
            with st.expander("⚡ Quick Housekeeping Status Turnover"):
                hk_col1, hk_col2, hk_col3 = st.columns([1, 1, 1])
                with hk_col1:
                    dirty_rooms = [r['room_number'] for r in all_rooms if r['housekeeping_status'] == 'Dirty']
                    sel_dirty = st.selectbox("Select Dirty Room to Clean:", dirty_rooms if dirty_rooms else ["None Available"])
                with hk_col2:
                    target_hk = st.selectbox("Assign New Status:", ["Clean", "Inspected", "Out of Order"])
                with hk_col3:
                    st.write("")
                    st.write("")
                    if st.button("Mark as Cleaned", use_container_width=True):
                        if sel_dirty != "None Available":
                            cursor.execute("UPDATE rooms SET housekeeping_status = ? WHERE hotel_id = ? AND room_number = ?", (target_hk, hotel_id, sel_dirty))
                            conn.commit()
                            st.success(f"Room {sel_dirty} marked as {target_hk}.")
                            st.rerun()

    # =========================================================
    # TAB 2: NEW RESERVATION ENTRY WITH FOLIO BILLING
    # =========================================================
    with tab_new_res:
        st.subheader("New Guest Reservation & Folio Intake")

        cursor.execute("SELECT name, require_serial FROM guest_types WHERE hotel_id = ?", (hotel_id,))
        channels = cursor.fetchall()
        channel_serial_map = {c[0]: bool(c[1]) for c in channels}
        channel_names = list(channel_serial_map.keys()) if channel_serial_map else ["Direct / Self-Pay"]

        cursor.execute("SELECT name FROM room_types WHERE hotel_id = ?", (hotel_id,))
        room_categories = [rt[0] for rt in cursor.fetchall()]

        t1, t2 = st.columns(2)
        with t1:
            check_in = st.date_input("Arrival Date", min_value=datetime.today().date(), key="nr_cin_v2")
        with t2:
            check_out = st.date_input("Departure Date", min_value=check_in, key="nr_cout_v2")

        nights = (check_out - check_in).days

        if nights <= 0:
            st.warning("Departure date must be at least 1 day after arrival date.")
        else:
            st.write("---")
            f1, f2 = st.columns(2)
            with f1:
                filter_opts = ["All"] + room_categories
                selected_cat = st.selectbox("Filter by Category:", filter_opts)

            # Query vacant & operational rooms
            vacant_rooms = db.get_available_rooms(hotel_id, str(check_in), str(check_out), selected_cat)

            with f2:
                if not vacant_rooms:
                    st.error("No vacant rooms available for the selected dates and category.")
                    chosen_room_no = None
                    chosen_room_type = None
                else:
                    room_choices = [f"{r['room_number']} ({r['room_type']}) - Status: {r['housekeeping_status']}" for r in vacant_rooms]
                    sel_r_str = st.selectbox("Assign Available Room:", room_choices)
                    chosen_room_no = sel_r_str.split(" ")[0]
                    chosen_room_type = sel_r_str.split("(")[1].split(")")[0]

            st.write("---")
            g1, g2, g3 = st.columns(3)
            with g1:
                guest_name = st.text_input("Guest Full Name")
                nationality = st.selectbox(
                    "Nationality", 
                    ["Azerbaijan", "Turkey", "United States", "United Kingdom", "Germany", "Russia", "Iran", "Georgia", "Other"]
                )

            with g2:
                sel_channel = st.selectbox("Booking Channel", channel_names)
                agency = st.text_input("Agency / Corporate Company", value="Direct" if sel_channel == "Direct / Self-Pay" else "")

            with g3:
                requires_serial = channel_serial_map.get(sel_channel, False)
                if requires_serial:
                    serial_no = st.text_input("ID / Passport / Voucher Serial (*Mandatory)", key="ser_v2")
                else:
                    serial_no = st.text_input("ID / Passport Serial (Optional)", key="ser_v2_opt")

            st.markdown("##### Minor & Guest Demographics")
            p1, p2, p3, p4 = st.columns(4)
            with p1:
                adults = st.number_input("Adult Guests", min_value=1, max_value=8, value=2)
            with p2:
                kids_6_12 = st.number_input("Children (6-12 yrs)", min_value=0, max_value=4, value=0)
            with p3:
                kids_0_6 = st.number_input("Children (0-6 yrs)", min_value=0, max_value=4, value=0)
            with p4:
                above_12 = st.number_input("Extra Guests (12+ yrs)", min_value=0, max_value=4, value=0)

            # Surcharges & Early Check-in Fee
            st.markdown("##### Folio Adjustments & Surcharges")
            s_col1, s_col2 = st.columns(2)
            with s_col1:
                early_fee = st.number_input(f"Early Check-In Surcharge ({curr})", min_value=0.0, value=0.0, step=10.0)
            with s_col2:
                late_fee = st.number_input(f"Late Check-Out Surcharge ({curr})", min_value=0.0, value=0.0, step=10.0)

            daily_rate = calculate_rate(hotel_id, chosen_room_type if chosen_room_type else "", sel_channel, adults, kids_6_12, kids_0_6, above_12)
            total_accommodation = daily_rate * nights
            total_billable = total_accommodation + early_fee + late_fee

            st.write("---")
            st.markdown("##### Folio Settlement (Payment Details)")
            pay_col1, pay_col2, pay_col3 = st.columns(3)
            with pay_col1:
                deposit_paid = st.number_input(f"Initial Deposit Paid ({curr})", min_value=0.0, max_value=float(total_billable), value=0.0, step=20.0)
            with pay_col2:
                payment_method = st.selectbox("Payment Method", ["Cash", "Credit Card", "Bank Transfer", "Direct Bill"])
            with pay_col3:
                remaining_balance = total_billable - deposit_paid
                st.metric("Outstanding Balance", f"{remaining_balance:,.2f} {curr}")

            b1, b2, b3 = st.columns(3)
            b1.metric("Stay Duration", f"{nights} Nights")
            b2.metric("Daily Tariff", f"{daily_rate:.2f} {curr}")
            b3.metric("Total Billed Portfolio", f"{total_billable:.2f} {curr}")

            if st.button("Confirm Reservation & Commit Folio", use_container_width=True, type="primary"):
                if not guest_name.strip():
                    st.error("Guest full name is mandatory.")
                elif requires_serial and not serial_no.strip():
                    st.error("Voucher / ID Serial number is strictly required for this booking channel.")
                elif not chosen_room_no:
                    st.error("Please select a vacant room to complete booking.")
                else:
                    booking_payload = {
                        "hotel_id": hotel_id,
                        "serial_no": serial_no.strip(),
                        "guest_name": guest_name.strip(),
                        "nationality": nationality,
                        "guest_type": sel_channel,
                        "agency": agency.strip(),
                        "room_number": chosen_room_no,
                        "room_type": chosen_room_type,
                        "check_in": str(check_in),
                        "check_out": str(check_out),
                        "adults": adults,
                        "kids_6_12": kids_6_12,
                        "kids_0_6": kids_0_6,
                        "above_12": above_12,
                        "daily_rate": daily_rate,
                        "total_balance": total_billable,
                        "paid_amount": deposit_paid,
                        "payment_method": payment_method,
                        "early_checkin_fee": early_fee,
                        "late_checkout_fee": late_fee,
                        "created_by": user_context["username"]
                    }

                    # Execute atomic transaction
                    success, msg = db.book_reservation_atomic(booking_payload)
                    if success:
                        st.success(f"Booking confirmed for {guest_name} in Room {chosen_room_no}. Folio initialized.")
                        st.rerun()
                    else:
                        st.error(f"Transaction aborted: {msg}")

    # =========================================================
    # TAB 3: RESERVATION QUEUE & CANCELLATION REQUESTS
    # =========================================================
    with tab_active_res:
        st.subheader("Confirmed Reservation Queue")
        cursor.execute("""
            SELECT id, serial_no, guest_name, room_number, room_type, check_in, check_out, 
                   guest_type, daily_rate, total_balance, paid_amount, created_by, status
            FROM reservations
            WHERE hotel_id = ? AND status IN ('Confirmed', 'Cancellation Requested')
            ORDER BY check_in ASC
        """, (hotel_id,))
        res_queue = cursor.fetchall()

        if not res_queue:
            st.info("No bookings currently in the queue.")
        else:
            df_q = pd.DataFrame(res_queue, columns=[
                "ID", "Serial No", "Guest Name", "Room", "Category", "Arrival", "Departure",
                "Channel", "Daily Rate", "Total Billed", "Paid", "Agent", "Status"
            ])
            st.dataframe(df_q, use_container_width=True)

            st.write("---")
            st.markdown("#### Front Desk Actions")

            confirmed_dict = {f"#{r['id']} - {r['guest_name']} (Room {r['room_number']}, {r['check_in']})": r for r in res_queue if r['status'] == 'Confirmed'}

            if confirmed_dict:
                sel_q_key = st.selectbox("Select Reservation to Action:", list(confirmed_dict.keys()))
                sel_res = confirmed_dict[sel_q_key]
                r_id = sel_res['id']

                act1, act2 = st.columns(2)
                with act1:
                    if st.button("Complete Check-In (In-House)", use_container_width=True, type="primary"):
                        cursor.execute("UPDATE reservations SET status = 'In-House' WHERE id = ? AND hotel_id = ?", (r_id, hotel_id))
                        conn.commit()
                        st.success(f"{sel_res['guest_name']} checked in. Status changed to In-House.")
                        st.rerun()

                with act2:
                    with st.expander("Submit Cancellation Request to Management"):
                        c_reason = st.text_area("State Operational Reason for Cancellation:")
                        if st.button("Submit Request", use_container_width=True):
                            if c_reason.strip():
                                cursor.execute("""
                                    INSERT INTO cancel_requests (hotel_id, reservation_id, requested_by, reason, status)
                                    VALUES (?, ?, ?, ?, 'Pending')
                                """, (hotel_id, r_id, user_context["username"], c_reason.strip()))
                                cursor.execute("UPDATE reservations SET status = 'Cancellation Requested' WHERE id = ? AND hotel_id = ?", (r_id, hotel_id))
                                conn.commit()
                                st.warning("Cancellation request forwarded to Administration.")
                                st.rerun()
                            else:
                                st.error("Please provide a cancellation reason.")

    # =========================================================
    # TAB 4: IN-HOUSE GUESTS, FOLIO SETTLEMENT & CHECK-OUT
    # =========================================================
    with tab_inhouse:
        st.subheader("In-House Guests & Folio Audits")
        cursor.execute("""
            SELECT id, serial_no, guest_name, room_number, room_type, check_in, check_out, 
                   guest_type, daily_rate, total_balance, paid_amount, payment_method, created_by
            FROM reservations
            WHERE hotel_id = ? AND status = 'In-House'
            ORDER BY room_number ASC
        """, (hotel_id,))
        inhouse_list = cursor.fetchall()

        if not inhouse_list:
            st.info("No guests currently in-house.")
        else:
            inhouse_data = []
            for g in inhouse_list:
                bal_due = g['total_balance'] - g['paid_amount']
                inhouse_data.append({
                    "ID": g['id'],
                    "Guest Name": g['guest_name'],
                    "Room": g['room_number'],
                    "Category": g['room_type'],
                    "Arrival": g['check_in'],
                    "Departure": g['check_out'],
                    "Total Billed": f"{g['total_balance']:,.2f} {curr}",
                    "Paid Amount": f"{g['paid_amount']:,.2f} {curr}",
                    "Balance Due": f"{bal_due:,.2f} {curr}",
                    "Payment Method": g['payment_method'],
                    "Agent": g['created_by']
                })
            st.dataframe(pd.DataFrame(inhouse_data), use_container_width=True)

            st.write("---")
            st.markdown("#### Folio Settlement, Room Reassignment & Check-Out")

            inh_dict = {f"Room {g['room_number']} - {g['guest_name']} (Due: {g['total_balance'] - g['paid_amount']:.2f} {curr})": g for g in inhouse_list}
            sel_inh_key = st.selectbox("Select In-House Guest Folio:", list(inh_dict.keys()))
            g_rec = inh_dict[sel_inh_key]

            g_id = g_rec['id']
            g_name = g_rec['guest_name']
            cur_room = g_rec['room_number']
            g_cin = g_rec['check_in']
            g_cout = g_rec['check_out']
            g_daily = g_rec['daily_rate']
            cur_paid = g_rec['paid_amount']
            cur_total = g_rec['total_balance']

            m_col1, m_col2 = st.columns(2)
            with m_col1:
                # Room Reassignment (Vacant only)
                vacant_switch = db.get_available_rooms(hotel_id, g_cin, g_cout, exclude_res_id=g_id)
                switch_opts = [cur_room] + [r['room_number'] for r in vacant_switch if r['room_number'] != cur_room]
                target_room = st.selectbox("Reassign Room (Vacant Clean Only):", switch_opts)

                cursor.execute("SELECT room_type FROM rooms WHERE hotel_id = ? AND room_number = ?", (hotel_id, target_room))
                row_t = cursor.fetchone()
                target_cat = row_t[0] if row_t else g_rec['room_type']
                st.caption(f"Category: **{target_cat}**")

            with m_col2:
                new_departure_date = st.date_input("Adjust Departure Date", value=datetime.strptime(g_cout, "%Y-%m-%d").date(), key="inh_cout_date_v2")

            # Folio Additional Payment
            with st.container(border=True):
                st.markdown("**Folio Payment Settle**")
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    add_payment = st.number_input(f"Record Additional Payment ({curr})", min_value=0.0, value=0.0, step=20.0)
                with p_c2:
                    add_method = st.selectbox("Payment Mode", ["Cash", "Credit Card", "Bank Transfer"])

            act_upd, act_cout = st.columns(2)
            with act_upd:
                if st.button("Save Reassignment / Folio Payment", use_container_width=True):
                    new_nights = (new_departure_date - datetime.strptime(g_cin, "%Y-%m-%d").date()).days
                    updated_total = (g_daily * new_nights)
                    updated_paid = cur_paid + add_payment

                    cursor.execute("""
                        UPDATE reservations 
                        SET room_number = ?, room_type = ?, check_out = ?, total_balance = ?, paid_amount = ?, payment_method = ?
                        WHERE id = ? AND hotel_id = ?
                    """, (target_room, target_cat, str(new_departure_date), updated_total, updated_paid, add_method, g_id, hotel_id))
                    conn.commit()
                    st.success(f"Folio and room assignment updated for {g_name}.")
                    st.rerun()

            with act_cout:
                if st.button("Process Departure (Check-Out)", use_container_width=True, type="secondary"):
                    # 1. Update reservation status to Checked-Out
                    cursor.execute("UPDATE reservations SET status = 'Checked-Out' WHERE id = ? AND hotel_id = ?", (g_id, hotel_id))
                    
                    # 2. AUTOMATIC HOUSEKEEPING TURNOVER: Mark room as Dirty!
                    cursor.execute("UPDATE rooms SET housekeeping_status = 'Dirty' WHERE hotel_id = ? AND room_number = ?", (hotel_id, cur_room))
                    
                    conn.commit()
                    st.success(f"Guest {g_name} checked out. Room {cur_room} released and automatically marked as DIRTY for turnover.")
                    st.rerun()

    conn.close()
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import io
import database as db
import auth

# -------------------------------------------------------------
# 1. EXECUTIVE ANALYTICS DASHBOARD & AUDIT EXPORTS
# -------------------------------------------------------------
def render_admin_dashboard(user_context: dict):
    hotel_id = user_context["hotel_id"]
    curr = user_context.get("currency", "AZN")

    conn = db.get_connection()
    cursor = conn.cursor()

    today_str = datetime.today().strftime("%Y-%m-%d")

    # Inventory Metrics
    cursor.execute("SELECT COUNT(*) FROM rooms WHERE hotel_id = ? AND housekeeping_status != 'Out of Order'", (hotel_id,))
    total_available_rooms = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM rooms WHERE hotel_id = ?", (hotel_id,))
    total_inventory = cursor.fetchone()[0] or 0

    # Operational Movement Today
    cursor.execute("SELECT COUNT(*) FROM reservations WHERE hotel_id = ? AND status = 'Confirmed' AND check_in = ?", (hotel_id, today_str))
    arrivals_today = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM reservations WHERE hotel_id = ? AND status = 'In-House' AND check_out = ?", (hotel_id, today_str))
    departures_today = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM reservations WHERE hotel_id = ? AND status = 'In-House'", (hotel_id,))
    occupied_rooms = cursor.fetchone()[0] or 0

    # Financial Aggregations
    cursor.execute("""
        SELECT COALESCE(SUM(daily_rate), 0) 
        FROM reservations 
        WHERE hotel_id = ? AND status = 'In-House'
    """, (hotel_id,))
    today_room_revenue = cursor.fetchone()[0] or 0.0

    cursor.execute("""
        SELECT COALESCE(SUM(total_balance), 0), COALESCE(SUM(paid_amount), 0)
        FROM reservations 
        WHERE hotel_id = ? AND status IN ('In-House', 'Checked-Out')
    """, (hotel_id,))
    fin_row = cursor.fetchone()
    total_billed = fin_row[0] or 0.0
    settled_cash = fin_row[1] or 0.0

    # Core Hospitality KPI Calculations
    occupancy_pct = (occupied_rooms / total_available_rooms * 100) if total_available_rooms > 0 else 0.0
    adr = (today_room_revenue / occupied_rooms) if occupied_rooms > 0 else 0.0
    revpar = (today_room_revenue / total_available_rooms) if total_available_rooms > 0 else 0.0

    # KPI Summary Row 1: Operations
    st.markdown("##### Operational Pulse (Today)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Today's Expected Arrivals", f"{arrivals_today} Bookings")
    kpi2.metric("Today's Expected Departures", f"{departures_today} Rooms")
    kpi3.metric("Current Occupied Rooms", f"{occupied_rooms} / {total_available_rooms}")
    kpi4.metric("Occupancy Rate", f"{occupancy_pct:.1f}%")

    # KPI Summary Row 2: Financial Yield
    st.markdown("##### Yield & Financial Performance")
    fin1, fin2, fin3, fin4 = st.columns(4)
    fin1.metric("ADR (Avg Daily Rate)", f"{adr:,.2f} {curr}")
    fin2.metric("RevPAR (Rev Per Room)", f"{revpar:,.2f} {curr}")
    fin3.metric("Settled Folio (Cash Flow)", f"{settled_cash:,.2f} {curr}")
    fin4.metric("Total Billed Portfolio", f"{total_billed:,.2f} {curr}")

    st.write("---")

    chart_col, summary_col = st.columns([1.3, 1])
    with chart_col:
        st.subheader("Distribution by Room Category")
        cursor.execute("""
            SELECT room_type, COUNT(*) 
            FROM reservations 
            WHERE hotel_id = ? 
            GROUP BY room_type
        """, (hotel_id,))
        cat_counts = cursor.fetchall()

        if cat_counts:
            df_pie = pd.DataFrame(cat_counts, columns=["Category", "Total Bookings"])
            fig = px.pie(
                df_pie, 
                values="Total Bookings", 
                names="Category", 
                hole=0.45,
                color_discrete_sequence=["#0284C7", "#0F766E", "#D97706", "#4F46E5", "#DB2777"]
            )
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No booking volume recorded yet for distribution visualization.")

    with summary_col:
        st.subheader("Inventory Breakdown")
        cursor.execute("""
            SELECT housekeeping_status, COUNT(*) 
            FROM rooms 
            WHERE hotel_id = ? 
            GROUP BY housekeeping_status
        """, (hotel_id,))
        hk_counts = dict(cursor.fetchall())

        with st.container(border=True):
            st.write(f"**Clean (Ready for Sale):** {hk_counts.get('Clean', 0)} rooms")
            st.write(f"**Dirty (Awaiting Turnover):** {hk_counts.get('Dirty', 0)} rooms")
            st.write(f"**Inspected (Supervisor Approved):** {hk_counts.get('Inspected', 0)} rooms")
            st.write(f"**Out of Order (Maintenance):** {hk_counts.get('Out of Order', 0)} rooms")
            st.write(f"**Total Registered Assets:** {total_inventory} rooms")
            st.progress(min(occupancy_pct / 100.0, 1.0))
            st.caption("Active capacity utilization")

    # --- ADVANCED EXCEL EXPORT ENGINE ---
    st.write("---")
    st.subheader("Official Data Export & Audit Reports")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_d = st.date_input("Audit Period Start", value=datetime.today().date())
    with col_d2:
        end_d = st.date_input("Audit Period End", value=datetime.today().date() + timedelta(days=7))

    if start_d > end_d:
        st.error("Audit start date cannot be later than end date.")
    else:
        exp1, exp2 = st.columns(2)

        # 1. Daily Occupancy & Nationality Audit
        with exp1:
            with st.container(border=True):
                st.markdown("#### 1. Daily Occupancy & Migration Audit")
                st.caption("Daily utilized inventory, domestic vs foreign guest breakdown.")

                daily_records = []
                cur_dt = start_d
                while cur_dt <= end_d:
                    dt_str = cur_dt.strftime("%Y-%m-%d")
                    cursor.execute("""
                        SELECT nationality, COUNT(*) 
                        FROM reservations 
                        WHERE hotel_id = ? AND status IN ('In-House', 'Confirmed') 
                        AND check_in <= ? AND check_out > ?
                        GROUP BY nationality
                    """, (hotel_id, dt_str, dt_str))
                    nat_data = cursor.fetchall()

                    used_rooms = sum([x[1] for x in nat_data])
                    domestic = sum([x[1] for x in nat_data if x[0] == 'Azerbaijan'])
                    foreign = sum([x[1] for x in nat_data if x[0] != 'Azerbaijan'])
                    foreign_breakdown = ", ".join([f"{x[0]}: {x[1]}" for x in nat_data if x[0] != 'Azerbaijan'])

                    daily_records.append({
                        "Date": dt_str,
                        "Occupied Rooms": used_rooms,
                        "Total Inventory": total_inventory,
                        "Occupancy %": round((used_rooms / total_inventory * 100), 1) if total_inventory > 0 else 0.0,
                        "Domestic Guests (Resident)": domestic,
                        "Foreign Guests": foreign,
                        "Foreign Nationalities": foreign_breakdown if foreign_breakdown else "None"
                    })
                    cur_dt += timedelta(days=1)

                df_daily = pd.DataFrame(daily_records)
                buf_daily = io.BytesIO()
                with pd.ExcelWriter(buf_daily, engine='openpyxl') as writer:
                    df_daily.to_excel(writer, index=False, sheet_name="Daily_Occupancy_Audit")

                st.download_button(
                    label="Download Occupancy Audit (.xlsx)",
                    data=buf_daily.getvalue(),
                    file_name=f"Occupancy_Audit_{start_d}_{end_d}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        # 2. Master Guest Registry
        with exp2:
            with st.container(border=True):
                st.markdown("#### 2. Master Guest Registry & Folios")
                st.caption("Complete reservation entries spanning the selected dates.")

                cursor.execute("""
                    SELECT id, serial_no, guest_name, nationality, guest_type, agency, 
                           room_number, room_type, check_in, check_out, 
                           adults, kids_6_12, kids_0_6, above_12, daily_rate, total_balance, 
                           paid_amount, payment_method, early_checkin_fee, late_checkout_fee, status, created_by
                    FROM reservations
                    WHERE hotel_id = ? AND check_in <= ? AND check_out >= ?
                    ORDER BY check_in ASC
                """, (hotel_id, end_d.strftime("%Y-%m-%d"), start_d.strftime("%Y-%m-%d")))
                all_res = cursor.fetchall()

                reg_cols = [
                    "ID", "Serial No", "Guest Name", "Nationality", "Channel", "Agency",
                    "Room No", "Category", "Check-In", "Check-Out",
                    "Adults", "Kids (6-12)", "Kids (0-6)", "Guests (12+)", "Daily Rate", "Total Billed",
                    "Settled Cash", "Payment Method", "Early In Fee", "Late Out Fee", "Status", "Agent"
                ]
                df_reg = pd.DataFrame(all_res, columns=reg_cols) if all_res else pd.DataFrame(columns=reg_cols)
                buf_reg = io.BytesIO()
                with pd.ExcelWriter(buf_reg, engine='openpyxl') as writer:
                    df_reg.to_excel(writer, index=False, sheet_name="Master_Registry")

                st.download_button(
                    label="Download Master Registry (.xlsx)",
                    data=buf_reg.getvalue(),
                    file_name=f"Master_Registry_{start_d}_{end_d}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

    conn.close()

# -------------------------------------------------------------
# 2. SYSTEM SETTINGS, HOUSEKEEPING & INVENTORY
# -------------------------------------------------------------
def render_admin_settings(user_context: dict):
    hotel_id = user_context["hotel_id"]
    curr = user_context.get("currency", "AZN")

    tab_inv, tab_cat, tab_pricing, tab_channels, tab_users, tab_cancels, tab_archive = st.tabs([
        "Room Inventory & Housekeeping",
        "Room Categories & Pricing",
        "Tariffs & Surcharges",
        "Booking Channels",
        "Staff Accounts",
        "Cancellation Approvals",
        "Departure Archive"
    ])

    conn = db.get_connection()
    cursor = conn.cursor()

    # --- TAB 1: ROOM INVENTORY & HOUSEKEEPING STATUS CONTROL ---
    with tab_inv:
        st.subheader("Physical Inventory & Housekeeping Control")
        col_r1, col_r2 = st.columns([1, 1.5])

        with col_r1:
            with st.container(border=True):
                st.markdown("**Register Individual Room**")
                r_num = st.text_input("Room Number (e.g., 101, 204)")
                r_floor = st.number_input("Floor", min_value=1, max_value=30, value=1)

                cursor.execute("SELECT name FROM room_types WHERE hotel_id = ?", (hotel_id,))
                cat_options = [x[0] for x in cursor.fetchall()]

                if not cat_options:
                    st.warning("Please configure at least one room category in the next tab first.")
                    r_cat = None
                else:
                    r_cat = st.selectbox("Assign Category", cat_options)

                r_hk = st.selectbox("Initial Housekeeping Status", ["Clean", "Inspected", "Dirty", "Out of Order"])

                if st.button("Register Room into Inventory", use_container_width=True):
                    if r_num.strip() and r_cat:
                        try:
                            cursor.execute("""
                                INSERT INTO rooms (hotel_id, room_number, room_type, floor, housekeeping_status)
                                VALUES (?, ?, ?, ?, ?)
                            """, (hotel_id, r_num.strip(), r_cat, r_floor, r_hk))
                            conn.commit()
                            st.success(f"Room {r_num} added to inventory.")
                            st.rerun()
                        except:
                            st.error(f"Room {r_num} already exists in this property.")

        with col_r2:
            cursor.execute("SELECT id, room_number, room_type, floor, housekeeping_status FROM rooms WHERE hotel_id = ? ORDER BY floor, room_number", (hotel_id,))
            rooms_list = cursor.fetchall()

            if rooms_list:
                df_rooms = pd.DataFrame(rooms_list, columns=["ID", "Room No", "Category", "Floor", "Housekeeping Status"])
                st.dataframe(df_rooms, use_container_width=True)

                with st.expander("Update Room Housekeeping Status / Delete"):
                    sel_rid = st.selectbox("Select Room to Update:", [r[0] for r in rooms_list], format_func=lambda x: [f"Room {r[1]} ({r[4]})" for r in rooms_list if r[0]==x][0])
                    sel_r_obj = [r for r in rooms_list if r[0] == sel_rid][0]

                    new_hk = st.selectbox("Assign Housekeeping Status:", ["Clean", "Inspected", "Dirty", "Out of Order"], index=["Clean", "Inspected", "Dirty", "Out of Order"].index(sel_r_obj[4]))

                    b_hk_upd, b_hk_del = st.columns(2)
                    with b_hk_upd:
                        if st.button("Update Status", key="btn_hk_upd"):
                            cursor.execute("UPDATE rooms SET housekeeping_status = ? WHERE id = ? AND hotel_id = ?", (new_hk, sel_rid, hotel_id))
                            conn.commit()
                            st.success("Housekeeping status updated.")
                            st.rerun()
                    with b_hk_del:
                        if st.button("Delete Room", key="btn_hk_del", type="secondary"):
                            cursor.execute("DELETE FROM rooms WHERE id = ? AND hotel_id = ?", (sel_rid, hotel_id))
                            conn.commit()
                            st.warning("Room removed from inventory.")
                            st.rerun()

    # --- TAB 2: ROOM CATEGORIES (DOUBLE & SINGLE RATES) ---
    with tab_cat:
        st.subheader("Room Categories (Base & Single Rates)")
        c1, c2 = st.columns([1, 1.5])

        with c1:
            with st.container(border=True):
                st.markdown("**Add Room Category**")
                c_name = st.text_input("Category Name (e.g., Deluxe Suite)")
                c_base = st.number_input(f"Base Tariff (2 Persons, {curr})", min_value=10.0, value=190.0, step=5.0)
                c_single = st.number_input(f"Single Occupancy Tariff (1 Person, {curr})", min_value=10.0, value=142.5, step=2.5)
                c_cap = st.number_input("Max Capacity (Persons)", min_value=1, value=2)

                if st.button("Save Category", use_container_width=True):
                    if c_name.strip():
                        try:
                            cursor.execute("""
                                INSERT INTO room_types (hotel_id, name, base_price, single_price, capacity)
                                VALUES (?, ?, ?, ?, ?)
                            """, (hotel_id, c_name.strip(), c_base, c_single, c_cap))
                            conn.commit()
                            st.success(f"Category '{c_name}' created.")
                            st.rerun()
                        except:
                            st.error("A category with this name already exists in this property.")

        with c2:
            cursor.execute("SELECT id, name, base_price, single_price, capacity FROM room_types WHERE hotel_id = ?", (hotel_id,))
            cats = cursor.fetchall()

            if cats:
                df_cats = pd.DataFrame(cats, columns=["ID", "Category", "Base Rate", "Single Rate", "Capacity"])
                st.dataframe(df_cats, use_container_width=True)

                with st.expander("Edit or Remove Category"):
                    sel_cid = st.selectbox("Select Category:", [c[0] for c in cats], format_func=lambda x: [c[1] for c in cats if c[0]==x][0])
                    sel_cat = [c for c in cats if c[0] == sel_cid][0]

                    ec_name = st.text_input("Name:", value=sel_cat[1], key="ec_name")
                    ec_base = st.number_input(f"Base Rate ({curr}):", value=float(sel_cat[2]), step=5.0, key="ec_base")
                    ec_single = st.number_input(f"Single Rate ({curr}):", value=float(sel_cat[3]), step=2.5, key="ec_single")
                    ec_cap = st.number_input("Capacity:", value=int(sel_cat[4]), key="ec_cap")

                    c_upd, c_del = st.columns(2)
                    with c_upd:
                        if st.button("Save Changes", key="btn_cupd"):
                            cursor.execute("""
                                UPDATE room_types SET name=?, base_price=?, single_price=?, capacity=?
                                WHERE id=? AND hotel_id=?
                            """, (ec_name.strip(), ec_base, ec_single, ec_cap, sel_cid, hotel_id))
                            conn.commit()
                            st.success("Category updated.")
                            st.rerun()
                    with c_del:
                        if st.button("Delete Category", key="btn_cdel", type="secondary"):
                            cursor.execute("DELETE FROM room_types WHERE id=? AND hotel_id=?", (sel_cid, hotel_id))
                            conn.commit()
                            st.warning("Category removed.")
                            st.rerun()

    # --- TAB 3: TARIFFS & SUPPLEMENTAL SURCHARGES ---
    with tab_pricing:
        st.subheader("Supplemental Surcharges (Children & Extra Beds)")
        st.caption("Daily automatic fees factored into bookings during calculation.")

        cursor.execute("SELECT rule_key, title, price FROM pricing_rules WHERE hotel_id = ?", (hotel_id,))
        rules = cursor.fetchall()

        with st.form("admin_tariffs_form"):
            upd_vals = {}
            for k, title, val in rules:
                upd_vals[k] = st.number_input(f"{title} ({curr}):", min_value=0.0, value=float(val), step=2.5)

            if st.form_submit_button("Update All Surcharges"):
                for k, v in upd_vals.items():
                    cursor.execute("UPDATE pricing_rules SET price = ? WHERE rule_key = ? AND hotel_id = ?", (v, k, hotel_id))
                conn.commit()
                st.success("Surcharge policies updated.")
                st.rerun()

    # --- TAB 4: BOOKING CHANNELS / GUEST TYPES ---
    with tab_channels:
        st.subheader("Booking Channels & Billability")
        g1, g2 = st.columns([1, 1.5])

        with g1:
            with st.container(border=True):
                st.markdown("**New Channel / Guest Type**")
                gt_name = st.text_input("Channel Title (e.g., Corporate Partner, VIP)")
                gt_pay = st.checkbox("Billable to Guest (Uncheck for Vouchers/Comp)", value=True)
                gt_ser = st.checkbox("Require Serial / ID No (*Mandatory for vouchers)", value=False)

                if st.button("Save Channel", use_container_width=True):
                    if gt_name.strip():
                        try:
                            cursor.execute("""
                                INSERT INTO guest_types (hotel_id, name, is_payable, require_serial)
                                VALUES (?, ?, ?, ?)
                            """, (hotel_id, gt_name.strip(), 1 if gt_pay else 0, 1 if gt_ser else 0))
                            conn.commit()
                            st.success("Channel added.")
                            st.rerun()
                        except:
                            st.error("Channel name already registered in this property.")

        with g2:
            cursor.execute("SELECT id, name, is_payable, require_serial FROM guest_types WHERE hotel_id = ?", (hotel_id,))
            gt_list = cursor.fetchall()

            if gt_list:
                df_gt = pd.DataFrame(gt_list, columns=["ID", "Channel", "Billable (1/0)", "Require Serial (1/0)"])
                st.dataframe(df_gt, use_container_width=True)

                with st.expander("Modify Channel"):
                    sel_gtid = st.selectbox("Select Channel:", [x[0] for x in gt_list], format_func=lambda x: [y[1] for y in gt_list if y[0]==x][0])
                    sel_gobj = [x for x in gt_list if x[0] == sel_gtid][0]

                    eg_name = st.text_input("Name:", value=sel_gobj[1], key="eg_name")
                    eg_pay = st.checkbox("Billable:", value=bool(sel_gobj[2]), key="eg_pay")
                    eg_ser = st.checkbox("Require Serial:", value=bool(sel_gobj[3]), key="eg_ser")

                    g_upd, g_del = st.columns(2)
                    with g_upd:
                        if st.button("Update Channel", key="btn_gupd"):
                            cursor.execute("""
                                UPDATE guest_types SET name=?, is_payable=?, require_serial=?
                                WHERE id=? AND hotel_id=?
                            """, (eg_name.strip(), 1 if eg_pay else 0, 1 if eg_ser else 0, sel_gtid, hotel_id))
                            conn.commit()
                            st.success("Updated.")
                            st.rerun()
                    with g_del:
                        if st.button("Delete Channel", key="btn_gdel", type="secondary"):
                            cursor.execute("DELETE FROM guest_types WHERE id=? AND hotel_id=?", (sel_gtid, hotel_id))
                            conn.commit()
                            st.warning("Deleted.")
                            st.rerun()

    # --- TAB 5: STAFF & ACCESS CONTROL ---
    with tab_users:
        st.subheader("Staff Accounts & Role Assignments")
        u1, u2 = st.columns([1, 1.5])

        with u1:
            with st.container(border=True):
                st.markdown("**Create Staff Account**")
                uname = st.text_input("Username")
                fname = st.text_input("Full Name")
                pwd = st.text_input("Password", type="password")
                role = st.selectbox("Operational Role", ["reception", "housekeeping", "admin"])

                if st.button("Register Account", use_container_width=True):
                    if uname.strip() and fname.strip() and pwd.strip():
                        try:
                            pwd_hash = auth.hash_password(pwd.strip())
                            cursor.execute("""
                                INSERT INTO users (hotel_id, username, password_hash, full_name, role)
                                VALUES (?, ?, ?, ?, ?)
                            """, (hotel_id, uname.strip(), pwd_hash, fname.strip(), role))
                            conn.commit()
                            st.success(f"Account for {fname} established.")
                            st.rerun()
                        except:
                            st.error("Username already registered.")

        with u2:
            cursor.execute("SELECT id, username, full_name, role, created_at FROM users WHERE hotel_id = ?", (hotel_id,))
            staff = cursor.fetchall()
            df_staff = pd.DataFrame(staff, columns=["ID", "Username", "Full Name", "Role", "Created At"])
            st.dataframe(df_staff, use_container_width=True)

            with st.expander("Modify Staff Account"):
                if staff:
                    sel_uid = st.selectbox("Select Account:", [x[0] for x in staff], format_func=lambda x: [f"@{y[1]} ({y[2]})" for y in staff if y[0]==x][0])
                    sel_uobj = [x for x in staff if x[0] == sel_uid][0]

                    eu_name = st.text_input("Full Name:", value=sel_uobj[2], key="eu_name")
                    eu_role = st.selectbox("Role:", ["reception", "housekeeping", "admin"], index=["reception", "housekeeping", "admin"].index(sel_uobj[3]), key="eu_role")
                    eu_pwd = st.text_input("New Password (Leave empty to keep unchanged):", type="password", key="eu_pwd")

                    u_upd, u_del = st.columns(2)
                    with u_upd:
                        if st.button("Update Account", key="btn_uupd"):
                            if eu_pwd.strip():
                                nh = auth.hash_password(eu_pwd.strip())
                                cursor.execute("UPDATE users SET full_name=?, role=?, password_hash=? WHERE id=? AND hotel_id=?", (eu_name.strip(), eu_role, nh, sel_uid, hotel_id))
                            else:
                                cursor.execute("UPDATE users SET full_name=?, role=? WHERE id=? AND hotel_id=?", (eu_name.strip(), eu_role, sel_uid, hotel_id))
                            conn.commit()
                            st.success("Account updated.")
                            st.rerun()
                    with u_del:
                        if st.button("Delete Account", key="btn_udel", type="secondary"):
                            if sel_uobj[1] == 'admin':
                                st.error("Root manager account cannot be deleted.")
                            else:
                                cursor.execute("DELETE FROM users WHERE id=? AND hotel_id=?", (sel_uid, hotel_id))
                                conn.commit()
                                st.warning("Staff account deleted.")
                                st.rerun()

    # --- TAB 6: CANCELLATION REQUESTS APPROVAL ---
    with tab_cancels:
        st.subheader("Reservation Cancellation Approvals")
        cursor.execute("""
            SELECT cr.id, cr.reservation_id, r.guest_name, r.room_number, cr.requested_by, cr.reason, cr.created_at
            FROM cancel_requests cr
            JOIN reservations r ON cr.reservation_id = r.id
            WHERE cr.hotel_id = ? AND cr.status = 'Pending'
            ORDER BY cr.created_at DESC
        """, (hotel_id,))
        cancels = cursor.fetchall()

        if not cancels:
            st.info("No pending cancellation requests in queue.")
        else:
            for c_id, res_id, g_name, r_num, agent, reason, created_at in cancels:
                with st.container(border=True):
                    st.write(f"**Booking ID:** #{res_id} | **Guest:** {g_name} | **Room:** {r_num}")
                    st.write(f"**Requested by Agent:** @{agent} | **Timestamp:** {created_at}")
                    st.error(f"**Reason:** {reason}")

                    c_act1, c_act2, _ = st.columns([1.2, 1.2, 3])
                    with c_act1:
                        if st.button("Authorize Cancellation", key=f"capp_{c_id}", type="primary"):
                            cursor.execute("UPDATE cancel_requests SET status = 'Approved' WHERE id = ?", (c_id,))
                            cursor.execute("UPDATE reservations SET status = 'Cancelled' WHERE id = ?", (res_id,))
                            conn.commit()
                            st.success(f"Booking #{res_id} cancelled.")
                            st.rerun()
                    with c_act2:
                        if st.button("Reject Request", key=f"crej_{c_id}"):
                            cursor.execute("UPDATE cancel_requests SET status = 'Rejected' WHERE id = ?", (c_id,))
                            cursor.execute("UPDATE reservations SET status = 'Confirmed' WHERE id = ?", (res_id,))
                            conn.commit()
                            st.info("Request rejected. Booking remains confirmed.")
                            st.rerun()

    # --- TAB 7: HISTORICAL DEPARTURE ARCHIVE ---
    with tab_archive:
        st.subheader("Historical Departure Archive (Checked-Out)")
        cursor.execute("""
            SELECT id, serial_no, guest_name, nationality, guest_type, agency, 
                   room_number, room_type, check_in, check_out, 
                   adults, kids_6_12, kids_0_6, above_12, daily_rate, total_balance, 
                   paid_amount, payment_method, created_by
            FROM reservations
            WHERE hotel_id = ? AND status = 'Checked-Out'
            ORDER BY check_out DESC
        """, (hotel_id,))
        arch_data = cursor.fetchall()

        if not arch_data:
            st.info("No checked-out guest records archived yet.")
        else:
            total_arch_guests = len(arch_data)
            total_arch_rev = sum([r[15] for r in arch_data])

            a1, a2, a3 = st.columns([1, 1, 1.5])
            a1.metric("Archived Departures", f"{total_arch_guests} Records")
            a2.metric("Realized Portfolio", f"{total_arch_rev:,.2f} {curr}")
            with a3:
                s_query = st.text_input("Search Archive (Name, Serial, Room):", key="arch_query")

            arch_cols = [
                "Booking ID", "ID / Serial", "Guest Name", "Nationality", "Channel", "Agency",
                "Room No", "Category", "Check-In", "Check-Out",
                "Adults", "Kids (6-12)", "Kids (0-6)", "Guests (12+)", "Daily Rate", "Total Billed",
                "Paid Cash", "Payment Method", "Created By"
            ]
            df_arch = pd.DataFrame(arch_data, columns=arch_cols)

            if s_query.strip():
                sq = s_query.strip().lower()
                df_arch = df_arch[
                    df_arch["Guest Name"].str.lower().str.contains(sq) |
                    df_arch["ID / Serial"].str.lower().str.contains(sq) |
                    df_arch["Room No"].str.lower().str.contains(sq)
                ]

            st.dataframe(df_arch, use_container_width=True)

            buf_arch = io.BytesIO()
            with pd.ExcelWriter(buf_arch, engine='openpyxl') as writer:
                df_arch.to_excel(writer, index=False, sheet_name="Checked_Out_Archive")

            st.download_button(
                label="Export Archive to Excel (.xlsx)",
                data=buf_arch.getvalue(),
                file_name=f"Departure_Archive_{datetime.today().strftime('%Y_%m_%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

    conn.close()
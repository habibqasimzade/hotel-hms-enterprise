import os
import sys
import streamlit as st

# Dynamically resolve and inject the 'src' directory into the system search path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import database as db
import auth
import admin_panel as ap
import reception_panel as rp

# Page configuration
st.set_page_config(
    page_title="HMS | by Habib Qasimzade",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema and verify root tables
db.init_db()

# Modern B2B SaaS Enterprise styling and immutable author attribution
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .author-watermark {
        position: fixed;
        bottom: 14px;
        right: 18px;
        background: rgba(15, 23, 42, 0.94);
        color: #F8FAFC;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25);
        z-index: 999999;
        pointer-events: none;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .author-sidebar-box {
        margin-top: 30px;
        padding: 12px;
        border-radius: 8px;
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        text-align: center;
        font-size: 11px;
        line-height: 1.6;
        color: #94A3B8;
    }
    .property-badge {
        background-color: #0369A1;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 8px;
    }
</style>
<div class="author-watermark">
    HMS • Created by <b>Habib Qasimzade</b>
</div>
""", unsafe_allow_html=True)

# Initialize session state variables
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_context" not in st.session_state:
    st.session_state.user_context = None

def handle_logout():
    """Clears authentication session state and forces a clean UI refresh."""
    st.session_state.authenticated = False
    st.session_state.user_context = None
    st.rerun()

# -------------------------------------------------------------
# 1. AUTHENTICATION & MULTI-TENANT ONBOARDING WORKSPACE
# -------------------------------------------------------------
if not st.session_state.authenticated:
    st.write("")
    st.write("")
    _, center_col, _ = st.columns([1, 1.3, 1])

    with center_col:
        st.markdown("<h2 style='text-align: center; margin-bottom: 2px;'>HMS</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 14px;'>Multi-Property Hospitality Operating System</p>", unsafe_allow_html=True)
        
        login_tab, register_tab = st.tabs(["Sign In to Property", "Register New Hotel (Tenant)"])

        # TAB 1: Operator Sign-In
        with login_tab:
            with st.container(border=True):
                login_user = st.text_input("Username", key="login_u")
                login_pass = st.text_input("Password", type="password", key="login_p")
                
                st.write("")
                if st.button("Sign In to Workstation", use_container_width=True, type="primary"):
                    if not login_user.strip() or not login_pass.strip():
                        st.warning("Please provide both username and password.")
                    else:
                        user_ctx = auth.authenticate_user(login_user, login_pass)
                        if user_ctx:
                            st.session_state.authenticated = True
                            st.session_state.user_context = user_ctx
                            st.rerun()
                        else:
                            st.error("Authentication failed. Invalid username or password.")
            
            st.caption("Default root login: **admin** | Password: **admin123**")

        # TAB 2: Autonomous Property Onboarding (Multi-Tenancy)
        with register_tab:
            with st.container(border=True):
                st.markdown("##### Property Onboarding")
                new_h_name = st.text_input("Hotel / Resort Name", placeholder="e.g., Caspian Palace Hotel")
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    new_h_code = st.text_input("Unique Hotel Code", placeholder="e.g., CPH01")
                with col_c2:
                    new_h_curr = st.selectbox("Base Currency", ["AZN", "USD", "EUR", "TRY"])

                st.markdown("##### General Manager Credentials")
                new_admin_user = st.text_input("Manager Username", key="reg_adm_u")
                new_admin_name = st.text_input("Manager Full Name", key="reg_adm_fn")
                new_admin_pass = st.text_input("Manager Password", type="password", key="reg_adm_p")

                if st.button("Register & Initialize Property", use_container_width=True):
                    if not (new_h_name.strip() and new_h_code.strip() and new_admin_user.strip() and new_admin_pass.strip()):
                        st.warning("Please fill in all property and administrator fields.")
                    else:
                        success, message = auth.register_new_hotel(
                            new_h_name, new_h_code, new_h_curr,
                            new_admin_user, new_admin_pass, new_admin_name
                        )
                        if success:
                            st.success(f"{message} You can now sign in using your manager credentials.")
                        else:
                            st.error(f"Registration failed: {message}")

# -------------------------------------------------------------
# 2. OPERATIONAL WORKSPACE (AUTHENTICATED SESSION)
# -------------------------------------------------------------
else:
    u = st.session_state.user_context

    with st.sidebar:
        # Tenant Metadata Header
        st.markdown(f"<div class='property-badge'>{u['hotel_code']} • {u['currency']}</div>", unsafe_allow_html=True)
        st.markdown(f"#### {u['hotel_name']}")
        
        # User Role Translation
        role_titles = {
            "admin": "General Manager",
            "reception": "Front Desk Agent",
            "housekeeping": "Housekeeping Supervisor"
        }
        user_role_label = role_titles.get(u.get('role'), u.get('role', 'Staff'))
        st.caption(f"Operator: **{u['full_name']}** ({user_role_label})")
        st.write("---")

        # Role-based workspace navigation routing
        if u.get('role') == 'admin':
            menu_selection = st.radio(
                "Property Navigation",
                ["Executive Analytics & KPIs", "System Settings & Inventory", "Front Desk Operations"]
            )
        else:
            menu_selection = st.radio(
                "Property Navigation",
                ["Front Desk Operations"]
            )

        st.write("---")
        if st.button("Sign Out", use_container_width=True):
            handle_logout()

        # Immutable copyright and developer license block
        st.markdown("""
        <div class="author-sidebar-box">
            <b>HMS v1.0</b><br>
            Architect & Author:<br>
            <b>Habib Qasimzade</b><br>
            All rights reserved © 2026
        </div>
        """, unsafe_allow_html=True)

    # Route view execution based on selected module
    if menu_selection == "Executive Analytics & KPIs":
        st.markdown(f"### Executive Performance Dashboard - {u['hotel_name']}")
        st.caption("Real-time revenue metrics, capacity yield (ADR & RevPAR), and governmental migration audit exports.")
        ap.render_admin_dashboard(u)

    elif menu_selection == "System Settings & Inventory":
        st.markdown(f"### Property Configuration & Inventory - {u['hotel_name']}")
        st.caption("Manage physical rooms, housekeeping statuses, category tariffs, staff accounts, and departure archives.")
        ap.render_admin_settings(u)

    elif menu_selection == "Front Desk Operations":
        st.markdown(f"### Front Desk Workstation - {u['hotel_name']}")
        st.caption("Live room rack, housekeeping turnover, atomic reservation intake, folio settlements, and departures.")
        rp.render_reception_panel(u)
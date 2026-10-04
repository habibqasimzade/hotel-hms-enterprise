# 🏨 Enterprise Multi-Tenant Hotel Property Management System (HMS)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework-Streamlit](https://img.shields.io/badge/Framework-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![Database-SQLite%20%2F%20Postgres--Ready](https://img.shields.io/badge/Database-SQLite%20%7C%20Postgres--Ready-informational.svg)]()
[![Tests-Pytest%20Passing](https://img.shields.io/badge/Tests-Pytest%20Passing-success.svg)](https://docs.pytest.org/)
[![License-MIT](https://img.shields.io/badge/License-MIT-green.svg)]()

> Designed and engineered by **Habib Qasimzade**  
> *Translating real-world hospitality domain expertise into an enterprise-grade cloud operating system.*

---

## 📌 Executive Summary & Problem Statement

Small-to-midsize accommodation providers and resort properties frequently struggle with fragmented software stacks: disjointed spreadsheets for billing, uncoordinated communication with housekeeping teams, and vulnerability to double-booking (overbooking) anomalies during peak walk-in and OTA arrival hours.

Drawing from hands-on front desk operational experience, this **Hotel Property Management System (HMS)** was engineered from the ground up to address these pain points. Built on a strict multi-tenant architecture, the platform enforces atomic reservation transactions, provides dynamic single vs. double occupancy rate engines, automates room turnover protocols, and computes executive-level hospitality decision metrics (**ADR, RevPAR, Real-Time Occupancy**).

---

## 🧱 Architectural Highlights & Core Capabilities

### 1. 🏢 Multi-Tenant Property Isolation
* Complete multi-property partitioning using tenant-bound scoping (`hotel_id`).
* Independent currency assignment, operational tariffs, and staff hierarchies for each registered hotel.
* Zero cross-tenant data leakage via scoped SQL execution.

### 2. 🛡️ Concurrency Control & Double-Booking Prevention Engine
* Overbooking prevention powered by an inverted interval collision algorithm:
  $$\text{Collision} \iff \neg (\text{CheckOut}_{\text{new}} \le \text{CheckIn}_{\text{existing}} \lor \text{CheckIn}_{\text{new}} \ge \text{CheckOut}_{\text{existing}})$$
* Enforced with **atomic transaction locks** (`BEGIN IMMEDIATE TRANSACTION`), ensuring thread-safe reservations even when two receptionists attempt to reserve the same inventory simultaneously.

### 3. 🧹 Automated Housekeeping Turnover Cycle
* Real-world operational room states: `Clean`, `Dirty`, `Inspected`, `Out of Order`.
* **Automatic Turnover Logic:** When a guest checks out, the room is automatically quarantined into `Dirty` status. It is systematically prevented from being assigned to incoming arrivals until marked as `Clean` or `Inspected`.

### 4. 💳 Guest Folio & Split-Settlement Billing
* Comprehensive guest portfolio management tracking:
  * Room accommodation base rates + dynamic minor surcharges.
  * Operational adjustments (Early Check-In / Late Check-Out fees).
  * Deposit intake, payment mode tracking (`Cash`, `Credit Card`, `Bank Transfer`, `Direct Bill`), and live outstanding balance due.

### 5. 📈 Executive Decision-Support KPIs & Official Audits
* Real-time hospitality analytics:
  * **Today's Expected Movements:** Live monitor of arrivals and departures.
  * **ADR (Average Daily Rate):** $\frac{\text{Room Revenue}}{\text{Occupied Rooms}}$
  * **RevPAR (Revenue Per Available Room):** $\frac{\text{Room Revenue}}{\text{Total Operational Inventory}}$
* Dual-channel official Excel exports (`openpyxl` engine):
  * **Migration & Daily Occupancy Audit:** Resident vs. Foreign visitor ratio and nationality distribution for local compliance.
  * **Master Guest Registry:** Complete historical audits.

---

## 📊 Database Schema (Entity-Relationship Diagram)

The system adheres to 3NF relational modeling with enforced foreign key cascades:

```mermaid
erDiagram
    HOTELS ||--o{ USERS : "employs"
    HOTELS ||--o{ ROOM_TYPES : "configures"
    HOTELS ||--o{ ROOMS : "manages"
    HOTELS ||--o{ GUEST_TYPES : "defines"
    HOTELS ||--o{ PRICING_RULES : "sets"
    HOTELS ||--o{ RESERVATIONS : "records"
    HOTELS ||--o{ GUEST_PROFILES : "maintains"
    ROOM_TYPES ||--o{ ROOMS : "categorizes"
    ROOMS ||--o{ RESERVATIONS : "allocates"
    RESERVATIONS ||--o{ CANCEL_REQUESTS : "audits"

    HOTELS {
        int id PK
        string hotel_name
        string hotel_code UK
        string currency
        datetime created_at
    }

    USERS {
        int id PK
        int hotel_id FK
        string username UK
        string password_hash
        string full_name
        string role
        datetime created_at
    }

    ROOM_TYPES {
        int id PK
        int hotel_id FK
        string name
        float base_price
        float single_price
        int capacity
    }

    ROOMS {
        int id PK
        int hotel_id FK
        string room_number
        string room_type
        int floor
        string housekeeping_status
    }

    RESERVATIONS {
        int id PK
        int hotel_id FK
        string serial_no
        string guest_name
        string nationality
        string guest_type
        string room_number FK
        string check_in
        string check_out
        float daily_rate
        float total_balance
        float paid_amount
        string payment_method
        string status
        string created_by
    }

    CANCEL_REQUESTS {
        int id PK
        int hotel_id FK
        int reservation_id FK
        string requested_by
        string reason
        string status
        datetime created_at
    }
   
🛠️ Technology Stack
Layer              Technology                Purpose   
Frontend & UI      Streamlit                 Responsive, high-velocity SaaS dashboard interface 
Application Logic  Python 3.10+              Core domain logic, tariff calculators, routing
Data Storage       SQLite (PostgreSQL Ready) Relational persistence with immediate transaction locking
Security & Auth    bcrypt                    Salted cryptographical password hashing
Analytics Engine   Plotly Express & Pandas   Capacity utilization and revenue distribution charting
Reporting & Export OpenPyXL                  Compliant dual-report .xlsx binary data generation
Quality Assurance  Pytest                    Automated mathematical unit tests for collisions and tariffs

🚀 Quickstart & Local Installation
Prerequisites:
Python 3.10 or higher
Git

1. Clone the Repository
git clone [https://github.com/](https://github.com/)<habibqasimzade>/hotel-hms-enterprise.git
cd hotel-hms-enterprise

2. Set Up a Virtual Environment
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

3. Install Dependencies
pip install -r requirements.txt

4. Execute Automated Unit Tests
Verify mathematical collision logic and pricing integrity:
pytest

5. Launch the Enterprise Application
streamlit run app.py
Open your browser and navigate to http://localhost:8501 .

🔑 Default Credentials
The platform initializes with a seeded demonstration tenant:

Demonstration Hotel: Grand Resort & Spa (Code: GR01)

Manager Username: admin

Default Password: admin123

New hotels and isolated tenant spaces can be instantiated autonomously via the "Register New Hotel" tab on the authentication portal.

🧪 Verification & Automated Testing
The automated test suite in tests/test_core.py validates critical operational assertions:

test_collision_math_logic: Validates boundary-condition edge cases (adjacent dates vs. overlapping date spans).

test_single_vs_double_pricing_calculation: Asserts dynamic policy calculation for single-occupant deductions and non-billable corporate voucher exemptions.

👤 Author & Architectural Contact
Habib Qasimzade  Instagram: @habibqasimzade ; Linkedin: linkedin.com/in/habibqasimzade

Business & AI Product Architect | Hospitality Tech Specialist

Developed as an enterprise-grade portfolio solution showcasing clean code architecture, domain-driven design, and financial analytics.

📄 License
This project is open-source software licensed under the MIT License.
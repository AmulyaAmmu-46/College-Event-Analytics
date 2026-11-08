# COLLEGE EVENT ANALYTICS SYSTEM
### A Smart Web-Based Platform for Event Management, Student Participation Tracking, and Performance Analytics

A complete, modern, professional web application designed for engineering colleges and universities to streamline event scheduling, enforce venue conflict prevention, manage student registrations, record real-time attendance, analyze student feedback, and compute multi-department performance analytics.

---

## 1. System Architecture & Portal Separation

The system features two completely separated and role-governed portals:

### 1. Admin Portal (`/auth/admin-login` & `/admin/dashboard`)
- **Dedicated Admin Authentication**: Independent login isolated from student registration; restricted to administrators and faculty coordinators.
- **Admin Analytics Dashboard**: 8 live summary KPI cards, department participation progress, recent registrations, and quick action shortcuts.
- **Event Scheduling & Management**: Full form with 10 event categories, 3 event types (Offline, Online, Hybrid), venue conflict detection, capacity limits, multi-department assignment, and college-wide event support.
- **Interactive Event Calendar**: Built-in FullCalendar providing Day, Week, and Month views of all scheduled campus events.
- **Registered Student Management**: Dedicated register with multi-criteria filtering by event, department, academic year, search by USN, cancellation with audit logs, and CSV export.
- **Attendance Management Module**: Mark individual students as *Present*, *Absent*, or *Excused*; bulk attendance marking tools; audit timestamps of the marking coordinator; live attendance rate calculations; and CSV attendance sheet exports.
- **Department Administration**: Native support and management for all 9 academic engineering/technology departments.
- **Student Account Management**: Browse student profiles, filter by department, inspect registration history, and activate/deactivate accounts.
- **Feedback Management & Analysis**: View satisfaction, organization, content, and venue ratings; rating distributions (1–5 stars); and algorithmic keyword sentiment themes.
- **Analytics & Popularity Scoring**: 8 interactive Chart.js visualizations backed by real database records with dynamic filtering and transparent event popularity score breakdowns.
- **Report Export Center**: Downloadable CSV reports across 6 dimensions.
- **In-App Notification Center & Audit Logs**: Real-time notifications and immutable audit trail recording administrative actions.

### 2. Student Portal (`/auth/login` & `/students/dashboard`)
- **Student Registration**: Register with Full Name, USN/Student ID, Email, Phone Number, Department (9 departments), Academic Year, and password.
- **Student Authentication**: Sign in using either college Email or University Seat Number (USN).
- **Student Dashboard**: Personalized dashboard with welcome banner, 5 KPI summary cards (Total Registered, Upcoming, Completed, Attended, Pending Feedback), and pending feedback alerts.
- **Browse & Search Events**: Filter campus events by category, department, date range, or keywords; inspect remaining seat capacity.
- **Event Registration**: Instant seat booking with capacity validation, deadline enforcement, duplicate prevention, and department eligibility checks.
- **My Registrations & My Attendance**: View enrollment records, verify official attendance status, and cancel registrations before deadlines.
- **Post-Event Feedback**: Submit star ratings across 4 dimensions and written comments for completed events attended.
- **Notification Feed**: In-app notifications with unread badge indicators.

---

## 2. Technology Stack

- **Backend**: Python 3.10+, Flask Framework, Flask-SQLAlchemy ORM, Flask-Login, Flask-WTF CSRF Protection, Werkzeug Password Hashing (PBKDF2).
- **Database**: SQLite (default local) / MySQL support via `DATABASE_URL`.
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Chart.js 4.4, FullCalendar 6.1.
- **Testing**: Pytest 8.4+, Flask Testing Client.
- **Environment**: Visual Studio Code, Git, Python Virtual Environment (`.venv`).

---

## 3. The Nine Academic Departments

The system stores all 9 departments in the database and assigns every student and event to them:

1. **Civil Engineering** (`CIVIL`)
2. **Mechanical Engineering** (`MECH`)
3. **Information Technology (IT)** (`IT`)
4. **Software Engineering (SE)** (`SE`)
5. **Artificial Intelligence and Machine Learning (AI/ML)** (`AIML`)
6. **Cybersecurity** (`CYS`)
7. **Master of Computer Applications (MCA)** (`MCA`)
8. **Aeronautical Engineering** (`AERO`)
9. **Aerospace Engineering** (`AEROSP`)

---

## 4. Key Formulas & Algorithms

### Attendance Rate Formula
$$\text{Attendance Rate} = \left(\frac{\text{Present Students}}{\text{Eligible Active Registered Students}}\right) \times 100$$
- Cancelled registrations are strictly excluded from both numerator and denominator.
- Excused participants remain in the eligible denominator, but are not counted as present.

### Transparent Event Popularity Scoring System
$$\text{Popularity Score} = (40\% \times \text{Fill Rate}) + (40\% \times \text{Attendance Rate}) + (20\% \times \text{Normalized Feedback})$$
- **Registration Fill Rate**: $\min\left(\frac{\text{Valid Registrations}}{\text{Capacity}} \times 100, 100\right)$ (safe default 0 if capacity undefined).
- **Attendance Rate**: $\left(\frac{\text{Present}}{\text{Active Registrations}}\right) \times 100$ (safe default 0 if no registrations).
- **Normalized Feedback Score**: $\left(\frac{\text{Average Feedback Rating}}{5.0}\right) \times 100$ (safe default 0 if no reviews yet).

---

## 5. Beginner-Friendly Windows PowerShell Execution Guide

Follow these exact step-by-step commands in **Windows PowerShell** or the **VS Code Integrated Terminal**:

### Step 1: Open Terminal and Set Execution Policy (if needed)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Step 2: Create and Activate Python Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Required Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
```powershell
Copy-Item .env.example .env
$secret = python -c "import secrets; print(secrets.token_hex(32))"
Set-Content .env "SECRET_KEY=$secret`nDATABASE_URL=sqlite:///college_event_analytics.db`nSESSION_COOKIE_SECURE=false"
```

### Step 5: Initialize and Seed Database
```powershell
python seed.py
```

### Step 6: Start the Flask Web Application
```powershell
python run.py
```

### Step 7: Open in Web Browser
Visit: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 6. Demo Accounts & Credentials

The seed script (`seed.py`) automatically populates the system with 9 departments, 11 sample events, 12 fictional students across departments, active registrations, attendance records, and evaluations.

| Portal | Role | Username / Email | Password | Purpose |
|---|---|---|---|---|
| **Admin Portal** | Chief Administrator | `admin@college.edu` | `CampusDemo123!` | Full system control, user roles, 9 depts, audits |
| **Admin Portal** | Administrator (Legacy) | `admin@example.com` | `CampusDemo123!` | Secondary admin account |
| **Admin Portal** | Faculty Coordinator | `coordinator@college.edu` | `CampusDemo123!` | AI/ML & IT event management and attendance |
| **Admin Portal** | Faculty Coordinator 2 | `coordinator2@college.edu` | `CampusDemo123!` | SE & Cybersecurity event management |
| **Student Portal**| Student (AIML) | `student@example.com` / `1MS21AI001` | `CampusDemo123!` | Student registration, attendance, feedback |
| **Student Portal**| Student (SE) | `student2@example.com` / `1MS21SE014` | `CampusDemo123!` | Event enrollment and feedback |
| **Student Portal**| Student (CYS) | `student3@example.com` / `1MS21CY022` | `CampusDemo123!` | Hackathons and workshop enrollments |
| **Student Portal**| Students 4–12 | `student4@college.edu` to `student12@college.edu` | `CampusDemo123!` | Civil, Mech, Aero, Aerospace & MCA students |

---

## 7. Automated Test Suite Execution

Run the complete Pytest test suite to verify all business rules, role access checks, scheduling conflict algorithms, and analytics calculations:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

### Test Results
- **Total Tests Collected**: 28 items
- **Passed**: 28 passed in 12.94s
- **Failed**: 0
- **Coverage**: Full details recorded in [TESTING_REPORT.md](./TESTING_REPORT.md).

---

## 8. Project Structure

```
College Event Analytics/
├── app/
│   ├── __init__.py                # App factory, blueprints, global context processors
│   ├── extensions.py              # db, csrf, login_manager instances
│   ├── models.py                  # 9 relational SQLAlchemy models & relationships
│   ├── security.py                # RBAC decorators (@roles_required, can_manage_event)
│   ├── admin/                     # Admin Portal routes & views
│   ├── analytics/                 # Chart.js analytics engine & popularity services
│   ├── attendance/                # Attendance tracking, bulk marking & CSV sheets
│   ├── auth/                      # Dedicated Admin Login, Student Login & Registration
│   ├── events/                    # Event scheduling, conflict detection, FullCalendar
│   ├── feedback/                  # Student feedback submission & keyword themes
│   ├── notifications/             # In-app notification center & audit logger
│   ├── reports/                   # 6-dimension downloadable CSV export suite
│   ├── students/                  # Student Portal dashboard, registrations, attendance
│   ├── static/                    # SaaS CSS styles, dashboard.js, assets
│   └── templates/                 # Jinja2 templates (base, landing, admin, student, etc.)
├── instance/
│   └── college_event_analytics.db # SQLite database
├── tests/
│   ├── conftest.py                # Pytest fixtures and isolated test app
│   ├── test_analytics_reports.py  # KPI cards, charts JSON, CSV downloads
│   ├── test_auth_events.py        # Authentication, profiles, deadlines, capacity
│   ├── test_new_sprint_features.py# 9 depts, venue conflict, bulk attendance, notifications
│   └── test_security_and_validation.py # RBAC 403 checks, invalid inputs, edge cases
├── .env.example                   # Environment configuration template
├── AGILE_PLAN.md                  # 8-sprint Agile plan, user stories, checklist
├── DATABASE_DESIGN.md             # Complete 9-table schema & integrity semantics
├── TESTING_REPORT.md              # Automated test execution record
├── requirements.txt               # Declared package dependencies
├── run.py                         # Application entrypoint
├── seed.py                        # Automated database seed script
└── README.md                      # Comprehensive user & execution manual
```

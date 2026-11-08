# Agile Plan and Implementation Blueprint

## 1. Project Overview & Methodology
The **College Event Analytics System** is developed following an iterative Agile methodology comprising 8 distinct sprints. Each sprint delivers functional, thoroughly tested increments across database models, backend business logic, responsive UI templates, and automated Pytest validations.

---

## 2. Sprint Breakdown & Acceptance Criteria

### Sprint 1: Requirement Analysis, Architecture & Authentication
- **User Story 1.1 (Admin Auth)**: As an administrator, I want a dedicated Admin Login page so that administrative access is kept strictly isolated from student registration.
  - *Acceptance Criteria*: Accessible at `/auth/admin-login`; requires email and password; validates role in (`admin`, `coordinator`); prevents student accounts from logging in through admin portal; hashes passwords with PBKDF2; provides logout.
- **User Story 1.2 (Student Registration & Auth)**: As a college student, I want to register an account with my USN, department, and phone number, and log in using either email or USN.
  - *Acceptance Criteria*: Accessible at `/auth/register` and `/auth/login`; accepts USN or email; validates 8+ character password, email regex, unique email/USN; assigns student role.
- **User Story 1.3 (Landing Page)**: As a visitor, I want a branded landing page highlighting upcoming events with direct entrances for students and administrators.
  - *Acceptance Criteria*: SaaS-style layout with stats, featured events, and separate portal login buttons.

### Sprint 2: Department Management & Student Profiles
- **User Story 2.1 (Nine Academic Departments)**: As an administrator, I want all nine engineering/technology departments stored in the database and manageable via UI.
  - *Acceptance Criteria*: Civil, Mechanical, IT, SE, AI/ML, Cybersecurity, MCA, Aeronautical, Aerospace seeded; department list shows student count and associated events; admin can add/edit departments.
- **User Story 2.2 (Student Profiles & Account Status)**: As an admin, I want to browse students, filter by department, view registration history, and activate/deactivate accounts.
  - *Acceptance Criteria*: Student list with search/filter; view individual profile with full registration records.

### Sprint 3: Event Scheduling, Conflict Prevention, Multi-Department & Calendar
- **User Story 3.1 (Event Scheduling)**: As an administrator or coordinator, I want to schedule events specifying category, type (Online/Offline/Hybrid), venue, date/times, registration dates, capacity, coordinator, and department assignments.
  - *Acceptance Criteria*: Validates end_time > start_time; registration_deadline <= event_date; supports single/multiple departments or college-wide.
- **User Story 3.2 (Venue Conflict Prevention)**: As an administrator, the system must prevent scheduling two events at the same venue and overlapping date/times.
  - *Acceptance Criteria*: Database query flags any conflicting event at the same venue on the same date with intersecting time intervals.
- **User Story 3.3 (Event Calendar View)**: As an administrator or student, I want to view scheduled events on an interactive calendar.
  - *Acceptance Criteria*: FullCalendar integration displaying events with month, week, and day views; clicking an event shows details.
- **User Story 3.4 (Student Event Discovery & Registration)**: As a student, I want to browse upcoming events, filter by department/category, and register with capacity and deadline checks.
  - *Acceptance Criteria*: Checks deadline, seat capacity, student eligibility (department match or college-wide), and prevents duplicates.

### Sprint 4: Registered Student Management & Attendance Tracking
- **User Story 4.1 (Registered Students Management)**: As an administrator, I want a dedicated page listing all registered students across events with filters and CSV export.
  - *Acceptance Criteria*: Shows Registration ID, Name, USN, Email, Phone, Department, Year, Event, Status, Attendance; supports search and CSV export.
- **User Story 4.2 (Attendance Management)**: As an event coordinator, I want to mark attendance as Present, Absent, or Excused, support bulk marking, and view the attendance rate.
  - *Acceptance Criteria*: Mark individual or bulk; records `marked_by_id` and timestamp; computes formula: $(Present / Eligible) \times 100$.

### Sprint 5: Student Feedback & Feedback Management
- **User Story 5.1 (Student Feedback Submission)**: As an attending student, I want to rate a completed event across four dimensions and submit written comments.
  - *Acceptance Criteria*: 4 star ratings (1–5) + comments; accessible only for completed events where student was marked Present; one submission per student.
- **User Story 5.2 (Admin Feedback Analysis)**: As an administrator, I want to review feedback ratings, view distributions, and see keyword themes.
  - *Acceptance Criteria*: Computes averages for satisfaction, organization, content, venue; extracts positive/improvement keywords.

### Sprint 6: Advanced Analytics Dashboard & Popularity Scoring
- **User Story 6.1 (Interactive Chart.js Analytics)**: As an administrator, I want 8 interactive charts with dynamic filters (date range, department, category, status, academic year).
  - *Acceptance Criteria*: Charts 1-8 powered by live database queries via JSON endpoint.
- **User Story 6.2 (Transparent Popularity Scoring)**: As an administrator, I want events ranked by the standard popularity formula with transparent calculation metrics.
  - *Acceptance Criteria*: $40\% \text{ Fill} + 40\% \text{ Attendance} + 20\% \text{ Feedback}$; displays components and handles missing data gracefully.

### Sprint 7: Reports, CSV Exports & In-App Notifications
- **User Story 7.1 (CSV Export Suite)**: As an administrator, I want downloadable CSV reports for registrations, attendance, feedback, departments, popularity, and monthly trends.
  - *Acceptance Criteria*: Authenticated, role-scoped CSV exports formatted for reporting.
- **User Story 7.2 (In-App Notification Center)**: As a user, I want in-app notifications with unread badges for event updates, registrations, and reminders.
  - *Acceptance Criteria*: Model and UI badge; mark as read; triggers on registration, status change, and feedback.
- **User Story 7.3 (Audit Logging)**: As an administrator, I want an audit trail of critical actions.
  - *Acceptance Criteria*: Logs action, user, timestamp, details, IP address.

### Sprint 8: Integration Testing, Verification & Final Documentation
- **User Story 8.1 (Automated Test Suite)**: Pytest suite verifying authentication, scheduling, conflicts, registration, attendance, feedback, analytics, and security.
  - *Acceptance Criteria*: All tests pass without warnings or regressions.
- **User Story 8.2 (Execution & Seeding)**: Complete seed script and Windows PowerShell instructions for single-command setup.

---

## 3. Product Backlog Status & Implementation Checklist

- [x] Sprint 1: Architecture, database schema, landing page, separate admin/student auth.
- [x] Sprint 2: 9 departments, student profiles, account management.
- [x] Sprint 3: Event scheduling, conflict detection, multi-department, calendar view.
- [x] Sprint 4: Registered students list, attendance module, bulk marking, CSV export.
- [x] Sprint 5: Student feedback submission, ratings distribution, keyword themes.
- [x] Sprint 6: Chart.js analytics (8 charts), dynamic filters, popularity scoring.
- [x] Sprint 7: In-app notifications, CSV reports suite, audit logging.
- [x] Sprint 8: Comprehensive test suite, documentation, and demo verification.

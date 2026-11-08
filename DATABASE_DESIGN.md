# Database Architecture and Relational Design

The **College Event Analytics System** uses SQLAlchemy ORM backed by SQLite (or MySQL via `DATABASE_URL`).
The schema consists of nine core tables designed with strict integrity constraints, foreign keys, unique indices, and timestamped audit tracking.

---

## 1. Entity Overview and Schema Definition

### 1. `departments`
Stores academic departments. Pre-seeded with 9 required departments.
- `id` (Integer, Primary Key, Autoincrement)
- `name` (String(120), Unique, Not Null) — Full department name
- `code` (String(20), Unique, Not Null) — Short department code (e.g. `AIML`, `CIVIL`, `MCA`)
- `created_at` (DateTime, Not Null, Default: UTC Now)

### 2. `users`
Unified user entity supporting role-based separation: `admin`, `coordinator`, and `student`.
- `id` (Integer, Primary Key, Autoincrement)
- `name` (String(120), Not Null) — Full user name
- `email` (String(255), Unique, Not Null, Indexed) — User email address
- `student_id` (String(40), Unique, Nullable) — Student USN / ID (mandatory for students)
- `phone_number` (String(20), Nullable) — Contact phone number
- `academic_year` (String(30), Nullable) — Academic year (e.g., Year 1, Year 2, Year 3, Year 4, MCA Year 1)
- `password_hash` (String(255), Not Null) — Werkzeug PBKDF2 secure password hash
- `role` (String(20), Not Null, Default: 'student', Indexed) — Role: `admin`, `coordinator`, or `student`
- `department_id` (Integer, ForeignKey('department.id'), Nullable) — Assigned academic department
- `is_active` (Boolean, Not Null, Default: True) — Account status toggle
- `created_at` (DateTime, Not Null, Default: UTC Now)

### 3. `events`
College events scheduled and managed by administrators and coordinators.
- `id` (Integer, Primary Key, Autoincrement)
- `title` (String(180), Not Null, Indexed) — Event title
- `description` (Text, Not Null, Default: '') — Detailed event description
- `category` (String(80), Not Null, Indexed) — Event Category (Technical, Cultural, Sports, Workshop, Seminar, Conference, Hackathon, Competition, Awareness, Other)
- `event_type` (String(20), Not Null, Default: 'Offline') — Type: `Online`, `Offline`, or `Hybrid`
- `venue` (String(180), Not Null) — Physical venue or online meeting link
- `event_date` (Date, Not Null, Indexed) — Scheduled date of the event
- `start_time` (Time, Not Null) — Event start time
- `end_time` (Time, Not Null) — Event end time
- `registration_start_date` (Date, Nullable) — Date when registrations open
- `registration_deadline` (Date, Not Null) — Registration cut-off date
- `capacity` (Integer, Nullable) — Maximum allowed participants
- `status` (String(20), Not Null, Default: 'Upcoming', Indexed) — Status: `Draft`, `Upcoming`, `Ongoing`, `Completed`, `Cancelled`
- `is_college_wide` (Boolean, Not Null, Default: False) — Flag indicating eligibility for all departments
- `department_id` (Integer, ForeignKey('department.id'), Nullable) — Primary organizing department
- `coordinator_id` (Integer, ForeignKey('user.id'), Not Null) — Assigned event coordinator
- `image_url` (String(255), Nullable, Default: '') — Event poster/image URL or preset
- `created_at` (DateTime, Not Null, Default: UTC Now)

### 4. `event_departments`
Association table enabling many-to-many relationships between events and eligible departments.
- `event_id` (Integer, ForeignKey('event.id'), Primary Key)
- `department_id` (Integer, ForeignKey('department.id'), Primary Key)

### 5. `registrations`
Student registrations for college events.
- `id` (Integer, Primary Key, Autoincrement)
- `event_id` (Integer, ForeignKey('event.id'), Not Null, Indexed)
- `student_id` (Integer, ForeignKey('user.id'), Not Null, Indexed)
- `registered_at` (DateTime, Not Null, Default: UTC Now)
- `status` (String(20), Not Null, Default: 'Active', Indexed) — Status: `Active`, `Cancelled`
- `cancelled_at` (DateTime, Nullable)
- *Constraint*: `UniqueConstraint('event_id', 'student_id', name='uq_registration_event_student')`

### 6. `attendance`
Attendance tracking records for registered students.
- `id` (Integer, Primary Key, Autoincrement)
- `registration_id` (Integer, ForeignKey('registration.id'), Unique, Not Null)
- `status` (String(20), Not Null, Default: 'Absent') — Status: `Present`, `Absent`, `Excused`
- `marked_by_id` (Integer, ForeignKey('user.id'), Nullable) — Admin/Coordinator who marked attendance
- `notes` (String(255), Nullable) — Optional remarks/excuse notes
- `updated_at` (DateTime, Not Null, Default: UTC Now, onupdate: UTC Now)

### 7. `feedback`
Post-event student evaluations.
- `id` (Integer, Primary Key, Autoincrement)
- `registration_id` (Integer, ForeignKey('registration.id'), Unique, Not Null)
- `satisfaction` (Integer, Not Null) — Overall Satisfaction rating (1–5)
- `organization` (Integer, Not Null) — Event Organization rating (1–5)
- `content_quality` (Integer, Not Null) — Content Quality rating (1–5)
- `venue_rating` (Integer, Not Null) — Venue and Facilities rating (1–5)
- `comments` (Text, Nullable) — Written student comments (up to 2000 chars)
- `submitted_at` (DateTime, Not Null, Default: UTC Now)
- *Constraint*: `UniqueConstraint('registration_id', name='uq_feedback_registration')`

### 8. `notifications`
In-app notification system for students, coordinators, and administrators.
- `id` (Integer, Primary Key, Autoincrement)
- `user_id` (Integer, ForeignKey('user.id'), Nullable, Indexed) — Nullable for broadcast/role notifications
- `target_role` (String(20), Nullable) — Role target (`admin`, `student`, or null for specific user)
- `title` (String(150), Not Null) — Short notification title
- `message` (Text, Not Null) — Notification body
- `category` (String(50), Default: 'general') — Category: `event`, `registration`, `attendance`, `feedback`
- `link` (String(255), Nullable) — Target URL or action link
- `is_read` (Boolean, Not Null, Default: False) — Read status
- `created_at` (DateTime, Not Null, Default: UTC Now)

### 9. `audit_logs`
Audit log recording critical administrative events and security actions.
- `id` (Integer, Primary Key, Autoincrement)
- `user_id` (Integer, ForeignKey('user.id'), Nullable) — User executing the action
- `action` (String(80), Not Null) — Action identifier (e.g. `EVENT_CREATED`, `ATTENDANCE_MARKED`, `REGISTRATION_CANCELLED`)
- `details` (Text, Nullable) — Structured description or contextual JSON
- `ip_address` (String(50), Nullable) — Client IP address
- `created_at` (DateTime, Not Null, Default: UTC Now)

---

## 2. Integrity and Reporting Semantics

1. **Conflict Detection**: Event scheduling validates that no other event is scheduled at the same venue on the same date with overlapping start and end times.
2. **Eligibility & Capacity**: Registration verifies that current date is between `registration_start_date` and `registration_deadline`, that student's department matches an assigned department (or the event is `is_college_wide`), and that active registrations do not exceed `capacity`.
3. **Attendance Rate Formula**:
   $$\text{Attendance Rate} = \left(\frac{\text{Present Students}}{\text{Eligible Registered Students}}\right) \times 100$$
   - Cancelled registrations are strictly excluded from both numerator and denominator.
   - `Excused` participants remain in the eligible denominator as registered, but are not counted as `Present`.
4. **Event Popularity Scoring Formula**:
   $$\text{Popularity Score} = 40\% \times \text{Fill Rate} + 40\% \times \text{Attendance Rate} + 20\% \times \text{Normalized Feedback}$$
   - **Fill Rate**: $\min\left(\frac{\text{Valid Registrations}}{\text{Capacity}} \times 100, 100\right)$ (default 0 if capacity undefined).
   - **Attendance Rate**: $\frac{\text{Present}}{\text{Active Registrations}} \times 100$ (default 0 if no registrations).
   - **Normalized Feedback**: $\frac{\text{Average Feedback Rating} - 1}{4} \times 100$ (default 0 if no feedback).

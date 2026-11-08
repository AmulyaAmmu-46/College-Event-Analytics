from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

# Association table for multi-department event assignments
event_departments = db.Table(
    "event_departments",
    db.Column("event_id", db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), primary_key=True),
    db.Column("department_id", db.Integer, db.ForeignKey("department.id", ondelete="CASCADE"), primary_key=True),
)


class Department(db.Model):
    __tablename__ = "department"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    users = db.relationship("User", back_populates="department")
    events = db.relationship("Event", back_populates="department", foreign_keys="Event.department_id")
    assigned_events = db.relationship(
        "Event",
        secondary=event_departments,
        back_populates="target_departments",
    )

    def __repr__(self):
        return f"<Department {self.code} - {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    student_id = db.Column(db.String(40), unique=True, nullable=True)  # USN / Student ID
    phone_number = db.Column(db.String(20), nullable=True)
    academic_year = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)  # admin, coordinator, student
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    department = db.relationship("Department", back_populates="users")
    coordinated_events = db.relationship("Event", back_populates="coordinator", foreign_keys="Event.coordinator_id")
    registrations = db.relationship("Registration", back_populates="student", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Event(db.Model):
    __tablename__ = "event"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(80), nullable=False, index=True)
    event_type = db.Column(db.String(20), nullable=False, default="Offline")  # Online, Offline, Hybrid
    venue = db.Column(db.String(180), nullable=False)
    event_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    registration_start_date = db.Column(db.Date, nullable=True)
    registration_deadline = db.Column(db.Date, nullable=False)
    capacity = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Upcoming", index=True)  # Draft, Upcoming, Ongoing, Completed, Cancelled
    is_college_wide = db.Column(db.Boolean, nullable=False, default=False)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)  # Organizing department
    coordinator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=True, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    department = db.relationship("Department", back_populates="events", foreign_keys=[department_id])
    target_departments = db.relationship(
        "Department",
        secondary=event_departments,
        back_populates="assigned_events",
    )
    coordinator = db.relationship("User", back_populates="coordinated_events", foreign_keys=[coordinator_id])
    registrations = db.relationship(
        "Registration", back_populates="event", cascade="all, delete-orphan"
    )

    @property
    def departments_display(self):
        if self.is_college_wide:
            return "College-Wide (All Departments)"
        if self.target_departments:
            return ", ".join(dept.code for dept in self.target_departments)
        if self.department:
            return self.department.code
        return "General"

    @property
    def active_registrations_count(self):
        return sum(1 for r in self.registrations if r.status == "Active")

    @property
    def remaining_seats(self):
        if self.capacity is None:
            return None
        return max(0, self.capacity - self.active_registrations_count)

    def is_eligible_student(self, user):
        if not user or user.role != "student":
            return False
        if self.is_college_wide:
            return True
        if not user.department_id:
            return False
        if self.department_id and user.department_id == self.department_id:
            return True
        if any(dept.id == user.department_id for dept in self.target_departments):
            return True
        return False

    def __repr__(self):
        return f"<Event {self.id}: {self.title}>"


class Registration(db.Model):
    __tablename__ = "registration"
    __table_args__ = (
        db.UniqueConstraint("event_id", "student_id", name="uq_registration_event_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    registered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="Active", index=True)  # Active, Cancelled
    cancelled_at = db.Column(db.DateTime, nullable=True)

    event = db.relationship("Event", back_populates="registrations")
    student = db.relationship("User", back_populates="registrations")
    attendance = db.relationship(
        "Attendance", back_populates="registration", uselist=False, cascade="all, delete-orphan"
    )
    feedback = db.relationship(
        "Feedback", back_populates="registration", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Registration {self.id} User:{self.student_id} Event:{self.event_id} ({self.status})>"


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(
        db.Integer, db.ForeignKey("registration.id"), unique=True, nullable=False
    )
    status = db.Column(db.String(20), nullable=False, default="Absent")  # Present, Absent, Excused
    marked_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    registration = db.relationship("Registration", back_populates="attendance")
    marked_by = db.relationship("User", foreign_keys=[marked_by_id])

    def __repr__(self):
        return f"<Attendance {self.id} Reg:{self.registration_id} Status:{self.status}>"


class Feedback(db.Model):
    __tablename__ = "feedback"
    __table_args__ = (
        db.UniqueConstraint("registration_id", name="uq_feedback_registration"),
    )

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"), nullable=False)
    satisfaction = db.Column(db.Integer, nullable=False)       # Overall satisfaction (1-5)
    organization = db.Column(db.Integer, nullable=False)       # Event organization (1-5)
    content_quality = db.Column(db.Integer, nullable=False)    # Content quality (1-5)
    venue_rating = db.Column(db.Integer, nullable=False)       # Venue & facilities (1-5)
    comments = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    registration = db.relationship("Registration", back_populates="feedback")

    @property
    def average_rating(self):
        return round((self.satisfaction + self.organization + self.content_quality + self.venue_rating) / 4.0, 1)

    def __repr__(self):
        return f"<Feedback {self.id} Reg:{self.registration_id} Overall:{self.satisfaction}>"


class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    target_role = db.Column(db.String(20), nullable=True)  # admin, coordinator, student, or None
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default="general")  # event, registration, attendance, feedback, alert
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification {self.id}: {self.title}>"


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)  # e.g., EVENT_CREATED, ATTENDANCE_MARKED
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} by User {self.user_id}>"

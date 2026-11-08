from datetime import date

from flask import Blueprint, render_template
from flask_login import current_user

from app.models import Attendance, Event, Feedback, Registration
from app.security import roles_required

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/dashboard")
@roles_required("student")
def dashboard():
    """Student Dashboard with summary metrics, registered events, upcoming events, and pending feedback."""
    registrations = (
        Registration.query.filter_by(student_id=current_user.id)
        .order_by(Registration.registered_at.desc())
        .all()
    )

    total_registered = len([r for r in registrations if r.status == "Active"])
    upcoming_registered = [
        r for r in registrations if r.status == "Active" and r.event.status == "Upcoming"
    ]
    completed_registered = [
        r for r in registrations if r.status == "Active" and r.event.status == "Completed"
    ]
    attended_count = sum(
        1 for r in registrations if r.status == "Active" and r.attendance and r.attendance.status == "Present"
    )

    # Pending feedback: active registrations for completed events where student was present and has no feedback yet
    pending_feedback = [
        r for r in completed_registered
        if r.attendance and r.attendance.status == "Present" and r.feedback is None
    ]

    # Upcoming campus events the student might want to join
    upcoming_events = (
        Event.query.filter(Event.status == "Upcoming", Event.event_date >= date.today())
        .order_by(Event.event_date.asc())
        .limit(4)
        .all()
    )

    return render_template(
        "students/dashboard.html",
        registrations=registrations,
        upcoming_registered=upcoming_registered,
        completed_registered=completed_registered,
        attended_count=attended_count,
        pending_feedback=pending_feedback,
        upcoming_events=upcoming_events,
        today=date.today(),
        stats={
            "total_registered": total_registered,
            "upcoming_count": len(upcoming_registered),
            "completed_count": len(completed_registered),
            "attended_count": attended_count,
            "pending_feedback_count": len(pending_feedback),
        },
    )


@students_bp.route("/my-registrations")
@roles_required("student")
def my_registrations():
    """Detailed My Registrations page."""
    registrations = (
        Registration.query.filter_by(student_id=current_user.id)
        .order_by(Registration.registered_at.desc())
        .all()
    )
    return render_template("students/my_registrations.html", registrations=registrations, today=date.today())


@students_bp.route("/my-attendance")
@roles_required("student")
def my_attendance():
    """Attendance history for student."""
    registrations = (
        Registration.query.join(Event)
        .filter(Registration.student_id == current_user.id, Registration.status == "Active")
        .order_by(Event.event_date.desc())
        .all()
    )
    total_events = len(registrations)
    present_events = sum(1 for r in registrations if r.attendance and r.attendance.status == "Present")
    absent_events = sum(1 for r in registrations if r.attendance and r.attendance.status == "Absent")
    excused_events = sum(1 for r in registrations if r.attendance and r.attendance.status == "Excused")
    rate = round(present_events / total_events * 100, 1) if total_events > 0 else 0.0

    return render_template(
        "students/my_attendance.html",
        registrations=registrations,
        total_events=total_events,
        present_events=present_events,
        absent_events=absent_events,
        excused_events=excused_events,
        attendance_rate=rate,
    )

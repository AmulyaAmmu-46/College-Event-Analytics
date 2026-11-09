import csv
from datetime import date, datetime
from io import StringIO

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from app.analytics.services import active_registrations, event_metrics
from app.extensions import db
from app.export_utils import excel_response
from app.models import Attendance, AuditLog, Department, Event, Feedback, Registration, User
from app.notifications.services import create_notification, log_action
from app.security import roles_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@roles_required("admin", "coordinator")
def dashboard():
    """Modern Admin Analytics Dashboard with 8 live KPI summary cards, recent activity, and quick actions."""
    events_query = Event.query
    if current_user.role == "coordinator":
        events_query = events_query.filter_by(coordinator_id=current_user.id)
    events = events_query.all()
    event_ids = [e.id for e in events]

    total_events = len(events)
    upcoming_events = sum(1 for e in events if e.status == "Upcoming")
    completed_events = sum(1 for e in events if e.status == "Completed")

    # Registrations and attendance
    active_regs = Registration.query.filter(
        Registration.event_id.in_(event_ids) if event_ids else False,
        Registration.status == "Active"
    ).all()
    total_registered = len(active_regs)

    present_count = 0
    absent_count = 0
    excused_count = 0
    for reg in active_regs:
        if reg.attendance:
            if reg.attendance.status == "Present":
                present_count += 1
            elif reg.attendance.status == "Absent":
                absent_count += 1
            elif reg.attendance.status == "Excused":
                excused_count += 1

    # Formula: Attendance Rate = (Present / Eligible Registered) * 100
    avg_attendance_rate = round((present_count / total_registered * 100), 1) if total_registered > 0 else 0.0

    # Feedback ratings
    feedback_entries = Feedback.query.join(Registration).filter(
        Registration.event_id.in_(event_ids) if event_ids else False
    ).all()
    if feedback_entries:
        avg_feedback_rating = round(sum(f.satisfaction for f in feedback_entries) / len(feedback_entries), 2)
    else:
        avg_feedback_rating = 0.0

    # Recent items
    recent_events = (
        events_query.order_by(Event.event_date.desc(), Event.id.desc()).limit(6).all()
    )
    latest_registrations = (
        Registration.query.join(Event)
        .filter(Registration.event_id.in_(event_ids) if event_ids else False)
        .order_by(Registration.registered_at.desc())
        .limit(6)
        .all()
    )
    recent_feedback = (
        Feedback.query.join(Registration).join(Event)
        .filter(Registration.event_id.in_(event_ids) if event_ids else False)
        .order_by(Feedback.submitted_at.desc())
        .limit(5)
        .all()
    )

    # Department summary
    departments = Department.query.order_by(Department.name).all()
    dept_participation = {}
    for d in departments:
        count = Registration.query.join(User).filter(
            User.department_id == d.id,
            Registration.status == "Active",
            Registration.event_id.in_(event_ids) if event_ids else False,
        ).count()
        dept_participation[d.code] = count

    return render_template(
        "admin/dashboard.html",
        kpi={
            "total_events": total_events,
            "upcoming_events": upcoming_events,
            "completed_events": completed_events,
            "total_registered": total_registered,
            "total_present": present_count,
            "total_absent": absent_count,
            "avg_attendance_rate": avg_attendance_rate,
            "avg_feedback_rating": avg_feedback_rating,
        },
        recent_events=recent_events,
        latest_registrations=latest_registrations,
        recent_feedback=recent_feedback,
        dept_participation=dept_participation,
        departments=departments,
    )


@admin_bp.route("/registrations")
@roles_required("admin", "coordinator")
def registrations():
    """Dedicated Registered Students Management Page."""
    query = Registration.query.join(Event).join(User)

    if current_user.role == "coordinator":
        query = query.filter(Event.coordinator_id == current_user.id)

    # Filters
    event_id = request.args.get("event_id", type=int)
    if event_id:
        query = query.filter(Registration.event_id == event_id)

    department_id = request.args.get("department_id", type=int)
    if department_id:
        query = query.filter(User.department_id == department_id)

    academic_year = request.args.get("academic_year", "").strip()
    if academic_year:
        query = query.filter(User.academic_year == academic_year)

    status = request.args.get("status", "").strip()
    if status:
        query = query.filter(Registration.status == status)

    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.student_id.ilike(f"%{search}%"),
            )
        )

    records = query.order_by(Registration.registered_at.desc()).all()
    events = Event.query.order_by(Event.title).all()
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        "admin/registrations.html",
        records=records,
        events=events,
        departments=departments,
        selected_event=event_id,
        selected_dept=department_id,
        selected_year=academic_year,
        search_query=search,
    )


@admin_bp.route("/registrations/<int:reg_id>/cancel", methods=["POST"])
@roles_required("admin", "coordinator")
def cancel_student_registration(reg_id):
    """Administrator cancel registration with audit history."""
    reg = db.get_or_404(Registration, reg_id)
    if current_user.role == "coordinator" and reg.event.coordinator_id != current_user.id:
        abort(403)

    reason = request.form.get("reason", "Cancelled by administrator").strip()
    reg.status = "Cancelled"
    reg.cancelled_at = datetime.utcnow()

    log_action(
        "ADMIN_CANCEL_REGISTRATION",
        details=f"Registration #{reg.id} for {reg.student.name} on event '{reg.event.title}' cancelled. Reason: {reason}",
    )
    create_notification(
        title="Event Registration Cancelled",
        message=f"Your registration for '{reg.event.title}' was cancelled by the administrator. Reason: {reason}",
        user_id=reg.student_id,
        category="event",
        link=url_for("students.my_registrations"),
    )
    db.session.commit()
    flash(f"Registration for {reg.student.name} has been cancelled.", "success")
    return redirect(request.referrer or url_for("admin.registrations"))


@admin_bp.route("/registrations/export.csv")
@roles_required("admin", "coordinator")
def export_registrations_csv():
    """Export filtered registered students list to CSV."""
    records = registration_export_query().all()
    rows = registration_export_rows(records)
    output = StringIO()
    csv.writer(output).writerows(rows)

    log_action("EXPORT_REGISTRATIONS_CSV", details=f"Exported {len(records)} records")
    db.session.commit()

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=registered_students_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"},
    )


@admin_bp.route("/registrations/export.xlsx")
@roles_required("admin", "coordinator")
def export_registrations_xlsx():
    records = registration_export_query().all()
    log_action("EXPORT_REGISTRATIONS_XLSX", details=f"Exported {len(records)} records")
    db.session.commit()
    return excel_response(
        registration_export_rows(records),
        f"registered_students_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.xlsx",
        "Registrations",
    )


def registration_export_query():
    query = Registration.query.join(Event).join(User)
    if current_user.role == "coordinator":
        query = query.filter(Event.coordinator_id == current_user.id)

    event_id = request.args.get("event_id", type=int)
    if event_id:
        query = query.filter(Registration.event_id == event_id)
    department_id = request.args.get("department_id", type=int)
    if department_id:
        query = query.filter(User.department_id == department_id)
    return query.order_by(Registration.registered_at.desc())


def registration_export_rows(records):
    rows = [[
        "Registration ID",
        "Student Name",
        "USN / Student ID",
        "Email",
        "Phone Number",
        "Department",
        "Academic Year",
        "Event Title",
        "Event Date",
        "Registration Date",
        "Registration Status",
        "Attendance Status",
    ]]
    for r in records:
        rows.append([
            r.id,
            r.student.name,
            r.student.student_id or "N/A",
            r.student.email,
            r.student.phone_number or "N/A",
            r.student.department.name if r.student.department else "Unassigned",
            r.student.academic_year or "N/A",
            r.event.title,
            r.event.event_date.isoformat(),
            r.registered_at.strftime("%Y-%m-%d %H:%M"),
            r.status,
            r.attendance.status if r.attendance else "Unmarked",
        ])
    return rows


@admin_bp.route("/students")
@roles_required("admin")
def students():
    """Student and account management."""
    query = User.query.filter_by(role="student")
    dept_id = request.args.get("department_id", type=int)
    if dept_id:
        query = query.filter_by(department_id=dept_id)
    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.student_id.ilike(f"%{search}%"),
            )
        )
    student_list = query.order_by(User.name).all()
    departments = Department.query.order_by(Department.name).all()

    dept_counts = {}
    for d in departments:
        dept_counts[d.id] = User.query.filter_by(role="student", department_id=d.id).count()

    return render_template(
        "admin/students.html",
        students=student_list,
        departments=departments,
        dept_counts=dept_counts,
        selected_dept=dept_id,
        search_query=search,
    )


@admin_bp.route("/students/<int:student_id>/toggle-status", methods=["POST"])
@roles_required("admin")
def toggle_student_status(student_id):
    student = db.get_or_404(User, student_id)
    student.is_active = not student.is_active
    db.session.commit()
    log_action(
        "TOGGLE_STUDENT_STATUS",
        details=f"Student {student.name} ({student.student_id}) status toggled to {'Active' if student.is_active else 'Inactive'}"
    )
    flash(f"Student account for {student.name} is now {'Active' if student.is_active else 'Inactive'}.", "info")
    return redirect(request.referrer or url_for("admin.students"))


@admin_bp.route("/users", methods=["GET", "POST"])
@roles_required("admin")
def users():
    if request.method == "POST":
        user = db.get_or_404(User, request.form.get("user_id", type=int))
        role = request.form.get("role", "")
        if role not in ("admin", "coordinator", "student"):
            flash("Choose a valid role.", "danger")
        elif user.role == "admin" and role != "admin" and User.query.filter_by(role="admin").count() <= 1:
            flash("At least one administrator account must remain.", "warning")
        else:
            old_role = user.role
            user.role = role
            log_action("USER_ROLE_CHANGED", details=f"Changed user {user.email} from {old_role} to {role}")
            db.session.commit()
            flash(f"Role for {user.name} updated to {role.title()}.", "success")
    return render_template("admin/users.html", users=User.query.order_by(User.name).all())


@admin_bp.route("/departments", methods=["GET", "POST"])
@roles_required("admin")
def departments():
    departments_list = Department.query.order_by(Department.name).all()
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip().upper()
            if not name or not code:
                flash("Department name and code are required.", "danger")
            elif Department.query.filter(
                (Department.name == name) | (Department.code == code)
            ).first():
                flash("Department name or code already exists.", "warning")
            else:
                dept = Department(name=name, code=code)
                db.session.add(dept)
                log_action("DEPARTMENT_CREATED", details=f"Created department {code} - {name}")
                db.session.commit()
                flash("Department added successfully.", "success")
                return redirect(url_for("admin.departments"))
        elif action == "edit":
            dept_id = request.form.get("department_id", type=int)
            dept = db.get_or_404(Department, dept_id)
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip().upper()
            if not name or not code:
                flash("Department name and code are required.", "danger")
            else:
                dept.name = name
                dept.code = code
                log_action("DEPARTMENT_UPDATED", details=f"Updated department #{dept.id} to {code} - {name}")
                db.session.commit()
                flash("Department updated successfully.", "success")
                return redirect(url_for("admin.departments"))

    # Compute department-wise student and event counts
    dept_stats = []
    for d in departments_list:
        student_count = User.query.filter_by(department_id=d.id, role="student").count()
        event_count = len(d.events) + len(d.assigned_events)
        dept_stats.append({
            "dept": d,
            "student_count": student_count,
            "event_count": event_count,
        })

    return render_template("admin/departments.html", dept_stats=dept_stats, departments=departments_list)


@admin_bp.route("/audit-logs")
@roles_required("admin")
def audit_logs():
    """System Audit Logs."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_logs.html", logs=logs)

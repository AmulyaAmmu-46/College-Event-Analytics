import csv
from datetime import datetime
from io import StringIO

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.export_utils import excel_response
from app.models import Attendance, Event, Registration
from app.notifications.services import create_notification, log_action
from app.security import can_manage_event, require_event_access, roles_required

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")
ATTENDANCE_STATUSES = ("Present", "Absent", "Excused")


@attendance_bp.route("/")
@roles_required("admin", "coordinator")
def index():
    """Attendance module landing page listing all events and their attendance progress."""
    events_query = Event.query
    if current_user.role == "coordinator":
        events_query = events_query.filter_by(coordinator_id=current_user.id)
    events = events_query.order_by(Event.event_date.desc()).all()

    events_summary = []
    for ev in events:
        active_regs = [r for r in ev.registrations if r.status == "Active"]
        total = len(active_regs)
        present = sum(1 for r in active_regs if r.attendance and r.attendance.status == "Present")
        absent = sum(1 for r in active_regs if r.attendance and r.attendance.status == "Absent")
        excused = sum(1 for r in active_regs if r.attendance and r.attendance.status == "Excused")
        marked = sum(1 for r in active_regs if r.attendance is not None)
        rate = round(present / total * 100, 1) if total > 0 else 0.0

        events_summary.append({
            "event": ev,
            "total_registered": total,
            "present": present,
            "absent": absent,
            "excused": excused,
            "unmarked": total - marked,
            "attendance_rate": rate,
        })

    return render_template("attendance/index.html", events_summary=events_summary)


@attendance_bp.route("/events/<int:event_id>", methods=["GET", "POST"])
@roles_required("admin", "coordinator")
def manage(event_id):
    event = db.get_or_404(Event, event_id)
    require_event_access(event)
    registrations = Registration.query.filter_by(event_id=event.id, status="Active").all()

    if request.method == "POST":
        bulk_action = request.form.get("bulk_action")
        notes_global = request.form.get("notes", "").strip()

        if bulk_action in ("mark_all_present", "mark_all_absent", "clear"):
            for reg in registrations:
                if bulk_action == "clear":
                    if reg.attendance:
                        db.session.delete(reg.attendance)
                else:
                    target_status = "Present" if bulk_action == "mark_all_present" else "Absent"
                    att = reg.attendance
                    if att is None:
                        att = Attendance(registration=reg)
                        db.session.add(att)
                    att.status = target_status
                    att.marked_by_id = current_user.id
                    att.updated_at = datetime.utcnow()
            log_action("ATTENDANCE_BULK_MARK", details=f"Bulk action '{bulk_action}' on event '{event.title}'")
            flash(f"Bulk attendance action applied: {bulk_action.replace('_', ' ').title()}.", "info")
        else:
            # Individual attendance records
            for reg in registrations:
                status = request.form.get(f"attendance_{reg.id}")
                note = request.form.get(f"notes_{reg.id}", "").strip()
                if status not in ATTENDANCE_STATUSES:
                    continue
                attendance = reg.attendance
                if attendance is None:
                    attendance = Attendance(registration=reg)
                    db.session.add(attendance)
                attendance.status = status
                attendance.marked_by_id = current_user.id
                attendance.updated_at = datetime.utcnow()
                if note:
                    attendance.notes = note

            log_action("ATTENDANCE_UPDATED", details=f"Updated attendance for event '{event.title}'")
            flash("Attendance saved.", "success")

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Attendance could not be saved because a record changed concurrently. Reload and retry.", "danger")

        return redirect(url_for("attendance.manage", event_id=event.id))

    # Calculate live attendance summary
    total_eligible = len(registrations)
    present_count = sum(1 for r in registrations if r.attendance and r.attendance.status == "Present")
    absent_count = sum(1 for r in registrations if r.attendance and r.attendance.status == "Absent")
    excused_count = sum(1 for r in registrations if r.attendance and r.attendance.status == "Excused")
    rate = round(present_count / total_eligible * 100, 1) if total_eligible > 0 else 0.0

    summary = {
        "total": total_eligible,
        "present": present_count,
        "absent": absent_count,
        "excused": excused_count,
        "rate": rate,
    }

    return render_template(
        "attendance/manage.html",
        event=event,
        registrations=registrations,
        statuses=ATTENDANCE_STATUSES,
        summary=summary,
    )


@attendance_bp.route("/events/<int:event_id>/export.csv")
@roles_required("admin", "coordinator")
def export_csv(event_id):
    """Export attendance sheet for an event to CSV."""
    event = db.get_or_404(Event, event_id)
    require_event_access(event)
    registrations = Registration.query.filter_by(event_id=event.id, status="Active").all()

    rows = attendance_export_rows(event, registrations)
    output = StringIO()
    csv.writer(output).writerows(rows)

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_event_{event.id}_{stamp}.csv"},
    )


@attendance_bp.route("/events/<int:event_id>/export.xlsx")
@roles_required("admin", "coordinator")
def export_xlsx(event_id):
    event = db.get_or_404(Event, event_id)
    require_event_access(event)
    registrations = Registration.query.filter_by(event_id=event.id, status="Active").all()
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    return excel_response(
        attendance_export_rows(event, registrations),
        f"attendance_event_{event.id}_{stamp}.xlsx",
        "Attendance",
    )


def attendance_export_rows(event, registrations):
    rows = [[
        "Event Title",
        "Event Date",
        "Student Name",
        "Student USN / ID",
        "Department",
        "Academic Year",
        "Attendance Status",
        "Notes",
        "Marked By",
        "Last Updated At",
    ]]
    for reg in registrations:
        att = reg.attendance
        rows.append([
            event.title,
            event.event_date.isoformat(),
            reg.student.name,
            reg.student.student_id or "N/A",
            reg.student.department.name if reg.student.department else "Unassigned",
            reg.student.academic_year or "N/A",
            att.status if att else "Unmarked",
            att.notes if att and att.notes else "",
            att.marked_by.name if att and att.marked_by else "System",
            att.updated_at.strftime("%Y-%m-%d %H:%M") if att else "",
        ])
    return rows


@attendance_bp.route("/events/<int:event_id>/participants")
@roles_required("admin", "coordinator")
def participants(event_id):
    event = db.get_or_404(Event, event_id)
    require_event_access(event)
    registrations = Registration.query.filter_by(event_id=event.id).all()
    return render_template("attendance/participants.html", event=event, registrations=registrations)

import csv
from datetime import datetime
from io import StringIO

from flask import Blueprint, Response, render_template, request
from flask_login import current_user

from app.analytics.services import event_metrics, filtered_events
from app.events.routes import EVENT_CATEGORIES, EVENT_STATUSES
from app.export_utils import excel_response
from app.models import Department, Event, Feedback, Registration
from app.notifications.services import log_action
from app.security import roles_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def report_events():
    events = filtered_events(request.args)
    if current_user.role == "coordinator":
        events = [event for event in events if event.coordinator_id == current_user.id]
    return events


@reports_bp.route("/")
@roles_required("admin", "coordinator")
def index():
    return render_template(
        "reports/index.html",
        departments=Department.query.order_by(Department.name).all(),
        categories=EVENT_CATEGORIES,
        statuses=EVENT_STATUSES,
    )


def report_rows(report_type, events):
    if report_type == "registrations":
        rows = [[
            "Event",
            "Event Date",
            "Category",
            "Student Name",
            "Student USN / ID",
            "Email",
            "Phone Number",
            "Department",
            "Academic Year",
            "Registration Status",
            "Registered At",
        ]]
        for event in events:
            for registration in event.registrations:
                rows.append([
                    event.title,
                    event.event_date.isoformat(),
                    event.category,
                    registration.student.name,
                    registration.student.student_id or "",
                    registration.student.email,
                    registration.student.phone_number or "",
                    registration.student.department.name if registration.student.department else "",
                    registration.student.academic_year or "",
                    registration.status,
                    registration.registered_at.isoformat(),
                ])
        return rows

    if report_type == "attendance":
        rows = [[
            "Event",
            "Event Date",
            "Student Name",
            "USN / Student ID",
            "Department",
            "Registration Status",
            "Attendance Status",
            "Notes",
            "Updated At",
        ]]
        for event in events:
            for registration in event.registrations:
                attendance = registration.attendance
                rows.append([
                    event.title,
                    event.event_date.isoformat(),
                    registration.student.name,
                    registration.student.student_id or "",
                    registration.student.department.name if registration.student.department else "",
                    registration.status,
                    attendance.status if attendance else "Unmarked",
                    attendance.notes if attendance and attendance.notes else "",
                    attendance.updated_at.isoformat() if attendance else "",
                ])
        return rows

    if report_type == "feedback":
        rows = [[
            "Event",
            "Event Date",
            "Student Department",
            "Overall Satisfaction",
            "Organization",
            "Content Quality",
            "Venue Rating",
            "Comments",
            "Submitted At",
        ]]
        for event in events:
            for registration in event.registrations:
                feedback = registration.feedback
                if feedback:
                    rows.append([
                        event.title,
                        event.event_date.isoformat(),
                        registration.student.department.name if registration.student.department else "Unassigned",
                        feedback.satisfaction,
                        feedback.organization,
                        feedback.content_quality,
                        feedback.venue_rating,
                        feedback.comments or "",
                        feedback.submitted_at.isoformat(),
                    ])
        return rows

    if report_type == "departments":
        rows = [["Department", "Event", "Active Registrations", "Attended"]]
        totals = {}
        for event in events:
            for registration in event.registrations:
                if registration.status == "Active":
                    department = registration.student.department.name if registration.student.department else "Unassigned"
                    key = (department, event.title)
                    totals.setdefault(key, [0, 0])
                    totals[key][0] += 1
                    totals[key][1] += int(bool(registration.attendance and registration.attendance.status == "Present"))
        for (department, title), (registered, attended) in sorted(totals.items()):
            rows.append([department, title, registered, attended])
        return rows

    if report_type == "popularity":
        rows = [[
            "Event",
            "Valid Registrations",
            "Attendees",
            "Registration Fill Rate (%)",
            "Attendance Rate (%)",
            "Average Feedback",
            "Popularity Score",
        ]]
        for event in sorted(events, key=lambda row: event_metrics(row)["popularity_score"], reverse=True):
            metric = event_metrics(event)
            rows.append([
                event.title,
                metric["registrations"],
                metric["attended"],
                metric["registration_fill_rate"] if metric["registration_fill_rate"] is not None else "N/A",
                metric["attendance_rate"],
                metric["average_rating"] if metric["average_rating"] is not None else "N/A",
                metric["popularity_score"],
            ])
        return rows

    if report_type == "monthly":
        rows = [[
            "Month",
            "Event",
            "Registrations",
            "Attendees",
            "Attendance Rate (%)",
            "Average Feedback",
        ]]
        for event in events:
            metric = event_metrics(event)
            rows.append([
                event.event_date.strftime("%Y-%m"),
                event.title,
                metric["registrations"],
                metric["attended"],
                metric["attendance_rate"],
                metric["average_rating"] if metric["average_rating"] is not None else "N/A",
            ])
        return rows

    return None


def get_report_rows(report_type):
    try:
        events = report_events()
    except ValueError as error:
        return None, (str(error), 400)

    rows = report_rows(report_type, events)
    if rows is None:
        return None, ("Unknown report type.", 404)
    return rows, None


@reports_bp.route("/<report_type>.csv")
@roles_required("admin", "coordinator")
def export(report_type):
    rows, error_response = get_report_rows(report_type)
    if error_response:
        return error_response

    output = StringIO()
    csv.writer(output).writerows(rows)

    log_action("EXPORT_REPORT_CSV", details=f"Downloaded CSV report: {report_type}")
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report_type}-{stamp}.csv"},
    )


@reports_bp.route("/<report_type>.xlsx")
@roles_required("admin", "coordinator")
def export_xlsx(report_type):
    rows, error_response = get_report_rows(report_type)
    if error_response:
        return error_response

    log_action("EXPORT_REPORT_XLSX", details=f"Downloaded Excel report: {report_type}")
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return excel_response(rows, f"{report_type}-{stamp}.xlsx", report_type.title())

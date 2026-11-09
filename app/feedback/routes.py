import csv
from datetime import datetime
from io import StringIO

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.analytics.services import feedback_themes
from app.extensions import db
from app.export_utils import excel_response
from app.models import Department, Event, Feedback, Registration
from app.notifications.services import create_notification, log_action
from app.security import can_manage_event, roles_required

feedback_bp = Blueprint("feedback", __name__, url_prefix="/feedback")


@feedback_bp.route("/")
@roles_required("admin", "coordinator")
def index():
    """All Feedback Overview & Management."""
    query = Feedback.query.join(Registration).join(Event)
    if current_user.role == "coordinator":
        query = query.filter(Event.coordinator_id == current_user.id)

    event_id = request.args.get("event_id", type=int)
    if event_id:
        query = query.filter(Registration.event_id == event_id)

    department_id = request.args.get("department_id", type=int)
    if department_id:
        query = query.filter(Event.department_id == department_id)

    entries = query.order_by(Feedback.submitted_at.desc()).all()
    events = Event.query.order_by(Event.title).all()
    departments = Department.query.order_by(Department.name).all()

    ratings = [f.satisfaction for f in entries]
    avg_satisfaction = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    avg_org = round(sum(f.organization for f in entries) / len(entries), 2) if entries else 0.0
    avg_content = round(sum(f.content_quality for f in entries) / len(entries), 2) if entries else 0.0
    avg_venue = round(sum(f.venue_rating for f in entries) / len(entries), 2) if entries else 0.0

    distribution = {star: ratings.count(star) for star in range(1, 6)}
    themes = feedback_themes([f.comments for f in entries if f.comments])

    return render_template(
        "feedback/index.html",
        entries=entries,
        events=events,
        departments=departments,
        selected_event=event_id,
        selected_dept=department_id,
        averages={
            "satisfaction": avg_satisfaction,
            "organization": avg_org,
            "content": avg_content,
            "venue": avg_venue,
            "total_count": len(entries),
        },
        distribution=distribution,
        themes=themes,
    )


@feedback_bp.route("/registration/<int:registration_id>", methods=["GET", "POST"])
@roles_required("student")
def submit(registration_id):
    registration = db.get_or_404(Registration, registration_id)
    if registration.student_id != current_user.id:
        abort(403)
    if (
        registration.status != "Active"
        or registration.event.status != "Completed"
        or not registration.attendance
        or registration.attendance.status != "Present"
    ):
        flash("Feedback is only allowed for completed events you attended as Present.", "warning")
        return redirect(url_for("students.dashboard"))

    if registration.feedback:
        flash("Feedback has already been submitted for this event.", "info")
        return redirect(url_for("students.dashboard"))

    if request.method == "POST":
        try:
            ratings = {
                key: int(request.form.get(key, ""))
                for key in ("satisfaction", "organization", "content_quality", "venue_rating")
            }
        except ValueError:
            ratings = {}
        if len(ratings) != 4 or any(value < 1 or value > 5 for value in ratings.values()):
            flash("Each rating must be a whole number from 1 to 5 stars.", "danger")
        else:
            feedback = Feedback(
                registration=registration,
                comments=request.form.get("comments", "").strip()[:2000],
                **ratings,
            )
            db.session.add(feedback)
            try:
                db.session.flush()
                # Notify admin/coordinator of new feedback
                create_notification(
                    title="New Feedback Received",
                    message=f"New feedback received for '{registration.event.title}' (Rating: {feedback.satisfaction}/5).",
                    target_role="admin",
                    category="feedback",
                    link=url_for("feedback.summary", event_id=registration.event_id),
                )
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Feedback was already submitted for this event.", "warning")
                return redirect(url_for("students.dashboard"))

            flash("Thank you for your feedback.", "success")
            return redirect(url_for("students.dashboard"))

    return render_template("feedback/form.html", registration=registration)


@feedback_bp.route("/events/<int:event_id>")
@roles_required("admin", "coordinator")
def summary(event_id):
    event = db.get_or_404(Event, event_id)
    if not can_manage_event(event):
        abort(403)
    entries = Feedback.query.join(Registration).filter(Registration.event_id == event.id).all()
    ratings = [entry.satisfaction for entry in entries]
    rating_averages = {
        "Overall satisfaction": sum(entry.satisfaction for entry in entries) / len(entries) if entries else None,
        "Event organization": sum(entry.organization for entry in entries) / len(entries) if entries else None,
        "Content quality": sum(entry.content_quality for entry in entries) / len(entries) if entries else None,
        "Venue and facilities": sum(entry.venue_rating for entry in entries) / len(entries) if entries else None,
    }
    return render_template(
        "feedback/summary.html",
        event=event,
        entries=entries,
        average=sum(ratings) / len(ratings) if ratings else None,
        rating_averages=rating_averages,
        distribution={rating: ratings.count(rating) for rating in range(1, 6)},
        themes=feedback_themes([entry.comments for entry in entries if entry.comments]),
    )


@feedback_bp.route("/export.csv")
@roles_required("admin", "coordinator")
def export_csv():
    entries = feedback_export_query().all()
    rows = feedback_export_rows(entries)
    output = StringIO()
    csv.writer(output).writerows(rows)

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=feedback_report_{stamp}.csv"},
    )


@feedback_bp.route("/export.xlsx")
@roles_required("admin", "coordinator")
def export_xlsx():
    entries = feedback_export_query().all()
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    return excel_response(feedback_export_rows(entries), f"feedback_report_{stamp}.xlsx", "Feedback")


def feedback_export_query():
    query = Feedback.query.join(Registration).join(Event)
    if current_user.role == "coordinator":
        query = query.filter(Event.coordinator_id == current_user.id)

    event_id = request.args.get("event_id", type=int)
    if event_id:
        query = query.filter(Registration.event_id == event_id)

    return query.order_by(Feedback.submitted_at.desc())


def feedback_export_rows(entries):
    rows = [[
        "Event Title",
        "Event Date",
        "Student Department",
        "Overall Satisfaction",
        "Event Organization",
        "Content Quality",
        "Venue & Facilities",
        "Written Comments",
        "Submitted Date",
    ]]
    for f in entries:
        rows.append([
            f.registration.event.title,
            f.registration.event.event_date.isoformat(),
            f.registration.student.department.name if f.registration.student.department else "Unassigned",
            f.satisfaction,
            f.organization,
            f.content_quality,
            f.venue_rating,
            f.comments or "",
            f.submitted_at.strftime("%Y-%m-%d %H:%M"),
        ])
    return rows

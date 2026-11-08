from datetime import date, datetime, time

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Department, Event, Registration, User
from app.notifications.services import create_notification, log_action
from app.security import can_manage_event, roles_required

events_bp = Blueprint("events", __name__, url_prefix="/events")

EVENT_CATEGORIES = (
    "Technical Events",
    "Cultural Events",
    "Sports Events",
    "Workshops",
    "Seminars",
    "Conferences",
    "Hackathons",
    "Competitions",
    "Awareness Programs",
    "Other Events",
)
EVENT_TYPES = ("Offline", "Online", "Hybrid")
EVENT_STATUSES = ("Draft", "Upcoming", "Ongoing", "Completed", "Cancelled")


def auto_update_event_statuses():
    """Auto-update event status based on current date (e.g. past events mark as Completed)."""
    today = date.today()
    past_events = Event.query.filter(
        Event.event_date < today,
        Event.status.in_(("Upcoming", "Ongoing")),
    ).all()
    if past_events:
        for ev in past_events:
            ev.status = "Completed"
        db.session.commit()


@events_bp.route("/")
def listing():
    auto_update_event_statuses()
    query = Event.query
    if not current_user.is_authenticated or current_user.role == "student":
        query = query.filter(Event.status != "Draft")

    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(
            or_(
                Event.title.ilike(f"%{search}%"),
                Event.description.ilike(f"%{search}%"),
                Event.venue.ilike(f"%{search}%"),
            )
        )

    category = request.args.get("category", "").strip()
    if category:
        query = query.filter(Event.category == category)

    status = request.args.get("status", "").strip()
    if status:
        query = query.filter(Event.status == status)

    dept_id = request.args.get("department", type=int)
    if dept_id:
        query = query.filter(
            or_(
                Event.department_id == dept_id,
                Event.target_departments.any(Department.id == dept_id),
                Event.is_college_wide == True,
            )
        )

    if request.args.get("date"):
        try:
            query = query.filter(Event.event_date == date.fromisoformat(request.args["date"]))
        except ValueError:
            flash("Date filter must use YYYY-MM-DD.", "warning")

    events = query.order_by(Event.event_date.asc(), Event.start_time.asc()).all()
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        "events/list.html",
        events=events,
        departments=departments,
        statuses=EVENT_STATUSES,
        categories=EVENT_CATEGORIES,
        event_types=EVENT_TYPES,
        today=date.today(),
    )


@events_bp.route("/calendar")
def calendar():
    """Interactive Event Calendar View (Month, Week, Day)."""
    return render_template("events/calendar.html", categories=EVENT_CATEGORIES)


@events_bp.route("/calendar-data")
def calendar_data():
    """JSON event feed for FullCalendar."""
    auto_update_event_statuses()
    query = Event.query
    if not current_user.is_authenticated or current_user.role == "student":
        query = query.filter(Event.status != "Draft")

    events = query.all()
    calendar_events = []
    color_map = {
        "Technical Events": "#4f46e5",
        "Cultural Events": "#ec4899",
        "Sports Events": "#f97316",
        "Workshops": "#06b6d4",
        "Seminars": "#8b5cf6",
        "Conferences": "#3b82f6",
        "Hackathons": "#10b981",
        "Competitions": "#eab308",
        "Awareness Programs": "#14b8a6",
        "Other Events": "#64748b",
    }

    for ev in events:
        start_dt = f"{ev.event_date.isoformat()}T{ev.start_time.strftime('%H:%M:%S')}"
        end_dt = f"{ev.event_date.isoformat()}T{ev.end_time.strftime('%H:%M:%S')}"
        calendar_events.append({
            "id": ev.id,
            "title": ev.title,
            "start": start_dt,
            "end": end_dt,
            "url": url_for("events.detail", event_id=ev.id),
            "backgroundColor": color_map.get(ev.category, "#4f46e5"),
            "borderColor": color_map.get(ev.category, "#4f46e5"),
            "extendedProps": {
                "venue": ev.venue,
                "category": ev.category,
                "status": ev.status,
                "departments": ev.departments_display,
            },
        })
    return jsonify(calendar_events)


@events_bp.route("/<int:event_id>")
def detail(event_id):
    auto_update_event_statuses()
    event = db.get_or_404(Event, event_id)
    is_registered = False
    student_registration = None
    if current_user.is_authenticated and current_user.role == "student":
        student_registration = Registration.query.filter_by(
            event_id=event.id, student_id=current_user.id, status="Active"
        ).first()
        is_registered = student_registration is not None

    return render_template(
        "events/detail.html",
        event=event,
        is_registered=is_registered,
        student_registration=student_registration,
        today=date.today(),
    )


def parse_event_form(existing_event=None):
    try:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        event_type = request.form.get("event_type", "Offline").strip()
        venue = request.form.get("venue", "").strip()
        event_date = date.fromisoformat(request.form["event_date"])
        start_time = time.fromisoformat(request.form["start_time"])
        end_time = time.fromisoformat(request.form["end_time"])
        registration_deadline = date.fromisoformat(request.form["registration_deadline"])
        reg_start_raw = request.form.get("registration_start_date")
        registration_start_date = date.fromisoformat(reg_start_raw) if reg_start_raw else None
        capacity = request.form.get("capacity", type=int)
        department_id = request.form.get("department_id", type=int)
        status = request.form.get("status", "Upcoming")
        is_college_wide = "is_college_wide" in request.form
        image_url = request.form.get("image_url", "").strip()
    except (KeyError, ValueError):
        return None, None, "Enter valid event dates and times."

    if not all([title, category, venue]):
        return None, None, "Title, category, and venue are required."
    if end_time <= start_time:
        return None, None, "End time must be after start time."
    if registration_deadline > event_date:
        return None, None, "Registration deadline cannot be after the event date."
    if registration_start_date and registration_start_date > registration_deadline:
        return None, None, "Registration start date cannot be after the registration deadline."
    if capacity is not None and capacity < 1:
        return None, None, "Capacity must be a positive number."
    if status not in EVENT_STATUSES:
        return None, None, "Choose a valid event status."

    # Validate organizing department
    primary_dept = db.session.get(Department, department_id) if department_id else None
    if not is_college_wide and not primary_dept:
        return None, None, "Choose a valid primary organizing department or check College-Wide."

    # Multi-department selection
    target_dept_ids = request.form.getlist("target_departments")
    target_depts = []
    if not is_college_wide:
        for tid in target_dept_ids:
            try:
                dept_obj = db.session.get(Department, int(tid))
                if dept_obj and dept_obj not in target_depts:
                    target_depts.append(dept_obj)
            except ValueError:
                pass
        if primary_dept and primary_dept not in target_depts:
            target_depts.append(primary_dept)

    # Coordinator
    if current_user.role == "coordinator":
        coordinator_id = current_user.id
    else:
        coord_val = request.form.get("coordinator_id", type=int)
        coord_user = db.session.get(User, coord_val) if coord_val else None
        if not coord_user or coord_user.role not in ("coordinator", "admin"):
            return None, None, "Choose a valid event coordinator."
        coordinator_id = coord_user.id

    # Venue Conflict Detection: check overlapping time slots on same venue & date
    conflict_query = Event.query.filter(
        Event.venue.ilike(venue),
        Event.event_date == event_date,
        Event.status != "Cancelled",
        Event.start_time < end_time,
        Event.end_time > start_time,
    )
    if existing_event:
        conflict_query = conflict_query.filter(Event.id != existing_event.id)
    conflict = conflict_query.first()
    if conflict:
        return None, None, f"Venue Scheduling Conflict: Venue '{venue}' is already booked for '{conflict.title}' ({conflict.start_time.strftime('%H:%M')} - {conflict.end_time.strftime('%H:%M')}) on {event_date}."

    values = {
        "title": title,
        "description": description,
        "category": category,
        "event_type": event_type,
        "venue": venue,
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "registration_start_date": registration_start_date,
        "registration_deadline": registration_deadline,
        "capacity": capacity,
        "department_id": primary_dept.id if primary_dept else None,
        "status": status,
        "is_college_wide": is_college_wide,
        "coordinator_id": coordinator_id,
        "image_url": image_url,
    }
    return values, target_depts, None


@events_bp.route("/create", methods=["GET", "POST"])
@roles_required("admin", "coordinator")
def create():
    departments = Department.query.order_by(Department.name).all()
    coordinators = User.query.filter(User.role.in_(("coordinator", "admin"))).order_by(User.name).all()

    if request.method == "POST":
        values, target_depts, error = parse_event_form()
        if error:
            flash(error, "danger")
        else:
            event = Event(**values)
            if target_depts:
                event.target_departments = target_depts
            db.session.add(event)
            db.session.flush()

            log_action("EVENT_CREATED", details=f"Created event '{event.title}' scheduled for {event.event_date}")
            # Notify students of newly published upcoming event
            if event.status == "Upcoming":
                create_notification(
                    title="New Event Announced!",
                    message=f"'{event.title}' has been scheduled for {event.event_date.strftime('%B %d, %Y')} at {event.venue}.",
                    target_role="student",
                    category="event",
                    link=url_for("events.detail", event_id=event.id),
                )
            db.session.commit()
            flash("Event created.", "success")
            return redirect(url_for("events.detail", event_id=event.id))

    return render_template(
        "events/form.html",
        event=None,
        departments=departments,
        statuses=EVENT_STATUSES,
        categories=EVENT_CATEGORIES,
        event_types=EVENT_TYPES,
        coordinators=coordinators,
    )


@events_bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
@roles_required("admin", "coordinator")
def edit(event_id):
    event = db.get_or_404(Event, event_id)
    if not can_manage_event(event):
        abort(403)
    departments = Department.query.order_by(Department.name).all()
    coordinators = User.query.filter(User.role.in_(("coordinator", "admin"))).order_by(User.name).all()

    if request.method == "POST":
        old_date = event.event_date
        old_status = event.status
        values, target_depts, error = parse_event_form(event)
        if error:
            flash(error, "danger")
        else:
            for key, value in values.items():
                setattr(event, key, value)
            if target_depts is not None:
                event.target_departments = target_depts

            log_action("EVENT_UPDATED", details=f"Updated event #{event.id} '{event.title}'")

            # Check if rescheduled or cancelled
            if old_date != event.event_date:
                create_notification(
                    title="Event Rescheduled",
                    message=f"'{event.title}' has been rescheduled to {event.event_date.strftime('%B %d, %Y')}.",
                    target_role="student",
                    category="event",
                    link=url_for("events.detail", event_id=event.id),
                )
            if old_status != "Cancelled" and event.status == "Cancelled":
                create_notification(
                    title="Event Cancelled",
                    message=f"Notice: '{event.title}' has been cancelled by the coordinators.",
                    target_role="student",
                    category="event",
                    link=url_for("events.detail", event_id=event.id),
                )

            db.session.commit()
            flash("Event updated successfully.", "success")
            return redirect(url_for("events.detail", event_id=event.id))

    return render_template(
        "events/form.html",
        event=event,
        departments=departments,
        statuses=EVENT_STATUSES,
        categories=EVENT_CATEGORIES,
        event_types=EVENT_TYPES,
        coordinators=coordinators,
    )


@events_bp.route("/<int:event_id>/delete", methods=["POST"])
@roles_required("admin")
def delete(event_id):
    event = db.get_or_404(Event, event_id)
    if Registration.query.filter_by(event_id=event.id).count():
        flash("Events with student registrations cannot be permanently deleted. Set status to 'Cancelled' instead.", "warning")
    else:
        title = event.title
        db.session.delete(event)
        log_action("EVENT_DELETED", details=f"Permanently deleted event '{title}'")
        db.session.commit()
        flash("Event deleted.", "success")
    return redirect(url_for("events.listing"))


@events_bp.route("/<int:event_id>/register", methods=["POST"])
@roles_required("student")
def register(event_id):
    auto_update_event_statuses()
    event = db.get_or_404(Event, event_id)

    today = date.today()
    if event.status != "Upcoming":
        flash("Registration is only open for upcoming events.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    if event.registration_start_date and today < event.registration_start_date:
        flash(f"Registration opens on {event.registration_start_date.strftime('%B %d, %Y')}.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    if event.registration_deadline < today:
        flash("Registration is closed for this event.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    # Department eligibility check
    if not event.is_eligible_student(current_user):
        flash(f"This event is exclusive to {event.departments_display}. Your department ({current_user.department.name if current_user.department else 'None'}) is not eligible.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    existing = Registration.query.filter_by(event_id=event.id, student_id=current_user.id).first()
    if existing and existing.status == "Active":
        flash("You are already registered for this event.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    # Capacity check
    active_count = Registration.query.filter_by(event_id=event.id, status="Active").count()
    if event.capacity is not None and active_count >= event.capacity:
        flash("This event is full. Maximum capacity reached.", "warning")
        return redirect(url_for("events.detail", event_id=event.id))

    if existing:
        existing.status = "Active"
        existing.registered_at = datetime.utcnow()
        existing.cancelled_at = None
        db.session.commit()
        flash("Registration restored.", "success")
    else:
        new_reg = Registration(event_id=event.id, student_id=current_user.id)
        db.session.add(new_reg)
        try:
            db.session.flush()
            # Student notification
            create_notification(
                title="Registration Confirmed!",
                message=f"You are successfully registered for '{event.title}' scheduled on {event.event_date.strftime('%B %d, %Y')} at {event.venue}.",
                user_id=current_user.id,
                category="registration",
                link=url_for("events.detail", event_id=event.id),
            )
            # Admin / Coordinator notification
            create_notification(
                title="New Event Registration",
                message=f"Student {current_user.name} ({current_user.student_id or 'No USN'}) registered for '{event.title}'.",
                target_role="admin",
                category="registration",
            )
            # Check if capacity reached
            if event.capacity is not None and (active_count + 1) >= event.capacity:
                create_notification(
                    title="Event Capacity Reached!",
                    message=f"Event '{event.title}' has reached its maximum capacity of {event.capacity} participants.",
                    target_role="admin",
                    category="alert",
                    link=url_for("admin.registrations", event_id=event.id),
                )
            db.session.commit()
            flash("You are registered for this event.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("You are already registered for this event.", "warning")

    return redirect(url_for("events.detail", event_id=event.id))


@events_bp.route("/registration/<int:registration_id>/cancel", methods=["POST"])
@roles_required("student")
def cancel_registration(registration_id):
    registration = db.get_or_404(Registration, registration_id)
    if registration.student_id != current_user.id:
        abort(403)
    if registration.event.event_date < date.today() or registration.event.status in ("Completed", "Cancelled"):
        flash("This registration can no longer be cancelled.", "warning")
    else:
        registration.status = "Cancelled"
        registration.cancelled_at = datetime.utcnow()
        create_notification(
            title="Registration Cancelled",
            message=f"You cancelled your registration for '{registration.event.title}'.",
            user_id=current_user.id,
            category="registration",
        )
        db.session.commit()
        flash("Registration cancelled.", "success")
    return redirect(url_for("students.dashboard"))

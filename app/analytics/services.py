from collections import Counter
from datetime import date

from app.models import Department, Event, Registration, User

POPULARITY_WEIGHTS = {
    "registration_fill_rate": 0.40,
    "attendance_rate": 0.40,
    "normalized_feedback": 0.20,
}


def active_registrations(event):
    return [registration for registration in event.registrations if registration.status == "Active"]


def event_metrics(event):
    registrations = active_registrations(event)
    total = len(registrations)
    present = sum(
        1
        for registration in registrations
        if registration.attendance and registration.attendance.status == "Present"
    )
    absent = sum(
        1
        for registration in registrations
        if registration.attendance and registration.attendance.status == "Absent"
    )
    excused = sum(
        1
        for registration in registrations
        if registration.attendance and registration.attendance.status == "Excused"
    )

    # Registration fill rate
    if event.capacity and event.capacity > 0:
        fill = min(total / event.capacity * 100, 100)
    else:
        fill = None

    # Attendance rate = (Present / Eligible Active Registrations) * 100
    attendance_rate = (present / total * 100) if total > 0 else 0.0

    # Feedback ratings (average of satisfaction)
    ratings = [
        registration.feedback.satisfaction
        for registration in registrations
        if registration.feedback is not None
    ]
    average_rating = sum(ratings) / len(ratings) if ratings else None

    # Normalized feedback score: (Average Rating / 5.0) * 100
    normalized_feedback = ((average_rating / 5.0) * 100) if average_rating is not None else 0.0

    score = (
        POPULARITY_WEIGHTS["registration_fill_rate"] * (fill or 0)
        + POPULARITY_WEIGHTS["attendance_rate"] * attendance_rate
        + POPULARITY_WEIGHTS["normalized_feedback"] * normalized_feedback
    )

    return {
        "registrations": total,
        "attended": present,
        "absent": absent,
        "excused": excused,
        "capacity": event.capacity,
        "registration_fill_rate": round(fill, 1) if fill is not None else None,
        "attendance_rate": round(attendance_rate, 1),
        "average_rating": round(average_rating, 2) if average_rating is not None else None,
        "normalized_feedback": round(normalized_feedback, 1),
        "popularity_score": round(score, 1),
    }


def filtered_events(args):
    query = Event.query
    if args.get("department"):
        try:
            department_id = int(args["department"])
            query = query.filter(
                (Event.department_id == department_id)
                | Event.target_departments.any(Department.id == department_id)
                | (Event.is_college_wide == True)
            )
        except ValueError as error:
            raise ValueError("Department filter must be a valid department ID.") from error

    if args.get("category"):
        query = query.filter(Event.category == args["category"])
    if args.get("status"):
        query = query.filter(Event.status == args["status"])

    parsed_dates = {}
    for key in ("start", "end"):
        if args.get(key):
            try:
                parsed_dates[key] = date.fromisoformat(args[key])
            except ValueError as error:
                raise ValueError(f"{key.title()} date must use YYYY-MM-DD.") from error

    if parsed_dates.get("start") and parsed_dates.get("end") and parsed_dates["start"] > parsed_dates["end"]:
        raise ValueError("Start date must be on or before end date.")
    if parsed_dates.get("start"):
        query = query.filter(Event.event_date >= parsed_dates["start"])
    if parsed_dates.get("end"):
        query = query.filter(Event.event_date <= parsed_dates["end"])

    if args.get("coordinator_id"):
        try:
            coordinator_id = int(args["coordinator_id"])
            query = query.filter(Event.coordinator_id == coordinator_id)
        except ValueError as error:
            raise ValueError("Coordinator ID must be an integer.") from error

    return query.order_by(Event.event_date, Event.title).all()


def dashboard_data(args):
    events = filtered_events(args)
    academic_year = args.get("academic_year")

    # Filter registrations by academic year if specified
    all_departments = Department.query.order_by(Department.name).all()
    # Initialize department counts for all 9 departments so none are missing
    departments_counter = {dept.name: 0 for dept in all_departments}

    metrics = [event_metrics(event) for event in events]
    registration_by_event = {
        event.title: metric["registrations"] for event, metric in zip(events, metrics)
    }

    categories = Counter()
    attendance_status = Counter({"Present": 0, "Absent": 0, "Excused": 0, "Unmarked": 0})
    monthly = Counter()
    ratings = {}
    comparative = {}

    for event, metric in zip(events, metrics):
        categories[event.category] += metric["registrations"]
        ratings[event.title] = metric["average_rating"]
        comparative[event.title] = {
            "registered": metric["registrations"],
            "attended": metric["attended"],
        }
        for reg in active_registrations(event):
            if academic_year and reg.student.academic_year != academic_year:
                continue

            # Increment student's department count
            dept_name = reg.student.department.name if reg.student.department else "Unassigned"
            departments_counter[dept_name] = departments_counter.get(dept_name, 0) + 1

            monthly[reg.registered_at.strftime("%Y-%m")] += 1
            status = reg.attendance.status if reg.attendance else "Unmarked"
            attendance_status[status] += 1

    total_registrations = sum(metric["registrations"] for metric in metrics)
    total_attendance = sum(metric["attended"] for metric in metrics)
    total_absent = sum(metric["absent"] for metric in metrics)
    total_excused = sum(metric["excused"] for metric in metrics)

    rating_values = [val for val in ratings.values() if val is not None]
    scores = sorted(
        ({"title": event.title, **metric} for event, metric in zip(events, metrics)),
        key=lambda item: item["popularity_score"],
        reverse=True,
    )

    return {
        "cards": {
            "total_events": len(events),
            "upcoming_events": sum(1 for e in events if e.status == "Upcoming"),
            "completed_events": sum(1 for e in events if e.status == "Completed"),
            "total_registrations": total_registrations,
            "total_attendance": total_attendance,
            "total_absent": total_absent,
            "total_excused": total_excused,
            "average_attendance_rate": round(
                sum(m["attendance_rate"] for m in metrics) / len(metrics), 1
            ) if metrics else 0.0,
            "average_feedback_rating": round(
                sum(rating_values) / len(rating_values), 2
            ) if rating_values else 0.0,
        },
        "registrations_by_event": registration_by_event,
        "registrations_by_category": dict(categories),
        "monthly_registrations": dict(sorted(monthly.items())),
        "department_participation": departments_counter,
        "attendance_status": dict(attendance_status),
        "ratings_by_event": ratings,
        "top_events": scores[:5],
        "registered_vs_attended": comparative,
        "popularity_weights": POPULARITY_WEIGHTS,
    }


def feedback_themes(comments):
    positive = {"great", "excellent", "engaging", "helpful", "enjoyed", "good", "well", "informative", "organized", "inspiring", "smooth"}
    negative = {"poor", "late", "crowded", "confusing", "bad", "improve", "unclear", "noisy", "disorganized", "short", "technical", "rushed"}
    words = Counter(
        word.strip(".,!?;:()[]{}\"'").lower()
        for comment in comments
        for word in comment.split()
    )
    return {
        "positive": [(word, count) for word, count in words.most_common() if word in positive][:6],
        "improvement": [(word, count) for word, count in words.most_common() if word in negative][:6],
    }

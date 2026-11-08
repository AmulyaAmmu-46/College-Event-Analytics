from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from app.analytics.services import dashboard_data, filtered_events
from app.events.routes import EVENT_CATEGORIES, EVENT_STATUSES
from app.models import Department, Event, User
from app.security import roles_required

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def scoped_filters():
    args = request.args.to_dict()
    if current_user.role == "coordinator":
        args["coordinator_id"] = current_user.id
    return args


@analytics_bp.route("/")
@roles_required("admin", "coordinator")
def dashboard():
    """Advanced Event Analytics Dashboard with 8 Chart.js visualizations and dynamic filters."""
    departments = Department.query.order_by(Department.name).all()
    academic_years = [
        row[0] for row in User.query.with_entities(User.academic_year)
        .filter(User.academic_year != None, User.role == "student")
        .distinct()
        .all()
    ]
    if not academic_years:
        academic_years = ["Year 1", "Year 2", "Year 3", "Year 4", "MCA Year 1", "MCA Year 2"]

    return render_template(
        "analytics/dashboard.html",
        departments=departments,
        categories=EVENT_CATEGORIES,
        statuses=EVENT_STATUSES,
        academic_years=sorted(academic_years),
    )


@analytics_bp.route("/data")
@roles_required("admin", "coordinator")
def data():
    """Filterable JSON API endpoint powering all 8 Chart.js charts."""
    args = scoped_filters()
    try:
        result = dashboard_data(args)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if current_user.role == "coordinator":
        events = filtered_events(args)
        allowed = {event.title for event in events}
        result["registrations_by_event"] = {
            key: value for key, value in result["registrations_by_event"].items() if key in allowed
        }
    return jsonify(result)

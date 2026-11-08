import os

from flask import Flask, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import csrf, db, login_manager


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object("config.Config")
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY") and not app.testing:
        raise RuntimeError("Set SECRET_KEY in the environment before starting the application.")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import Notification, User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Blueprint imports
    from app.admin.routes import admin_bp
    from app.analytics.routes import analytics_bp
    from app.attendance.routes import attendance_bp
    from app.auth.routes import auth_bp
    from app.events.routes import events_bp
    from app.feedback.routes import feedback_bp
    from app.notifications.routes import notifications_bp
    from app.reports.routes import reports_bp
    from app.students.routes import students_bp

    for blueprint in (
        auth_bp,
        admin_bp,
        analytics_bp,
        attendance_bp,
        events_bp,
        feedback_bp,
        notifications_bp,
        reports_bp,
        students_bp,
    ):
        app.register_blueprint(blueprint)

    @app.context_processor
    def inject_global_data():
        unread_count = 0
        if current_user.is_authenticated:
            roles = [current_user.role]
            if current_user.role == "coordinator":
                roles.append("admin")
            unread_count = Notification.query.filter(
                or_(
                    Notification.user_id == current_user.id,
                    Notification.target_role.in_(roles),
                ),
                Notification.is_read == False,
            ).count()
        return dict(unread_notifications_count=unread_count)

    @app.route("/")
    def index():
        from app.models import Department, Event, User
        if current_user.is_authenticated:
            return render_template("home.html")
        # For public visitors on landing page, pass database stats and upcoming highlights
        featured_events = (
            Event.query.filter(Event.status == "Upcoming")
            .order_by(Event.event_date.asc())
            .limit(3)
            .all()
        )
        stats = {
            "total_events": Event.query.count(),
            "total_departments": Department.query.count(),
            "total_students": User.query.filter_by(role="student").count(),
        }
        return render_template("landing.html", featured_events=featured_events, stats=stats)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, message="You do not have permission to access this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="The requested page could not be found."), 404

    @app.cli.command("init-db")
    def init_db_command():
        """Create missing tables without removing existing data."""
        db.create_all()
        print("Database tables are ready.")

    return app

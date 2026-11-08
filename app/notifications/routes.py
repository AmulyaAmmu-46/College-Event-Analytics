from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def get_user_notifications_query(user):
    """Filter notifications for a specific user or user's role."""
    roles = [user.role]
    if user.role == "coordinator":
        roles.append("admin")  # Coordinators also get administrative event alerts
    return Notification.query.filter(
        or_(
            Notification.user_id == user.id,
            Notification.target_role.in_(roles),
        )
    ).order_by(Notification.created_at.desc())


@notifications_bp.route("/")
@login_required
def index():
    notifications = get_user_notifications_query(current_user).limit(100).all()
    return render_template("notifications/index.html", notifications=notifications)


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    # verify ownership or role target
    if notification.user_id and notification.user_id != current_user.id:
        if notification.target_role != current_user.role:
            return jsonify({"success": False, "error": "Unauthorized"}), 403
    notification.is_read = True
    db.session.commit()
    target = request.referrer or url_for("notifications.index")
    return redirect(target)


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    notifications = get_user_notifications_query(current_user).filter_by(is_read=False).all()
    for n in notifications:
        n.is_read = True
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/unread-count")
@login_required
def unread_count():
    count = get_user_notifications_query(current_user).filter_by(is_read=False).count()
    return jsonify({"count": count})

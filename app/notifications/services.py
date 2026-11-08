from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog, Notification


def create_notification(title, message, user_id=None, target_role=None, category="general", link=None):
    """
    Creates an in-app notification.
    If user_id is provided, it targets a specific user.
    If target_role is provided (e.g., 'admin', 'student'), it targets users with that role.
    """
    notification = Notification(
        user_id=user_id,
        target_role=target_role,
        title=title,
        message=message,
        category=category,
        link=link,
    )
    db.session.add(notification)
    return notification


def log_action(action, details=None, user=None):
    """
    Records an administrative action into the audit_log table.
    """
    user_id = None
    if user:
        user_id = user.id
    elif has_request_context() and current_user and current_user.is_authenticated:
        user_id = current_user.id

    ip_address = None
    if has_request_context():
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        details=str(details) if details else None,
        ip_address=ip_address,
    )
    db.session.add(log_entry)
    return log_entry

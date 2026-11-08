from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def can_manage_event(event):
    return current_user.role == "admin" or (
        current_user.role == "coordinator" and event.coordinator_id == current_user.id
    )


def require_event_access(event):
    if not can_manage_event(event):
        abort(403)

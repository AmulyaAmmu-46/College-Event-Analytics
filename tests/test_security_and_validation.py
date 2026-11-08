from datetime import date, time, timedelta

import pytest
from app.analytics.services import event_metrics
from app.extensions import db
from app.models import Department, Event, Registration, User


def test_unauthorized_admin_access_redirects_or_forbids(client):
    # Anonymous user accessing admin routes is redirected to login
    for path in (
        "/admin/dashboard",
        "/admin/registrations",
        "/admin/students",
        "/admin/departments",
        "/admin/audit-logs",
        "/events/create",
        "/attendance/",
        "/feedback/",
    ):
        response = client.get(path)
        assert response.status_code in (302, 401, 403), f"Failed for {path}"


def test_student_cannot_access_admin_urls(client, login_as):
    login_as(client, "student@test.local")
    # Logged-in student receives 403 Forbidden on admin-only routes
    for path in (
        "/admin/dashboard",
        "/admin/registrations",
        "/admin/students",
        "/admin/departments",
        "/admin/users",
        "/admin/audit-logs",
        "/events/create",
        "/attendance/",
        "/feedback/",
    ):
        response = client.get(path)
        assert response.status_code == 403, f"Expected 403 Forbidden for {path}, got {response.status_code}"


def test_invalid_event_time_range_rejected(client, login_as, app):
    login_as(client, "admin@test.local")
    with app.app_context():
        dept_id = Department.query.first().id
        coord_id = User.query.filter_by(role="coordinator").first().id

    # End time before start time
    invalid_form = {
        "title": "Invalid Timing Event",
        "description": "Test",
        "category": "Workshops",
        "venue": "Lab 1",
        "event_date": (date.today() + timedelta(days=5)).isoformat(),
        "start_time": "14:00",
        "end_time": "12:00",  # Invalid: end < start
        "registration_deadline": (date.today() + timedelta(days=4)).isoformat(),
        "department_id": str(dept_id),
        "coordinator_id": str(coord_id),
        "status": "Upcoming",
    }
    response = client.post("/events/create", data=invalid_form, follow_redirects=True)
    assert b"End time must be after start time" in response.data


def test_registration_deadline_after_event_date_rejected(client, login_as, app):
    login_as(client, "admin@test.local")
    with app.app_context():
        dept_id = Department.query.first().id
        coord_id = User.query.filter_by(role="coordinator").first().id

    # Deadline after event date
    invalid_form = {
        "title": "Invalid Deadline Event",
        "description": "Test",
        "category": "Workshops",
        "venue": "Lab 2",
        "event_date": (date.today() + timedelta(days=5)).isoformat(),
        "start_time": "10:00",
        "end_time": "12:00",
        "registration_deadline": (date.today() + timedelta(days=7)).isoformat(),  # Invalid: deadline > event_date
        "department_id": str(dept_id),
        "coordinator_id": str(coord_id),
        "status": "Upcoming",
    }
    response = client.post("/events/create", data=invalid_form, follow_redirects=True)
    assert b"Registration deadline cannot be after the event date" in response.data


def test_popularity_score_safe_with_missing_feedback_and_zero_capacity(app):
    with app.app_context():
        dept = Department.query.first()
        coord = User.query.filter_by(role="coordinator").first()
        ev = Event(
            title="Event with No Capacity and No Feedback",
            description="Testing safety",
            category="Competitions",
            venue="Ground",
            event_date=date.today() + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(11, 0),
            registration_deadline=date.today(),
            capacity=None,  # No capacity
            status="Upcoming",
            department=dept,
            coordinator=coord,
        )
        db.session.add(ev)
        db.session.commit()

        metrics = event_metrics(ev)
        assert metrics["registration_fill_rate"] is None
        assert metrics["average_rating"] is None
        assert metrics["popularity_score"] >= 0.0
        assert metrics["popularity_score"] <= 100.0

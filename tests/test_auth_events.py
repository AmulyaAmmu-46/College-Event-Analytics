from datetime import date, timedelta

from app.extensions import db
from app.models import Attendance, Event, Registration, User


def test_login_logout_and_invalid_credentials(client):
    response = client.post("/auth/login", data={"email": "student@test.local", "password": "bad"})
    assert b"Invalid email or password" in response.data
    response = client.post(
        "/auth/login",
        data={"email": "student@test.local", "password": "TestPass123!"},
        follow_redirects=True,
    )
    assert b"Hello, Student User" in response.data
    response = client.post("/auth/logout", follow_redirects=True)
    assert b"Sign in" in response.data


def test_profile_can_change_password_with_current_password(client, login_as):
    login_as(client, "student@test.local")
    response = client.post(
        "/auth/profile",
        data={
            "name": "Student Updated",
            "student_id": "student@test.local",
            "academic_year": "Year 4",
            "department_id": "1",
            "current_password": "TestPass123!",
            "new_password": "NewTestPass123!",
        },
        follow_redirects=True,
    )
    assert b"Profile updated" in response.data
    client.post("/auth/logout")
    response = client.post(
        "/auth/login",
        data={"email": "student@test.local", "password": "NewTestPass123!"},
        follow_redirects=True,
    )
    assert b"Hello, Student Updated" in response.data


def test_role_restrictions(client, login_as):
    login_as(client, "student@test.local")
    assert client.get("/analytics/").status_code == 403
    client.post("/auth/logout")
    login_as(client, "coord@test.local")
    assert client.get("/admin/users").status_code == 403


def test_registration_duplicate_and_capacity(app, client, login_as):
    with app.app_context():
        event_id = Event.query.first().id
    login_as(client, "student@test.local")
    first = client.post(f"/events/{event_id}/register", follow_redirects=True)
    assert b"registered for this event" in first.data
    again = client.post(f"/events/{event_id}/register", follow_redirects=True)
    assert b"already registered" in again.data
    login_as(client, "other@test.local")
    full = client.post(f"/events/{event_id}/register", follow_redirects=True)
    assert b"event is full" in full.data
    with app.app_context():
        assert Registration.query.filter_by(event_id=event_id, status="Active").count() == 1


def test_registration_deadline_is_enforced(app, client, login_as):
    with app.app_context():
        event = Event.query.first()
        event.registration_deadline = date.today() - timedelta(days=1)
        event_id = event.id
        db.session.commit()
    login_as(client, "student@test.local")
    response = client.post(f"/events/{event_id}/register", follow_redirects=True)
    assert b"Registration is closed" in response.data


def test_student_cannot_access_another_registration_cancel(client, app, login_as):
    with app.app_context():
        event = Event.query.first()
        student = User.query.filter_by(email="student@test.local").first()
        registration = Registration(event=event, student=student)
        db.session.add(registration)
        db.session.commit()
        registration_id = registration.id
    login_as(client, "other@test.local")
    assert client.post(f"/events/registration/{registration_id}/cancel").status_code == 403


def test_role_pages_render_without_template_errors(client, app, login_as):
    with app.app_context():
        event_id = Event.query.first().id
    for path in ("/events/", f"/events/{event_id}"):
        assert client.get(path).status_code == 200
    login_as(client, "admin@test.local")
    for path in (
        "/admin/users",
        "/admin/departments",
        "/analytics/",
        "/reports/",
        "/events/create",
        f"/events/{event_id}/edit",
        f"/attendance/events/{event_id}",
        f"/attendance/events/{event_id}/participants",
        f"/feedback/events/{event_id}",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
    login_as(client, "student@test.local")
    assert client.get("/students/dashboard").status_code == 200


def test_admin_can_create_and_edit_event(client, app, login_as):
    with app.app_context():
        department_id = Event.query.first().department_id
        coordinator_id = User.query.filter_by(role="coordinator").first().id
    login_as(client, "admin@test.local")
    form = {
        "title": "New campus seminar",
        "description": "A test description",
        "category": "Seminar",
        "venue": "Room 12",
        "event_date": (date.today() + timedelta(days=10)).isoformat(),
        "start_time": "10:00",
        "end_time": "11:30",
        "registration_deadline": (date.today() + timedelta(days=8)).isoformat(),
        "capacity": "20",
        "department_id": str(department_id),
        "coordinator_id": str(coordinator_id),
        "status": "Upcoming",
    }
    response = client.post("/events/create", data=form, follow_redirects=True)
    assert b"Event created" in response.data
    with app.app_context():
        event = Event.query.filter_by(title="New campus seminar").first()
        assert event is not None
        form["title"] = "Updated campus seminar"
        form["registration_deadline"] = (date.today() + timedelta(days=9)).isoformat()
        event_id = event.id
    response = client.post(f"/events/{event_id}/edit", data=form, follow_redirects=True)
    assert b"Event updated" in response.data
    with app.app_context():
        assert db.session.get(Event, event_id).title == "Updated campus seminar"


def test_coordinator_cannot_manage_unassigned_event(client, app, login_as):
    with app.app_context():
        event = Event.query.first()
        event.coordinator_id = User.query.filter_by(email="admin@test.local").first().id
        event_id = event.id
        db.session.commit()
    login_as(client, "coord@test.local")
    assert client.get(f"/events/{event_id}/edit").status_code == 403
    assert client.get(f"/attendance/events/{event_id}").status_code == 403


def test_attendance_is_saved_and_reflected_in_registration_history(client, app, login_as):
    with app.app_context():
        event = Event.query.first()
        student = User.query.filter_by(email="student@test.local").first()
        registration = Registration(event=event, student=student)
        db.session.add(registration)
        db.session.commit()
        event_id, registration_id = event.id, registration.id
    login_as(client, "coord@test.local")
    response = client.post(
        f"/attendance/events/{event_id}",
        data={f"attendance_{registration_id}": "Present"},
        follow_redirects=True,
    )
    assert b"Attendance saved" in response.data
    with app.app_context():
        registration = db.session.get(Registration, registration_id)
        assert registration.attendance.status == "Present"
        assert registration.attendance.updated_at is not None


def test_feedback_requires_completed_attendance_and_is_single_submission(client, app, login_as):
    with app.app_context():
        event = Event.query.first()
        event.status = "Completed"
        registration = Registration(
            event=event,
            student=User.query.filter_by(email="student@test.local").first(),
        )
        db.session.add(registration)
        db.session.flush()
        db.session.add(Attendance(registration=registration, status="Present"))
        db.session.commit()
        registration_id = registration.id
    login_as(client, "student@test.local")
    data = {
        "satisfaction": "5",
        "organization": "4",
        "content_quality": "5",
        "venue_rating": "4",
    }
    response = client.post(
        f"/feedback/registration/{registration_id}",
        data=data,
        follow_redirects=True,
    )
    assert b"Thank you for your feedback" in response.data
    second = client.get(f"/feedback/registration/{registration_id}", follow_redirects=True)
    assert b"already been submitted" in second.data

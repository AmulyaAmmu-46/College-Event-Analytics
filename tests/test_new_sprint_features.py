from datetime import date, datetime, time, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook
from app.analytics.services import event_metrics
from app.extensions import db
from app.models import Attendance, Department, Event, Feedback, Notification, Registration, User


def test_dedicated_admin_login_and_role_isolation(client):
    # Student cannot log in through /auth/admin-login
    response = client.post(
        "/auth/admin-login",
        data={"email": "student@test.local", "password": "TestPass123!"},
        follow_redirects=True,
    )
    assert b"Access restricted" in response.data or b"reserved for Administrators" in response.data

    # Admin successfully logs in through /auth/admin-login
    response = client.post(
        "/auth/admin-login",
        data={"email": "admin@test.local", "password": "TestPass123!"},
        follow_redirects=True,
    )
    assert b"Admin Analytics Dashboard" in response.data or b"Administrative Control" in response.data


def test_student_registration_with_usn_and_phone(client, app):
    with app.app_context():
        dept = Department.query.first()
        dept_id = dept.id

    reg_data = {
        "name": "Kavya Murthy",
        "email": "kavya@test.local",
        "student_id": "1MS21CS099",
        "phone_number": "+91 9988776655",
        "academic_year": "Year 3",
        "department_id": str(dept_id),
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    response = client.post("/auth/register", data=reg_data, follow_redirects=True)
    assert b"Student account created successfully" in response.data or b"sign in" in response.data

    # Verify duplicate USN is blocked
    dup_data = dict(reg_data, email="different@test.local")
    dup_response = client.post("/auth/register", data=dup_data, follow_redirects=True)
    assert b"student ID / USN" in dup_response.data

    # Verify student can login using USN instead of email
    login_response = client.post(
        "/auth/login",
        data={"email": "1MS21CS099", "password": "Password123!"},
        follow_redirects=True,
    )
    assert b"Kavya Murthy" in login_response.data or b"Hello, Kavya Murthy" in login_response.data


def test_nine_departments_and_multi_department_assignment(app):
    with app.app_context():
        dept_codes = ["CIVIL", "MECH", "IT", "SE", "AIML", "CYS", "MCA", "AERO", "AEROSP"]
        for code in dept_codes:
            if not Department.query.filter_by(code=code).first():
                db.session.add(Department(name=f"Dept {code}", code=code))
        db.session.commit()

        assert Department.query.count() >= 9
        d1 = Department.query.filter_by(code="AIML").first()
        d2 = Department.query.filter_by(code="CYS").first()

        coord = User.query.filter_by(role="coordinator").first()
        multi_event = Event(
            title="Joint AI and Cyber Summit",
            description="Inter-department workshop",
            category="Workshops",
            venue="Seminar Hall B",
            event_date=date.today() + timedelta(days=15),
            start_time=time(14, 0),
            end_time=time(16, 0),
            registration_deadline=date.today() + timedelta(days=14),
            capacity=50,
            status="Upcoming",
            department=d1,
            coordinator=coord,
            is_college_wide=False,
        )
        multi_event.target_departments = [d1, d2]
        db.session.add(multi_event)
        db.session.commit()

        assert multi_event.is_eligible_student(User(role="student", department_id=d1.id))
        assert multi_event.is_eligible_student(User(role="student", department_id=d2.id))


def test_venue_scheduling_conflict_prevention(client, app, login_as):
    login_as(client, "admin@test.local")
    with app.app_context():
        dept_id = Department.query.first().id
        coord_id = User.query.filter_by(role="coordinator").first().id

    event_date = (date.today() + timedelta(days=20)).isoformat()
    # Event 1
    form1 = {
        "title": "First Hall Event",
        "description": "Morning Session",
        "category": "Workshops",
        "venue": "Main Auditorium",
        "event_date": event_date,
        "start_time": "10:00",
        "end_time": "13:00",
        "registration_deadline": event_date,
        "capacity": "100",
        "department_id": str(dept_id),
        "coordinator_id": str(coord_id),
        "status": "Upcoming",
    }
    resp1 = client.post("/events/create", data=form1, follow_redirects=True)
    assert b"Event created" in resp1.data

    # Event 2 conflicting with Event 1 (same venue, same date, overlapping 11:00-14:00)
    form2 = dict(form1, title="Conflicting Hall Event", start_time="11:00", end_time="14:00")
    resp2 = client.post("/events/create", data=form2, follow_redirects=True)
    assert b"Scheduling Conflict" in resp2.data or b"Conflict" in resp2.data

    # Event 3 non-conflicting (same venue, same date, afternoon 14:00-17:00)
    form3 = dict(form1, title="Afternoon Hall Event", start_time="14:00", end_time="17:00")
    resp3 = client.post("/events/create", data=form3, follow_redirects=True)
    assert b"Event created" in resp3.data


def test_bulk_attendance_and_rate_formula(client, app, login_as):
    with app.app_context():
        ev = Event.query.first()
        student1 = User.query.filter_by(email="student@test.local").first()
        student2 = User.query.filter_by(email="other@test.local").first()

        db.session.add(Registration(event=ev, student=student1, status="Active"))
        db.session.add(Registration(event=ev, student=student2, status="Active"))
        db.session.commit()
        event_id = ev.id

    login_as(client, "admin@test.local")
    # Test bulk mark all present
    response = client.post(
        f"/attendance/events/{event_id}",
        data={"bulk_action": "mark_all_present"},
        follow_redirects=True,
    )
    assert b"Bulk attendance action applied" in response.data or b"Attendance" in response.data

    with app.app_context():
        metric = event_metrics(db.session.get(Event, event_id))
        assert metric["attendance_rate"] == 100.0


def test_in_app_notifications_lifecycle(client, app, login_as):
    with app.app_context():
        student = User.query.filter_by(email="student@test.local").first()
        notif = Notification(
            user_id=student.id,
            title="Registration Reminder",
            message="Don't forget your scheduled campus event tomorrow.",
            category="event",
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
        notif_id = notif.id

    login_as(client, "student@test.local")
    # Notification center loads
    resp = client.get("/notifications/")
    assert resp.status_code == 200
    assert b"Registration Reminder" in resp.data

    # Unread count endpoint
    count_resp = client.get("/notifications/unread-count")
    assert count_resp.status_code == 200
    assert count_resp.get_json()["count"] >= 1

    # Mark as read
    client.post(f"/notifications/{notif_id}/read", follow_redirects=True)
    with app.app_context():
        assert db.session.get(Notification, notif_id).is_read is True


def test_admin_portal_views_and_csv_exports(app, client, login_as):
    login_as(client, "admin@test.local")

    # Admin Portal pages render with 200
    assert client.get("/admin/dashboard").status_code == 200
    assert client.get("/admin/registrations").status_code == 200
    assert client.get("/admin/students").status_code == 200
    assert client.get("/admin/departments").status_code == 200
    assert client.get("/admin/audit-logs").status_code == 200
    assert client.get("/events/calendar").status_code == 200
    assert client.get("/events/calendar-data").status_code == 200
    assert client.get("/attendance/").status_code == 200
    assert client.get("/feedback/").status_code == 200

    # CSV Exports
    reg_csv = client.get("/admin/registrations/export.csv")
    assert reg_csv.status_code == 200
    assert reg_csv.mimetype == "text/csv"

    fb_csv = client.get("/feedback/export.csv")
    assert fb_csv.status_code == 200
    assert fb_csv.mimetype == "text/csv"

    with app.app_context():
        event_id = Event.query.first().id
    for path in (
        "/admin/registrations/export.xlsx",
        "/feedback/export.xlsx",
        f"/attendance/events/{event_id}/export.xlsx",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        worksheet = load_workbook(BytesIO(response.data)).active
        assert worksheet.max_row >= 1
        assert all(cell.value for cell in worksheet[1])
        assert worksheet.freeze_panes == "A2"

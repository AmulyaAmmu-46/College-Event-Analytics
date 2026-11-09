from datetime import date, time, timedelta
from io import BytesIO

from openpyxl import load_workbook
from app.analytics.services import event_metrics
from app.extensions import db
from app.models import Attendance, Event, Feedback, Registration, User


def test_attendance_rate_and_zero_registration_score(app):
    with app.app_context():
        event = Event.query.first()
        assert event_metrics(event)["attendance_rate"] == 0
        student = User.query.filter_by(role="student").first()
        registration = Registration(event=event, student=student)
        db.session.add(registration)
        db.session.flush()
        db.session.add(Attendance(registration=registration, status="Present"))
        db.session.commit()
        metric = event_metrics(event)
        assert metric["registrations"] == 1
        assert metric["attended"] == 1
        assert metric["attendance_rate"] == 100
        db.session.add(
            Feedback(
                registration=registration,
                satisfaction=5,
                organization=5,
                content_quality=5,
                venue_rating=5,
            )
        )
        db.session.commit()
        assert event_metrics(event)["popularity_score"] == 100


def test_dashboard_api_and_csv_exports(client, login_as):
    login_as(client, "admin@test.local")
    dashboard = client.get("/analytics/data")
    assert dashboard.status_code == 200
    assert "cards" in dashboard.get_json()
    assert dashboard.get_json()["cards"]["total_events"] == 1
    for report in ("registrations", "attendance", "feedback", "departments", "popularity", "monthly"):
        response = client.get(f"/reports/{report}.csv")
        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        excel_response = client.get(f"/reports/{report}.xlsx")
        assert excel_response.status_code == 200
        assert excel_response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        workbook = load_workbook(BytesIO(excel_response.data), read_only=False)
        worksheet = workbook.active
        assert worksheet.max_row >= 1
        assert worksheet.freeze_panes == "A2"
        assert worksheet.auto_filter.ref == worksheet.dimensions
        assert all(cell.value for cell in worksheet[1])


def test_coordinator_export_is_limited_to_assigned_events(app, client, login_as):
    with app.app_context():
        department = Event.query.first().department
        other = Event(
            title="Unassigned event",
            description="",
            category="Talk",
            venue="Room",
            event_date=date.today() + timedelta(days=3),
            start_time=time(9),
            end_time=time(10),
            registration_deadline=date.today() + timedelta(days=2),
            status="Upcoming",
            department=department,
            coordinator=User.query.filter_by(email="admin@test.local").first(),
        )
        db.session.add(other)
        db.session.commit()
    login_as(client, "coord@test.local")
    response = client.get("/reports/popularity.csv")
    assert b"Test event" in response.data
    assert b"Unassigned event" not in response.data


def test_excel_report_treats_text_as_text(app, client, login_as):
    with app.app_context():
        event = Event.query.first()
        event.title = "=1+1"
        db.session.commit()

    login_as(client, "admin@test.local")
    response = client.get("/reports/popularity.xlsx")
    worksheet = load_workbook(BytesIO(response.data)).active
    assert worksheet["A2"].value == "=1+1"
    assert worksheet["A2"].data_type == "s"


def test_empty_dashboard_returns_zero_values(app, client, login_as):
    with app.app_context():
        Event.query.delete()
        db.session.commit()
    login_as(client, "admin@test.local")
    data = client.get("/analytics/data").get_json()
    assert data["cards"]["total_events"] == 0
    assert data["cards"]["total_registrations"] == 0
    assert data["cards"]["average_attendance_rate"] == 0


def test_invalid_report_filters_return_validation_error(client, login_as):
    login_as(client, "admin@test.local")
    assert client.get("/analytics/data?start=not-a-date").status_code == 400
    response = client.get("/reports/popularity.csv?start=2026-03-02&end=2026-02-01")
    assert response.status_code == 400
    assert b"Start date must be on or before end date" in response.data

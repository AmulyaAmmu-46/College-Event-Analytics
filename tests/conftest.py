from datetime import date, time, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Department, Event, User


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-key",
        }
    )
    with application.app_context():
        db.create_all()
        department = Department(name="Computing", code="CMP")
        db.session.add(department)
        db.session.flush()
        for email, name, role in (
            ("admin@test.local", "Admin User", "admin"),
            ("coord@test.local", "Coordinator User", "coordinator"),
            ("student@test.local", "Student User", "student"),
            ("other@test.local", "Other Student", "student"),
        ):
            user = User(name=name, email=email, role=role, department=department, student_id=email.split("@")[0])
            user.set_password("TestPass123!")
            db.session.add(user)
        db.session.flush()
        event = Event(
            title="Test event",
            description="A test event",
            category="Workshop",
            venue="Hall A",
            event_date=date.today() + timedelta(days=5),
            start_time=time(10),
            end_time=time(12),
            registration_deadline=date.today() + timedelta(days=4),
            capacity=1,
            status="Upcoming",
            department=department,
            coordinator=User.query.filter_by(role="coordinator").first(),
        )
        db.session.add(event)
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, password="TestPass123!"):
    client.post("/auth/logout")
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


@pytest.fixture
def login_as():
    return login

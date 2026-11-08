from datetime import date, datetime, time, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    Attendance,
    AuditLog,
    Department,
    Event,
    Feedback,
    Notification,
    Registration,
    User,
)
from app.notifications.services import create_notification

DEMO_PASSWORD = "CampusDemo123!"

DEPARTMENTS_CONFIG = [
    ("Civil Engineering", "CIVIL"),
    ("Mechanical Engineering", "MECH"),
    ("Information Technology (IT)", "IT"),
    ("Software Engineering (SE)", "SE"),
    ("Artificial Intelligence and Machine Learning (AI/ML)", "AIML"),
    ("Cybersecurity", "CYS"),
    ("Master of Computer Applications (MCA)", "MCA"),
    ("Aeronautical Engineering", "AERO"),
    ("Aerospace Engineering", "AEROSP"),
]


def get_or_create_user(email, **values):
    user = User.query.filter_by(email=email).first()
    if user:
        return user
    user = User(email=email, **values)
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    return user


def seed_demo_data():
    # 1. Seed All 9 Departments
    departments = {}
    for name, code in DEPARTMENTS_CONFIG:
        dept = Department.query.filter_by(code=code).first()
        if not dept:
            dept = Department(name=name, code=code)
            db.session.add(dept)
        departments[code] = dept
    db.session.flush()

    # 2. Seed Administrator Account
    admin = get_or_create_user(
        "admin@college.edu",
        name="Chief Campus Administrator",
        role="admin",
        phone_number="+91 98765 00001",
    )
    # Also support admin@example.com for backward compatibility
    get_or_create_user(
        "admin@example.com",
        name="Campus Administrator",
        role="admin",
        phone_number="+91 98765 00002",
    )

    # 3. Seed at least Two Event Coordinators
    coordinator1 = get_or_create_user(
        "coordinator@college.edu",
        name="Prof. Marcus Vance",
        role="coordinator",
        department=departments["AIML"],
        phone_number="+91 98765 11001",
    )
    coordinator2 = get_or_create_user(
        "coordinator2@college.edu",
        name="Dr. Elena Rostova",
        role="coordinator",
        department=departments["SE"],
        phone_number="+91 98765 11002",
    )
    # Also support coordinator@example.com for backward compatibility
    get_or_create_user(
        "coordinator@example.com",
        name="Prof. Marcus Vance",
        role="coordinator",
        department=departments["AIML"],
        phone_number="+91 98765 11001",
    )

    # 4. Seed 12 Diverse Students Across All Departments
    student_specs = [
        ("student@example.com", "Aarav Sharma", "1MS21AI001", "+91 98765 20001", "Year 3", departments["AIML"]),
        ("student2@example.com", "Priya Patel", "1MS21SE014", "+91 98765 20002", "Year 3", departments["SE"]),
        ("student3@example.com", "Rohan Verma", "1MS21CY022", "+91 98765 20003", "Year 4", departments["CYS"]),
        ("student4@college.edu", "Ananya Reddy", "1MS22IT033", "+91 98765 20004", "Year 2", departments["IT"]),
        ("student5@college.edu", "Devendra Singh", "1MS21ME045", "+91 98765 20005", "Year 4", departments["MECH"]),
        ("student6@college.edu", "Neha Kulkarni", "1MS22CV012", "+91 98765 20006", "Year 2", departments["CIVIL"]),
        ("student7@college.edu", "Vikram Nair", "1MS21AE019", "+91 98765 20007", "Year 3", departments["AERO"]),
        ("student8@college.edu", "Sneha Joshi", "1MS21AS028", "+91 98765 20008", "Year 4", departments["AEROSP"]),
        ("student9@college.edu", "Karthik Raja", "1MS22MC007", "+91 98765 20009", "MCA Year 2", departments["MCA"]),
        ("student10@college.edu", "Divya Menon", "1MS23AI089", "+91 98765 20010", "Year 1", departments["AIML"]),
        ("student11@college.edu", "Aditya Deshmukh", "1MS22SE050", "+91 98765 20011", "Year 2", departments["SE"]),
        ("student12@college.edu", "Meera Pillai", "1MS23CY061", "+91 98765 20012", "Year 1", departments["CYS"]),
    ]
    students = []
    for email, name, usn, phone, year, dept in student_specs:
        s = get_or_create_user(
            email,
            name=name,
            role="student",
            student_id=usn,
            phone_number=phone,
            academic_year=year,
            department=dept,
        )
        students.append(s)
    db.session.flush()

    today = date.today()

    # 5. Seed 11 Realistic Sample Events Across All 10 Categories
    event_specs = [
        # (title, category, type, venue, date_offset, status, capacity, primary_dept, is_college_wide, coordinator, target_depts)
        (
            "National AI & Deep Learning Summit 2026",
            "Conferences",
            "Hybrid",
            "Dr. APJ Abdul Kalam Auditorium",
            -20,
            "Completed",
            40,
            departments["AIML"],
            True,
            coordinator1,
            [departments["AIML"], departments["SE"], departments["IT"], departments["CYS"]],
        ),
        (
            "Cloud Security & Ethical Hacking Hands-on",
            "Workshops",
            "Offline",
            "Cyber Defense Lab - Room 402",
            -12,
            "Completed",
            25,
            departments["CYS"],
            False,
            coordinator2,
            [departments["CYS"], departments["IT"], departments["SE"]],
        ),
        (
            "Full-Stack Web3 & Microservices Hackathon",
            "Hackathons",
            "Hybrid",
            "Innovation Hub - Floor 3",
            -5,
            "Completed",
            30,
            departments["SE"],
            True,
            coordinator2,
            [departments["SE"], departments["IT"], departments["AIML"], departments["MCA"]],
        ),
        (
            "Aerospace Dynamics & Propulsion Symposium",
            "Technical Events",
            "Offline",
            "Aero Hangar Seminar Hall",
            -2,
            "Completed",
            35,
            departments["AEROSP"],
            False,
            coordinator1,
            [departments["AEROSP"], departments["AERO"], departments["MECH"]],
        ),
        (
            "Annual College Cultural Fest - TARANG 2026",
            "Cultural Events",
            "Offline",
            "Main Campus Open Air Amphitheatre",
            4,
            "Upcoming",
            100,
            departments["AIML"],
            True,
            coordinator1,
            list(departments.values()),
        ),
        (
            "Autonomous Drone Design & Flight Competition",
            "Competitions",
            "Offline",
            "Campus Sports Field",
            9,
            "Upcoming",
            30,
            departments["AERO"],
            False,
            coordinator1,
            [departments["AERO"], departments["AEROSP"], departments["MECH"]],
        ),
        (
            "Robotics & Smart Automation in Manufacturing",
            "Seminars",
            "Offline",
            "Mechanical Engineering Seminar Hall",
            14,
            "Upcoming",
            45,
            departments["MECH"],
            False,
            coordinator2,
            [departments["MECH"], departments["CIVIL"], departments["AERO"]],
        ),
        (
            "Sustainable Infrastructure & Green Smart Cities",
            "Awareness Programs",
            "Hybrid",
            "Civil Dept Conference Room 101",
            18,
            "Upcoming",
            50,
            departments["CIVIL"],
            False,
            coordinator1,
            [departments["CIVIL"], departments["MECH"]],
        ),
        (
            "Inter-Department Cricket & Football Tournament",
            "Sports Events",
            "Offline",
            "College Sports Complex",
            25,
            "Upcoming",
            60,
            departments["MCA"],
            True,
            coordinator2,
            list(departments.values()),
        ),
        (
            "Modern Enterprise Software with Cloud-Native Java",
            "Workshops",
            "Online",
            "Virtual Zoom Auditorium",
            30,
            "Upcoming",
            80,
            departments["MCA"],
            False,
            coordinator2,
            [departments["MCA"], departments["SE"], departments["IT"]],
        ),
        (
            "Campus Blood Donation & Health Awareness Camp",
            "Awareness Programs",
            "Offline",
            "Campus Health Center",
            35,
            "Upcoming",
            120,
            departments["IT"],
            True,
            coordinator1,
            list(departments.values()),
        ),
    ]

    events = []
    for title, cat, etype, venue, offset, status, cap, pdept, cw, coord, targets in event_specs:
        ev = Event.query.filter_by(title=title).first()
        ev_date = today + timedelta(days=offset)
        if not ev:
            ev = Event(
                title=title,
                description=f"Official college {cat.lower()} hosted by {pdept.name}. Open for all eligible students to participate, learn, and collaborate.",
                category=cat,
                event_type=etype,
                venue=venue,
                event_date=ev_date,
                start_time=time(10, 0),
                end_time=time(13, 0),
                registration_start_date=ev_date - timedelta(days=20),
                registration_deadline=ev_date if status == "Completed" else ev_date - timedelta(days=1),
                capacity=cap,
                status=status,
                is_college_wide=cw,
                department=pdept,
                coordinator=coord,
            )
            ev.target_departments = targets
            db.session.add(ev)
        events.append(ev)
    db.session.flush()

    # 6. Seed Registrations, Attendance, and Feedback for Completed Events
    completed_events = [e for e in events if e.status == "Completed"]
    upcoming_events = [e for e in events if e.status == "Upcoming"]

    feedback_comments = [
        "Incredible session! The hands-on demonstrations were deeply engaging and well-structured.",
        "Excellent event organization and great speakers. Learned practical industry tools.",
        "Good workshop, but the lab was slightly crowded. Overall very valuable content.",
        "Loved the interactive coding hackathon! Highly motivating team experience.",
        "Very well organized and smooth venue setup. Looking forward to the next edition.",
        "Content was top-notch and cleared many advanced concepts. Keep hosting more such events!",
        "Engaging presentation, though the timeline felt slightly rushed at the end.",
    ]

    # For completed events: register students, mark attendance, add feedback
    for ev_idx, ev in enumerate(completed_events):
        for s_idx, student in enumerate(students):
            # Register most students for completed events
            if s_idx % (ev_idx + 2) == 0 or s_idx < 8:
                reg = Registration.query.filter_by(event=ev, student=student).first()
                if not reg:
                    reg = Registration(
                        event=ev,
                        student=student,
                        registered_at=datetime.utcnow() - timedelta(days=25 - ev_idx * 3),
                        status="Active",
                    )
                    db.session.add(reg)
                    db.session.flush()

                # Attendance: 75% Present, 15% Absent, 10% Excused
                if not reg.attendance:
                    att_status = "Present"
                    if s_idx % 7 == 0:
                        att_status = "Absent"
                    elif s_idx % 9 == 0:
                        att_status = "Excused"

                    db.session.add(
                        Attendance(
                            registration=reg,
                            status=att_status,
                            marked_by_id=ev.coordinator_id,
                            notes="Medical leave sanctioned" if att_status == "Excused" else None,
                            updated_at=datetime.utcnow() - timedelta(days=abs(offset) - 1),
                        )
                    )

                # Feedback: only for students marked Present
                if reg.attendance and reg.attendance.status == "Present" and not reg.feedback:
                    if s_idx % 2 == 0 or s_idx < 5:
                        satisfaction = 4 if s_idx % 3 != 0 else 5
                        comment = feedback_comments[(ev_idx + s_idx) % len(feedback_comments)]
                        db.session.add(
                            Feedback(
                                registration=reg,
                                satisfaction=satisfaction,
                                organization=4 + (s_idx % 2),
                                content_quality=5 if satisfaction == 5 else 4,
                                venue_rating=4,
                                comments=comment,
                                submitted_at=datetime.utcnow() - timedelta(days=abs(offset) - 2),
                            )
                        )

    # For upcoming events: register sample students
    for ev_idx, ev in enumerate(upcoming_events[:3]):
        for s_idx, student in enumerate(students[:6]):
            if (s_idx + ev_idx) % 2 == 0:
                reg = Registration.query.filter_by(event=ev, student=student).first()
                if not reg:
                    db.session.add(
                        Registration(
                            event=ev,
                            student=student,
                            registered_at=datetime.utcnow() - timedelta(days=2),
                            status="Active",
                        )
                    )

    # 7. Seed Sample In-App Notifications
    create_notification(
        title="Welcome to College Event Analytics Platform",
        message="System fully initialized with 9 engineering departments, sample events, attendance records, and performance analytics.",
        target_role="admin",
        category="general",
    )
    create_notification(
        title="Upcoming Fest: TARANG 2026",
        message="Registrations are now open for the Annual Cultural Fest TARANG 2026. Register early to secure your spot!",
        target_role="student",
        category="event",
    )
    create_notification(
        title="Registration Confirmed: National AI Summit",
        message="Your seat has been reserved. Check the event calendar for timing and venue details.",
        user_id=students[0].id,
        category="registration",
    )

    # 8. Seed Audit Log entries
    db.session.add(AuditLog(
        user_id=admin.id,
        action="SYSTEM_SEEDED",
        details="Initial system setup: 9 departments, 11 events, 12 students, attendance and feedback records.",
        ip_address="127.0.0.1",
    ))

    db.session.commit()
    return admin


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_demo_data()
    print("==================================================================")
    print("COLLEGE EVENT ANALYTICS SYSTEM: Database Seeded Successfully!")
    print("==================================================================")
    print("Nine Departments Seeded:")
    print("1. Civil Engineering (CIVIL)")
    print("2. Mechanical Engineering (MECH)")
    print("3. Information Technology (IT)")
    print("4. Software Engineering (SE)")
    print("5. Artificial Intelligence and Machine Learning (AIML)")
    print("6. Cybersecurity (CYS)")
    print("7. Master of Computer Applications (MCA)")
    print("8. Aeronautical Engineering (AERO)")
    print("9. Aerospace Engineering (AEROSP)")
    print("------------------------------------------------------------------")
    print("Administrator Account : admin@college.edu  / CampusDemo123!")
    print("                      : admin@example.com  / CampusDemo123!")
    print("Coordinator Account   : coordinator@college.edu / CampusDemo123!")
    print("                      : coordinator2@college.edu / CampusDemo123!")
    print("Student Accounts      : student@example.com  / CampusDemo123!")
    print("                      : student2@example.com / CampusDemo123!")
    print("                      : student3@example.com / CampusDemo123!")
    print("                      : student4@college.edu to student12@college.edu")
    print("==================================================================")

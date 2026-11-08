import re
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from app.extensions import db
from app.models import Department, User
from app.notifications.services import create_notification, log_action

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def is_safe_redirect_target(target):
    if not target:
        return False
    ref_url = urlparse(urljoin(request.host_url, target))
    return ref_url.scheme in ("http", "https") and ref_url.netloc == request.host


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Student and general portal login (supports Email or USN)."""
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        elif current_user.role == "student":
            return redirect(url_for("students.dashboard"))
        return redirect(url_for("index"))

    if request.method == "POST":
        # Support both 'email' and 'credential' form field names for full backward compatibility
        credential = (request.form.get("credential") or request.form.get("email") or "").strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            or_(User.email.ilike(credential), User.student_id == credential)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash("Your account has been deactivated. Please contact the administrator.", "danger")
                return render_template("auth/login.html")

            login_user(user)
            target = request.args.get("next")
            return redirect(target if is_safe_redirect_target(target) else url_for("index"))

        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    """Dedicated Admin & Coordinator Login."""
    if current_user.is_authenticated:
        if current_user.role in ("admin", "coordinator"):
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.role not in ("admin", "coordinator"):
                flash("Access restricted. This login is reserved for Administrators and Coordinators. Please use the Student Portal.", "danger")
                return render_template("auth/admin_login.html")
            if not user.is_active:
                flash("Your administrator account has been deactivated.", "danger")
                return render_template("auth/admin_login.html")

            login_user(user)
            log_action("ADMIN_LOGIN_SUCCESS", details=f"Admin {user.email} logged in", user=user)
            target = request.args.get("next")
            if target and is_safe_redirect_target(target):
                return redirect(target)
            return redirect(url_for("admin.dashboard"))

        flash("Invalid administrator email or password.", "danger")
    return render_template("auth/admin_login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Student Registration with USN, Phone, 9 Departments, and Year."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    departments = Department.query.order_by(Department.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        student_id = request.form.get("student_id", "").strip().upper()
        phone_number = request.form.get("phone_number", "").strip()
        academic_year = request.form.get("academic_year", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        department_id = request.form.get("department_id", type=int)

        department = db.session.get(Department, department_id) if department_id else None

        if not name or not student_id or not academic_year or not password:
            flash("Name, student ID (USN), academic year, email, and password are required.", "danger")
        elif confirm_password and password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif not department:
            flash("Select a valid department.", "danger")
        elif User.query.filter(User.email == email).first():
            flash("An account already uses that email address.", "danger")
        elif User.query.filter(User.student_id == student_id).first():
            flash("An account already uses that student ID / USN.", "danger")
        else:
            user = User(
                name=name,
                email=email,
                student_id=student_id,
                phone_number=phone_number or None,
                academic_year=academic_year,
                department=department,
                role="student",
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            # Welcome notification
            create_notification(
                title="Welcome to College Event Analytics",
                message=f"Welcome {name}! Your student account is now active. Explore upcoming events and register today.",
                user_id=user.id,
                category="general",
                link=url_for("events.listing"),
            )
            # Admin notification
            create_notification(
                title="New Student Registered",
                message=f"New student {name} ({student_id}) joined department {department.name}.",
                target_role="admin",
                category="registration",
            )
            db.session.commit()
            flash("Student account created successfully! You can now sign in with your email or USN.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", departments=departments)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    departments = Department.query.order_by(Department.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        department = db.session.get(Department, request.form.get("department_id", type=int))
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")

        if not name:
            flash("Name is required.", "danger")
        elif current_user.role == "student" and not department:
            flash("Select a valid department.", "danger")
        elif current_user.role == "student" and (
            not request.form.get("student_id", "").strip()
            or not request.form.get("academic_year", "").strip()
        ):
            flash("Student ID and academic year are required.", "danger")
        elif current_user.role == "student" and User.query.filter(
            User.student_id == request.form.get("student_id", "").strip().upper(),
            User.id != current_user.id,
        ).first():
            flash("That student ID belongs to another account.", "danger")
        elif new_password and (not current_password or not current_user.check_password(current_password)):
            flash("Enter your current password to change it.", "danger")
        elif new_password and len(new_password) < 8:
            flash("New password must be at least 8 characters.", "danger")
        else:
            current_user.name = name
            current_user.phone_number = phone_number or None
            if current_user.role == "student":
                current_user.department = department
                current_user.student_id = request.form.get("student_id", "").strip().upper()
                current_user.academic_year = request.form.get("academic_year", "").strip()
            if new_password:
                current_user.set_password(new_password)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", departments=departments)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("auth.login"))

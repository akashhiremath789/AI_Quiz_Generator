import re
from functools import wraps

import mysql.connector
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute, fetch_one

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def login_required(view):
    """Protect a route: redirect anonymous visitors to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = None
        if len(name) < 2 or len(name) > 100:
            error = "Enter your full name (2 to 100 characters)."
        elif not EMAIL_RE.match(email) or len(email) > 150:
            error = "Enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."

        if not error:
            try:
                if fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
                    error = "An account with this email already exists."
                else:
                    execute(
                        "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                        (name, email, generate_password_hash(password)),
                    )
                    flash("Account created. Please log in.", "success")
                    return redirect(url_for("auth.login"))
            except mysql.connector.Error:
                error = "Could not reach the database. Check your MySQL settings."

        flash(error, "error")
        return render_template("register.html", name=name, email=email)

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Enter your email and password.", "error")
            return render_template("login.html", email=email)

        try:
            user = fetch_one("SELECT id, name, password FROM users WHERE email = %s", (email,))
        except mysql.connector.Error:
            flash("Could not reach the database. Check your MySQL settings.", "error")
            return render_template("login.html", email=email)

        if user and check_password_hash(user["password"], password):
            session.clear()  # drop any old session data
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard.index"))

        flash("Incorrect email or password.", "error")
        return render_template("login.html", email=email)

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))

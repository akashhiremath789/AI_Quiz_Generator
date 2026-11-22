import mysql.connector
from flask import Blueprint, flash, render_template, session

from database import list_user_attempts, list_user_quizzes
from routes.auth import login_required

bp = Blueprint("history", __name__)


@bp.route("/my-quizzes")
@login_required
def my_quizzes():
    try:
        quizzes = list_user_quizzes(session["user_id"])
    except mysql.connector.Error:
        flash("Could not load your quizzes. Check the database connection.", "error")
        quizzes = []
    return render_template("history.html", view="quizzes", quizzes=quizzes, attempts=[])


@bp.route("/history")
@login_required
def history():
    try:
        attempts = list_user_attempts(session["user_id"])
    except mysql.connector.Error:
        flash("Could not load your history. Check the database connection.", "error")
        attempts = []
    return render_template("history.html", view="history", quizzes=[], attempts=attempts)

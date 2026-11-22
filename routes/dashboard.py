import mysql.connector
from flask import Blueprint, flash, render_template, session

from database import get_dashboard_stats, get_subject_averages, list_user_attempts
from routes.auth import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    user_id = session["user_id"]
    try:
        stats = get_dashboard_stats(user_id)
        recent = list_user_attempts(user_id, limit=5)
        trend = list(reversed(list_user_attempts(user_id, limit=10)))  # oldest -> newest for the chart
        subjects = get_subject_averages(user_id)
    except mysql.connector.Error:
        flash("Could not load your data. Check the database connection.", "error")
        stats, recent, trend, subjects = {"generated": 0, "attempted": 0, "avg_score": 0}, [], [], []

    chart_labels = [a["attempted_at"].strftime("%d %b") for a in trend]
    chart_scores = [a["percentage"] for a in trend]
    return render_template("dashboard.html", stats=stats, recent_attempts=recent,
                           chart_labels=chart_labels, chart_scores=chart_scores,
                           subject_labels=[x["subject"] for x in subjects],
                           subject_scores=[x["avg"] for x in subjects])

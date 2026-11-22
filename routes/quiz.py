import json
import secrets
import uuid

import mysql.connector
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from werkzeug.utils import secure_filename

from database import (create_quiz, get_attempt_review, get_quiz_questions, get_user_attempt,
                      get_user_quiz, save_attempt)
from routes.auth import login_required
from services.gemini_service import GeminiError, generate_questions
from services.pdf_service import PDFError, extract_text, validate_upload

ALLOWED_COUNTS = (5, 10, 15)
ALLOWED_DIFFICULTY = ("Easy", "Medium", "Hard")

bp = Blueprint("quiz", __name__)


@bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    if request.method == "GET":
        return render_template("generate_quiz.html")

    subject = request.form.get("subject", "").strip()
    topic = request.form.get("topic", "").strip()
    difficulty = request.form.get("difficulty", "")
    try:
        count = int(request.form.get("num_questions", ""))
    except ValueError:
        count = 0

    error = None
    if not subject or len(subject) > 100:
        error = "Enter a subject (up to 100 characters)."
    elif not topic or len(topic) > 150:
        error = "Enter a topic (up to 150 characters)."
    elif count not in ALLOWED_COUNTS:
        error = "Choose 5, 10 or 15 questions."
    elif difficulty not in ALLOWED_DIFFICULTY:
        error = "Choose Easy, Medium or Hard."

    form = {"subject": subject, "topic": topic, "num_questions": count or 5,
            "difficulty": difficulty or "Medium"}
    if error:
        flash(error, "error")
        return render_template("generate_quiz.html", form=form)

    try:
        questions = generate_questions(count, difficulty, subject=subject, topic=topic)
        quiz_id = create_quiz(session["user_id"], f"{subject}: {topic}", subject, topic,
                              difficulty, "topic", questions)
    except GeminiError as exc:
        flash(str(exc), "error")
        return render_template("generate_quiz.html", form=form)
    except mysql.connector.Error:
        current_app.logger.exception("Could not save quiz")
        flash("Could not save the quiz. Check the database connection.", "error")
        return render_template("generate_quiz.html", form=form)

    flash(f"Quiz ready with {count} questions.", "success")
    return redirect(url_for("quiz.take", quiz_id=quiz_id))


@bp.route("/upload-pdf", methods=["GET", "POST"])
@login_required
def upload_pdf():
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if request.method == "GET":
        return render_template("upload_pdf.html", max_mb=max_mb)

    title = request.form.get("title", "").strip()[:100]
    difficulty = request.form.get("difficulty", "")
    try:
        count = int(request.form.get("num_questions", ""))
    except ValueError:
        count = 0

    if count not in ALLOWED_COUNTS:
        flash("Choose 5, 10 or 15 questions.", "error")
        return render_template("upload_pdf.html", max_mb=max_mb)
    if difficulty not in ALLOWED_DIFFICULTY:
        flash("Choose Easy, Medium or Hard.", "error")
        return render_template("upload_pdf.html", max_mb=max_mb)

    uploaded = request.files.get("pdf_file")
    try:
        pdf_bytes = validate_upload(uploaded, max_mb)
        text = extract_text(pdf_bytes)
        file_label = secure_filename(uploaded.filename)[:150] or "document.pdf"
        quiz_title = title or file_label.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        questions = generate_questions(count, difficulty, source_text=text)
        quiz_id = create_quiz(session["user_id"], quiz_title[:200], quiz_title[:100], file_label,
                              difficulty, "pdf", questions)
    except (PDFError, GeminiError) as exc:
        flash(str(exc), "error")
        return render_template("upload_pdf.html", max_mb=max_mb)
    except mysql.connector.Error:
        current_app.logger.exception("Could not save quiz")
        flash("Could not save the quiz. Check the database connection.", "error")
        return render_template("upload_pdf.html", max_mb=max_mb)

    flash(f"Quiz ready with {count} questions from your PDF.", "success")
    return redirect(url_for("quiz.take", quiz_id=quiz_id))


@bp.route("/quiz/<int:quiz_id>")
@login_required
def take(quiz_id):
    try:
        quiz = get_user_quiz(quiz_id, session["user_id"])  # only the owner can open a quiz
        if not quiz:
            flash("Quiz not found.", "error")
            return redirect(url_for("history.my_quizzes"))
        questions = get_quiz_questions(quiz_id)  # correct answers are NOT sent to the browser
    except mysql.connector.Error:
        current_app.logger.exception("Could not load quiz")
        flash("Could not load the quiz. Check the database connection.", "error")
        return redirect(url_for("history.my_quizzes"))

    if not questions:
        flash("This quiz has no questions.", "error")
        return redirect(url_for("history.my_quizzes"))

    token = uuid.uuid4().hex  # single-use token: a quiz page can be submitted only once
    session[f"quiz_token_{quiz_id}"] = token
    return render_template("take_quiz.html", quiz=quiz, questions=questions,
                           time_limit=len(questions) * 60, token=token)


@bp.route("/quiz/<int:quiz_id>/submit", methods=["POST"])
@login_required
def submit(quiz_id):
    user_id = session["user_id"]

    expected = session.pop(f"quiz_token_{quiz_id}", None)  # consumed here, so a repeat POST is rejected
    if not expected or not secrets.compare_digest(expected, request.form.get("token", "")):
        flash("This quiz was already submitted or has expired.", "info")
        return redirect(url_for("history.history"))

    try:
        answers = json.loads(request.form.get("answers", "{}"))
        if not isinstance(answers, dict):
            answers = {}
    except ValueError:
        answers = {}
    try:
        time_taken = min(max(int(request.form.get("time_taken", 0)), 0), 24 * 3600)
    except ValueError:
        time_taken = 0

    try:
        quiz = get_user_quiz(quiz_id, user_id)
        if not quiz:
            flash("Quiz not found.", "error")
            return redirect(url_for("history.my_quizzes"))
        questions = get_quiz_questions(quiz_id, include_answers=True)

        rows, score = [], 0
        for q in questions:
            selected = answers.get(str(q["id"]))
            selected = selected if selected in ("A", "B", "C", "D") else None
            correct = selected is not None and selected == q["correct_answer"]
            score += 1 if correct else 0
            rows.append((q["id"], selected, correct))

        total = len(questions)
        percentage = round(score / total * 100, 2) if total else 0
        attempt_id = save_attempt(user_id, quiz_id, score, total, percentage, time_taken, rows)
    except mysql.connector.Error:
        current_app.logger.exception("Could not save attempt")
        flash("Could not save your result. Please try again.", "error")
        return redirect(url_for("quiz.take", quiz_id=quiz_id))

    return redirect(url_for("quiz.result", attempt_id=attempt_id))


@bp.route("/result/<int:attempt_id>")
@login_required
def result(attempt_id):
    try:
        attempt = get_user_attempt(attempt_id, session["user_id"])  # only the owner can view it
        if not attempt:
            flash("Result not found.", "error")
            return redirect(url_for("history.history"))
        review = get_attempt_review(attempt_id)
    except mysql.connector.Error:
        current_app.logger.exception("Could not load result")
        flash("Could not load the result. Check the database connection.", "error")
        return redirect(url_for("history.history"))

    answered = sum(1 for r in review if r["selected_answer"])
    stats = {"correct": attempt["score"], "unanswered": len(review) - answered,
             "incorrect": answered - attempt["score"]}
    return render_template("result.html", attempt=attempt, review=review, stats=stats)

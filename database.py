"""MySQL helpers. One connection per request, stored on flask.g.
All queries use %s placeholders (parameterized) to prevent SQL injection."""
import mysql.connector
from flask import g, current_app


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = mysql.connector.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            autocommit=False,
        )
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def fetch_one(sql, params=()):
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def fetch_all(sql, params=()):
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def execute(sql, params=()):
    """Run INSERT/UPDATE/DELETE, commit, return lastrowid."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(sql, params)
        db.commit()
        return cur.lastrowid
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def init_app(app):
    app.teardown_appcontext(close_db)


# =====================================================================
# Data-access functions used by the routes.
# Every function that reads a quiz or attempt takes user_id so a student
# can only ever reach their own data.
# =====================================================================

def format_duration(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _clean_percentage(value):
    value = round(float(value), 1)
    return int(value) if value == int(value) else value


def _prepare_attempt(row):
    row["percentage"] = _clean_percentage(row["percentage"])
    row["time_display"] = format_duration(row["time_taken"])
    return row


# ---------- Quizzes ----------

def create_quiz(user_id, title, subject, topic, difficulty, source_type, questions):
    """Save a quiz and all its questions in ONE transaction. Returns the quiz id.
    `questions` is a list of dicts: question_text, option_a..option_d, correct_answer, explanation."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO quizzes (user_id, title, subject, topic, difficulty, source_type, total_questions) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, title, subject, topic, difficulty, source_type, len(questions)),
        )
        quiz_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, "
            "correct_answer, explanation) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [(quiz_id, q["question_text"], q["option_a"], q["option_b"], q["option_c"], q["option_d"],
              q["correct_answer"], q["explanation"]) for q in questions],
        )
        db.commit()
        return quiz_id
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def get_user_quiz(quiz_id, user_id):
    """Returns the quiz only if it belongs to this user, otherwise None."""
    return fetch_one("SELECT * FROM quizzes WHERE id = %s AND user_id = %s", (quiz_id, user_id))


def get_quiz_questions(quiz_id, include_answers=False):
    """Questions for taking a quiz do NOT include the correct answer or explanation."""
    columns = "id, question_text, option_a, option_b, option_c, option_d"
    if include_answers:
        columns += ", correct_answer, explanation"
    return fetch_all(f"SELECT {columns} FROM questions WHERE quiz_id = %s ORDER BY id", (quiz_id,))


def list_user_quizzes(user_id):
    return fetch_all(
        "SELECT q.*, (SELECT COUNT(*) FROM quiz_attempts a WHERE a.quiz_id = q.id) AS attempts "
        "FROM quizzes q WHERE q.user_id = %s ORDER BY q.created_at DESC, q.id DESC",
        (user_id,),
    )


# ---------- Attempts ----------

def save_attempt(user_id, quiz_id, score, total, percentage, time_taken, answer_rows):
    """Save an attempt and its per-question answers in ONE transaction. Returns the attempt id.
    `answer_rows` is a list of (question_id, selected_answer_or_None, is_correct)."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO quiz_attempts (user_id, quiz_id, score, total_questions, percentage, time_taken) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, quiz_id, score, total, percentage, time_taken),
        )
        attempt_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO user_answers (attempt_id, question_id, selected_answer, is_correct) "
            "VALUES (%s, %s, %s, %s)",
            [(attempt_id, qid, sel, 1 if ok else 0) for qid, sel, ok in answer_rows],
        )
        db.commit()
        return attempt_id
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def list_user_attempts(user_id, limit=None):
    sql = (
        "SELECT a.id, a.quiz_id, a.score, a.total_questions, a.percentage, a.time_taken, a.attempted_at, "
        "q.title, q.subject, q.difficulty "
        "FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id "
        "WHERE a.user_id = %s ORDER BY a.attempted_at DESC, a.id DESC"
    )
    params = [user_id]
    if limit:
        sql += " LIMIT %s"
        params.append(int(limit))
    return [_prepare_attempt(r) for r in fetch_all(sql, tuple(params))]


def get_user_attempt(attempt_id, user_id):
    """Returns the attempt only if it belongs to this user, otherwise None."""
    row = fetch_one(
        "SELECT a.id, a.quiz_id, a.score, a.total_questions, a.percentage, a.time_taken, a.attempted_at, "
        "q.title, q.subject, q.difficulty "
        "FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id "
        "WHERE a.id = %s AND a.user_id = %s",
        (attempt_id, user_id),
    )
    return _prepare_attempt(row) if row else None


def get_attempt_review(attempt_id):
    """Questions with the student's answer, for the result page (only call after ownership is checked)."""
    rows = fetch_all(
        "SELECT qu.id, qu.question_text, qu.option_a, qu.option_b, qu.option_c, qu.option_d, "
        "qu.correct_answer, qu.explanation, ua.selected_answer, ua.is_correct "
        "FROM user_answers ua JOIN questions qu ON qu.id = ua.question_id "
        "WHERE ua.attempt_id = %s ORDER BY qu.id",
        (attempt_id,),
    )
    for r in rows:
        r["is_correct"] = bool(r["is_correct"])
    return rows


# ---------- Dashboard ----------

def get_dashboard_stats(user_id):
    generated = fetch_one("SELECT COUNT(*) AS n FROM quizzes WHERE user_id = %s", (user_id,))["n"]
    row = fetch_one(
        "SELECT COUNT(*) AS n, AVG(percentage) AS avg_pct FROM quiz_attempts WHERE user_id = %s",
        (user_id,),
    )
    avg = _clean_percentage(row["avg_pct"]) if row["avg_pct"] is not None else 0
    return {"generated": generated, "attempted": row["n"], "avg_score": avg}


def get_subject_averages(user_id, limit=6):
    """Average score per subject, for the dashboard bar chart."""
    rows = fetch_all(
        "SELECT q.subject, AVG(a.percentage) AS avg_pct, COUNT(*) AS attempts "
        "FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id "
        "WHERE a.user_id = %s GROUP BY q.subject ORDER BY attempts DESC, q.subject LIMIT %s",
        (user_id, int(limit)),
    )
    return [{"subject": r["subject"], "avg": _clean_percentage(r["avg_pct"]), "attempts": r["attempts"]} for r in rows]

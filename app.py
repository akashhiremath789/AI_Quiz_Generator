import secrets

from flask import Flask, abort, flash, redirect, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge

import database
from config import Config
from routes import auth, dashboard, history, quiz


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    database.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(quiz.bp)
    app.register_blueprint(history.bp)

    # ---- CSRF protection: every POST must carry the token stored in the session
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not secrets.compare_digest(sent, expected):
                abort(400)

    @app.errorhandler(400)
    def bad_request(_):
        flash("Your session expired. Please try again.", "error")
        return redirect(url_for("home"))

    @app.route("/")
    def home():
        if session.get("user_id"):
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_):
        flash("That file is too large. Please upload a smaller PDF.", "error")
        return redirect(url_for("quiz.upload_pdf"))

    @app.errorhandler(404)
    def not_found(_):
        flash("That page does not exist.", "error")
        return redirect(url_for("home"))

    @app.errorhandler(500)
    def server_error(_):
        flash("Something went wrong on our side. Please try again.", "error")
        return redirect(url_for("home"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

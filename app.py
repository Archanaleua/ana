"""
ANA — Think. Learn. Assist.
Flask application entrypoint.
"""
import os
import sys
from flask import Flask, render_template, session, redirect, request
from dotenv import load_dotenv
from services.auth_utils import login_required
from datetime import timedelta

load_dotenv()

try:
    from routes.auth import auth_bp
    from routes.chat import chat_bp
    from routes.documents import documents_bp
    from routes.api import api_bp
except Exception as exc:
    print("\n[ANA STARTUP ERROR] Failed to import a blueprint.", file=sys.stderr)
    print(f"  Reason: {exc}\n", file=sys.stderr)
    print("  Check routes/*.py and services/*.py for import-time errors", file=sys.stderr)
    print("  (e.g. a client being constructed with a missing API key).\n", file=sys.stderr)
    raise

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    if app.config["SECRET_KEY"] == "change-me-in-production":
        print("[ANA WARNING] FLASK_SECRET_KEY not set in .env — using insecure default.", file=sys.stderr)

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(documents_bp, url_prefix="/documents")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Pages
    @app.route("/")
    def landing():
        # if already logged in, skip landing and go straight to workspace
        if session.get("user_id"):
            return redirect("/app")
        return render_template("landing.html")

    @app.route("/start")
    def start():
        # landing page input submits here with ?q=their question
        q = request.args.get("q", "").strip()
        if session.get("user_id"):
            # already logged in — go to workspace with question in URL
            if q:
                return redirect(f"/app?q={q}")
            return redirect("/app")
        # not logged in — go to signup, save question in session
        if q:
            session["pending_q"] = q
        return redirect("/auth/signup")

    @app.route("/profile")
    @login_required
    def profile():
        return render_template("profile.html")

    @app.route("/settings")
    @login_required
    def settings():
        return render_template("settings.html")
    
    @app.route("/app")
    @login_required
    def workspace():
        # pick up any pending question from landing page
        pending_q = session.pop("pending_q", None)
        q = request.args.get("q", pending_q or "")
        return render_template(
            "app.html",
            user_id=session.get("user_id"),
            user_email=session.get("email"),
            pending_q=q,
        )
    
    @app.route("/share/<share_id>")
    def shared_chat(share_id):
        return render_template(
        "shared_chat.html",
        share_id=share_id
        )


    @app.errorhandler(404)
    def not_found(_):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception(e)
        return render_template("404.html"), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
        threaded=True,
    )



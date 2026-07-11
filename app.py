"""
ANA — Think. Learn. Assist.
Flask application entrypoint.
"""
import os
import sys
import subprocess
import atexit
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


_mcp_process = None


def _start_mcp_server():
    """
    Auto-launch the MCP server (mcp_server/hr_server.py) as a background
    process alongside Flask, so you never have to start it manually again.

    Guarded against Flask's debug reloader, which restarts this whole file
    in a child process — without the guard you'd end up with two MCP
    servers both trying to bind port 8000.
    """
    global _mcp_process

    # In debug mode, Flask's reloader runs this script twice: once as the
    # parent "monitor" process, once as the actual child server process.
    # WERKZEUG_RUN_MAIN is only set inside that child process, so we use it
    # to make sure we only ever start the MCP server once.
    is_reloader_active = os.getenv("FLASK_DEBUG", "1") == "1"
    if is_reloader_active and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    project_root = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(project_root, "mcp_server", "hr_server.py")
    if not os.path.exists(server_path):
        print(f"[ANA WARNING] MCP server file not found at {server_path} — HR tools will be unavailable.", file=sys.stderr)
        return

    # Run as a module (`python -m mcp_server.hr_server`), not as a bare script.
    # Running it as a script only puts the mcp_server/ folder on sys.path, so
    # `from services.xxx import ...` inside hr_server.py fails with
    # ModuleNotFoundError: No module named 'services'. Running as a module
    # from the project root puts the project root on sys.path instead, which
    # is what hr_server.py's imports actually expect.
    print(f"[ANA] Starting MCP server: python -m mcp_server.hr_server (cwd={project_root})")
    creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    _mcp_process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.hr_server"],
        cwd=project_root,
        creationflags=creationflags,
    )

    def _stop_mcp_server():
        if _mcp_process and _mcp_process.poll() is None:
            print("[ANA] Stopping MCP server...")
            _mcp_process.terminate()

    atexit.register(_stop_mcp_server)


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

app = create_app()

if __name__ == "__main__":
    _start_mcp_server()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
        threaded=True,
    )
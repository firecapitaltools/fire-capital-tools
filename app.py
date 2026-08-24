"""
FIRE Capital Tools — Flask Application
"""

from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config
from models import User

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Create uploads folder ──────────────────────────────────────────────
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────────────
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"          # type: ignore[assignment]
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    csrf.init_app(app)

    def wants_json_session_response() -> bool:
        return (
            request.path.startswith("/tools/mmr-summary/upload")
            or request.path.startswith("/tools/mmr-summary/download/")
            or request.path.startswith("/tools/fire-metrics/download-latest")
            or request.path.startswith("/tools/fire-metrics/export/city-analytics")
            or request.path.startswith("/tools/fire-metrics/search")
            or request.path.startswith("/tools/fire-metrics/refresh-status")
            or request.path.startswith("/tools/scorecard-pro/upload")
            or request.path.startswith("/tools/scorecard-pro/analysis/")
            or request.path.startswith("/tools/scorecard-pro/download/")
            or request.accept_mimetypes.best == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )

    def session_expired_response():
        return jsonify({"error": "session_expired", "redirect": url_for("auth.login")}), 401

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if wants_json_session_response():
            return session_expired_response()
        flash(login_manager.login_message, login_manager.login_message_category)
        return redirect(url_for("auth.login", next=request.full_path if request.query_string else request.path))

    # ── User loader ────────────────────────────────────────────────────────
    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return User.get_by_id(user_id, app.config)

    @app.context_processor
    def inject_user_permissions():
        can_access_admin = (
            current_user.is_authenticated
            and User.matches_admin_user(current_user.get_id() or "", app.config)
        )
        return {"can_access_admin": can_access_admin}

    # ── Blueprints ─────────────────────────────────────────────────────────
    from auth import auth_bp
    from tools.admin import admin_bp
    from tools.deal_analyzer import deal_analyzer_bp
    from tools.deal_dive import deal_dive_bp
    from tools.feedback import feedback_bp
    from tools.fire_metrics import fire_metrics_bp
    from tools.mmr_summary import mmr_bp
    from tools.rent_comps import rent_comps_bp
    from tools.scorecard_pro import scorecard_bp
    from tools.site_dd import site_dd_bp
    from tools.investor_notes import investor_notes_bp
    from tools.investor_report import investor_report_bp
    from tools.underwriting import underwriting_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(mmr_bp, url_prefix="/tools/mmr-summary")
    app.register_blueprint(fire_metrics_bp, url_prefix="/tools/fire-metrics")
    app.register_blueprint(scorecard_bp, url_prefix="/tools/scorecard-pro")
    app.register_blueprint(deal_dive_bp, url_prefix="/tools/deal-dive")
    app.register_blueprint(rent_comps_bp, url_prefix="/tools/rent-comps")
    app.register_blueprint(deal_analyzer_bp, url_prefix="/tools/deal-analyzer")
    app.register_blueprint(site_dd_bp, url_prefix="/tools/site-dd")
    app.register_blueprint(underwriting_bp, url_prefix="/tools/underwriting")
    app.register_blueprint(investor_report_bp, url_prefix="/tools/investor-report")
    # The notetaker shares Investor Report's prefix: it is a feature of
    # that tool, not a tool of its own.
    app.register_blueprint(investor_notes_bp, url_prefix="/tools/investor-report")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(feedback_bp, url_prefix="/feedback")

    # ── Stale-form defence ─────────────────────────────────────────────────
    #
    # THREE PAGES, NAMED ONE BY ONE, BECAUSE THE BLAST RADIUS IS SPECIFIC
    #
    # These render forms that POST to a FULL-COLLECTION-REWRITE handler:
    # the form carries the whole set and the handler replaces the whole
    # set, so submitting a render that predates an item can erase it.
    # Site DD's `_collect()` now treats an absent field as "unchanged",
    # which fixes the erasure itself; this narrows the window in which a
    # stale render is offered to the user at all.
    #
    #   site_dd.area_detail    -> save_area
    #   site_dd.room_detail    -> save_room
    #   underwriting.detail    -> save_expenses / save_capex / save_loans
    #
    # `no-store` specifically, not `no-cache`: `no-cache` still permits the
    # browser's back/forward cache to restore the page, which is the path
    # that produces a stale render in the first place.
    #
    # DELIBERATELY NOT APPLIED BROADLY. Static assets keep their caching or
    # the PWA stops being installable, and the service worker shell is
    # untouched -- it already bypasses /tools/ and caches no authenticated
    # route. Read-only tool pages are not listed either: re-reading a stale
    # report costs nothing, and blanket no-store would make every page a
    # fresh round trip for a fleet that works on bad connections.
    #
    # A mitigation, not the fix. It does nothing about two tabs or two
    # devices, which is why the _collect() change is the real defence.
    STALE_FORM_ENDPOINTS = frozenset({
        "site_dd.area_detail",
        "site_dd.room_detail",
        "underwriting.detail",
    })

    @app.after_request
    def no_store_on_editable_forms(response):
        if request.endpoint in STALE_FORM_ENDPOINTS:
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    # ── Security headers ───────────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["X-XSS-Protection"]       = "1; mode=block"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if wants_json_session_response():
            return session_expired_response()
        flash("Your session expired. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    # ── Session inactivity timeout ────────────────────────────────────────
    @app.before_request
    def check_session_timeout():
        if not current_user.is_authenticated:
            return
        session.permanent = True
        last: str | None = session.get("_last_active")
        if last:
            elapsed = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds()
            if elapsed > app.permanent_session_lifetime.total_seconds():
                logout_user()
                session.clear()
                if wants_json_session_response():
                    return session_expired_response()
                flash("Your session expired. Please log in again.", "warning")
                return redirect(url_for("auth.login"))
        session["_last_active"] = datetime.utcnow().isoformat()
        session.modified = True

    # ── PWA routes (root-level so service worker scope covers all of /) ────
    @app.route("/service-worker.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "service-worker.js")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Content-Type"] = "application/javascript"
        return response

    @app.route("/manifest.json")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.json",
                                   mimetype="application/manifest+json")

    # ── Core routes ────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    def dashboard():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return render_template("dashboard.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        debug=app.config.get("DEBUG", False),
        host="0.0.0.0",
        port=5000,
    )

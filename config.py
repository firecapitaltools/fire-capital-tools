import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Security ───────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-change-before-deploy")
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 4 * 60 * 60   # 4-hour CSRF token validity
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    # Marks the session cookie Secure so the browser will only ever send it
    # over HTTPS. Railway terminates TLS at the edge and 301s HTTP->HTTPS,
    # so in production there is no plaintext leg for the cookie to travel
    # on and this costs nothing.
    #
    # Env-gated rather than hardcoded True because local development runs
    # over http://localhost, where a Secure cookie is simply never sent
    # back -- which presents as "login silently does nothing", one of the
    # more confusing failure modes to debug. Defaults false so a developer
    # who has not set anything keeps a working login; production opts in
    # by setting SESSION_COOKIE_SECURE=true.
    SESSION_COOKIE_SECURE: bool = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # ── Session ────────────────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=4)
    SESSION_PERMANENT: bool = True

    # ── Runtime ────────────────────────────────────────────────────────────
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    TEMPLATES_AUTO_RELOAD: bool = True
    GOOGLE_MAPS_API_KEY: str = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    GOOGLE_MAPS_MAP_ID: str = os.environ.get("GOOGLE_MAPS_MAP_ID", "")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    FIRE_METRICS_SUMMARY_MODEL: str = os.environ.get("FIRE_METRICS_SUMMARY_MODEL", "")
    FIRE_METRICS_CRE_MODEL: str = os.environ.get("FIRE_METRICS_CRE_MODEL", "gpt-4.1-mini")
    FIRE_METRICS_AI_SUMMARIES_ENABLED: bool = os.environ.get("FIRE_METRICS_AI_SUMMARIES_ENABLED", "true").lower() == "true"

    # ── File uploads ───────────────────────────────────────────────────────
    # Env-var-overridable with a repo-relative fallback, the same shape as
    # USER_STORE_PATH below and every *_DB_PATH in tools/. On Railway this
    # must point at the persistent volume: the container filesystem is
    # ephemeral, so anything written under the repo is destroyed on each
    # deploy. Deal Dive is the reason this matters -- its uploads are
    # tracked in deal_files and downloadable indefinitely, unlike Scorecard
    # Pro's and MMR's, which are session scratch on a 4-hour TTL.
    UPLOAD_FOLDER: str = os.environ.get(
        "UPLOAD_FOLDER_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"),
    )
    # Raised from 20 MB for Site DD video (30s at 720p runs 25-40 MB).
    #
    # Raising this alone would have removed the only size guard from every
    # other upload endpoint in the app, which had been protected by it as
    # a side effect rather than by any deliberate per-endpoint limit. So
    # tools/upload_limits.py now gives each endpoint its own explicit cap
    # at the value it effectively had before, and this figure is only the
    # backstop for the largest single thing the app accepts.
    MAX_CONTENT_LENGTH: int = 48 * 1024 * 1024   # 48 MB

    # ── Admin credentials (loaded from .env) ──────────────────────────────
    ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "michelle")
    ADMIN_PASSWORD_HASH: str = os.environ.get("ADMIN_PASSWORD_HASH", "")
    # THE FALLBACK IS NAMED SO THE APP CAN TELL IT APART FROM A CHOICE.
    #
    # `os.environ.get(NAME, fallback)` collapses "the operator set this"
    # and "nobody set this" into one string, so any check reading
    # app.config can only ever see a path and never see whether anyone
    # chose it. That defeated the first version of this guard: it read
    # app.config, found a value, and reported the store configured on a
    # production box where the variable is not set at all.
    #
    # Exporting the default lets `User.user_store_is_configured()` ask the
    # real question -- is this path the one nobody picked?
    DEFAULT_USER_STORE_PATH: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "users.json")
    USER_STORE_PATH: str = os.environ.get(
        "USER_STORE_PATH", DEFAULT_USER_STORE_PATH)

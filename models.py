import json
import os
import tempfile
from datetime import datetime
from typing import Any

import bcrypt
from flask_login import UserMixin


class User(UserMixin):
    """Website user backed by the .env admin plus a local signup user store."""

    def __init__(self, username: str) -> None:
        self.id = username

    def get_id(self) -> str:
        return self.id

    @staticmethod
    def verify(username: str, password: str, app_config: dict) -> "User | None":
        """
        Check supplied credentials against signup users first, then the configured
        admin account. Returns a User on success, None on failure.
        """
        stored_user = User.find_stored_user(username, app_config)
        if stored_user and User._check_password(password, stored_user.get("password_hash", "")):
            return User(User.clean_config_value(stored_user.get("username", username)))

        admin_username = User.admin_username(app_config)
        if User.normalize_username(username) != User.normalize_username(admin_username):
            return None
        stored_hash = User.clean_config_value(app_config.get("ADMIN_PASSWORD_HASH", ""))
        if User._check_password(password, stored_hash):
            return User(admin_username)
        return None

    @staticmethod
    def get_by_id(user_id: str, app_config: dict) -> "User | None":
        stored_user = User.find_stored_user(user_id, app_config)
        if stored_user:
            return User(User.clean_config_value(stored_user.get("username", user_id)))
        if User.matches_admin_user(user_id, app_config):
            return User(User.admin_username(app_config))
        return None

    @staticmethod
    def create(username: str, password: str, app_config: dict) -> "User":
        clean_username = User.clean_config_value(username)
        normalized = User.normalize_username(clean_username)
        if not clean_username or not normalized:
            raise ValueError("Username is required.")
        # REFUSED RATHER THAN WRITTEN SOMEWHERE TEMPORARY.
        #
        # Creating the account would appear to succeed and would log the
        # user straight in, so the loss would surface days later as "my
        # password stopped working" rather than as an error anyone could
        # connect to a deploy. A named refusal now is cheaper than that.
        warning = User.user_store_warning(app_config)
        if warning:
            raise ValueError(warning)
        if User.get_by_id(clean_username, app_config):
            raise ValueError("Username already exists.")

        store = User._load_store(app_config)
        users = store.setdefault("users", {})
        users[normalized] = {
            "username": clean_username,
            "password_hash": User.hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
        }
        User._write_store(store, app_config)
        return User(clean_username)

    @staticmethod
    def update_password(username: str, new_password: str, app_config: dict) -> bool:
        normalized = User.normalize_username(username)
        store = User._load_store(app_config)
        users = store.setdefault("users", {})
        user = users.get(normalized)
        if not isinstance(user, dict):
            return False
        user["password_hash"] = User.hash_password(new_password)
        user["updated_at"] = datetime.utcnow().isoformat()
        User._write_store(store, app_config)
        return True

    @staticmethod
    def is_stored_user(username: str, app_config: dict) -> bool:
        return User.find_stored_user(username, app_config) is not None

    @staticmethod
    def find_stored_user(username: str, app_config: dict) -> dict[str, Any] | None:
        normalized = User.normalize_username(username)
        if not normalized:
            return None
        users = User._load_store(app_config).get("users", {})
        if not isinstance(users, dict):
            return None
        user = users.get(normalized)
        return user if isinstance(user, dict) else None

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def clean_config_value(value) -> str:
        return str(value or "").strip().strip('"').strip("'").strip()

    @staticmethod
    def admin_username(app_config: dict) -> str:
        return User.clean_config_value(app_config.get("ADMIN_USERNAME", ""))

    @staticmethod
    def normalize_username(username: str) -> str:
        return User.clean_config_value(username).casefold()

    @staticmethod
    def matches_configured_user(user_id: str, app_config: dict) -> bool:
        return User.get_by_id(user_id, app_config) is not None

    @staticmethod
    def matches_admin_user(user_id: str, app_config: dict) -> bool:
        return User.normalize_username(user_id) == User.normalize_username(User.admin_username(app_config))

    @staticmethod
    def user_store_path(app_config: dict) -> str:
        """Where signup accounts live.

        THE FALLBACK IS NOT A SAFE DEFAULT AND MUST NOT BE USED SILENTLY

        Twelve `*_DB_PATH` variables are set in production and every one
        points at the `/data` volume. `USER_STORE_PATH` was not among them,
        so this fell back to `users.json` beside the source file — on
        Railway that is the **container filesystem**, which is replaced on
        every deploy. The first person to sign up would have lost their
        account at the next push, with no error and nothing in the logs.

        It cost nothing only because there are zero signup users: every
        login is the env-configured admin, which does not touch this file.

        The path itself still resolves, because login and lookup must keep
        working either way. What changed is that WRITING is refused when
        the variable is unset -- see `user_store_is_configured()` -- so the
        unset state produces a named failure rather than a silent write to
        somewhere temporary. Standing rule 1: demonstrate both failure
        states, not just the good one.
        """
        configured_path = User.clean_config_value(app_config.get("USER_STORE_PATH", ""))
        if configured_path:
            return os.path.abspath(configured_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

    @staticmethod
    def user_store_is_configured(app_config: dict) -> bool:
        """True when USER_STORE_PATH names a location on purpose.

        The app cannot tell whether an unconfigured fallback persists --
        in a checkout it does, in a container it does not -- so it does not
        guess. Unset means unknown, and unknown is not good enough to
        write an account to.
        """
        return bool(User.clean_config_value(app_config.get("USER_STORE_PATH", "")))

    @staticmethod
    def user_store_warning(app_config: dict) -> str | None:
        """The banner text when the store has nowhere durable to live."""
        if User.user_store_is_configured(app_config):
            return None
        return ("USER_STORE_PATH is not set. New accounts cannot be created, "
                "because there is nowhere durable to store them — on Railway "
                "the default path is the container filesystem and is erased "
                "on every deploy. Set USER_STORE_PATH to a file on the /data "
                "volume, for example /data/users.json.")

    @staticmethod
    def _check_password(password: str, stored_hash: str) -> bool:
        stored_hash = User.clean_config_value(stored_hash)
        if not stored_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def _load_store(app_config: dict) -> dict[str, Any]:
        path = User.user_store_path(app_config)
        if not os.path.exists(path):
            return {"users": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"users": {}}
        if not isinstance(data, dict):
            return {"users": {}}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data

    @staticmethod
    def _write_store(store: dict[str, Any], app_config: dict) -> None:
        path = User.user_store_path(app_config)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory or None, delete=False) as tmp:
            json.dump(store, tmp, indent=2)
            tmp.write("\n")
            tmp_path = tmp.name
        os.replace(tmp_path, path)

"""The user store must not fall back silently to somewhere temporary.

WHAT WAS WRONG

`User.user_store_path()` reads `USER_STORE_PATH` and falls back to
`users.json` beside the source file. Twelve `*_DB_PATH` variables are set
in production and every one points at the `/data` volume; this one was not
among them. On Railway the fallback is the **container filesystem**, which
is replaced on every deploy.

So the first person to sign up would have had their account accepted, been
logged straight in, and lost the account at the next push — with no error,
nothing in the logs, and no way to connect the loss to a deploy. It would
have surfaced days later as "my password stopped working".

It cost nothing only because there are zero signup users: every login is
the env-configured admin, which never touches this file. **That is why it
was worth fixing now — there is no data to migrate.**

STANDING RULE 1, INCLUDING THE PART THE PART-47 QUOTATION DROPPED

    "Every persistent DB path: env-var-with-fallback, verified via live
     in-process code, never trust the Railway dashboard. Any new
     *_DB_PATH must demonstrate BOTH failure states (unset → visible red
     banner naming the var) and success, not just the good one."

Both states are demonstrated below. The app does not guess whether an
unconfigured fallback persists — in a checkout it does, in a container it
does not — so unset means unknown, and unknown is not good enough to write
an account to.
"""

import json
import tempfile
import unittest
from pathlib import Path

from app import app
from models import User


def config_without():
    cfg = dict(app.config)
    cfg.pop("USER_STORE_PATH", None)
    return cfg


def config_with(path):
    cfg = dict(app.config)
    cfg["USER_STORE_PATH"] = str(path)
    return cfg


class TheUnsetStateIsNamedNotSilentTests(unittest.TestCase):
    def test_unset_is_reported_as_unconfigured(self):
        self.assertFalse(User.user_store_is_configured(config_without()))

    def test_the_warning_names_the_variable(self):
        warning = User.user_store_warning(config_without())
        self.assertIsNotNone(warning)
        self.assertIn("USER_STORE_PATH", warning)

    def test_the_warning_says_what_to_set_it_to(self):
        """A named error the reader cannot act on is only half a fix."""
        warning = User.user_store_warning(config_without())
        self.assertIn("/data", warning)

    def test_creating_an_account_is_refused_by_name(self):
        with self.assertRaises(ValueError) as caught:
            User.create("someone", "longenough1", config_without())
        self.assertIn("USER_STORE_PATH", str(caught.exception))

    def test_it_refuses_before_validating_the_form(self):
        """Telling the user their password is too short would be a
        misleading answer to a configuration failure."""
        with self.assertRaises(ValueError) as caught:
            User.create("someone", "x", config_without())
        self.assertIn("USER_STORE_PATH", str(caught.exception))


class TheSetStateStillWorksTests(unittest.TestCase):
    def setUp(self):
        self.store = Path(tempfile.mkdtemp()) / "users.json"

    def test_set_is_reported_as_configured(self):
        self.assertTrue(User.user_store_is_configured(config_with(self.store)))

    def test_no_warning_when_set(self):
        self.assertIsNone(User.user_store_warning(config_with(self.store)))

    def test_an_account_is_created_and_written_where_told(self):
        cfg = config_with(self.store)
        User.create("realuser", "longenough1", cfg)
        self.assertTrue(self.store.exists())
        stored = json.load(open(self.store))["users"]
        self.assertIn("realuser", stored)

    def test_the_path_resolves_to_the_configured_file(self):
        self.assertEqual(User.user_store_path(config_with(self.store)),
                         str(self.store.resolve()))


class TheSignupPageShowsBothStatesTests(unittest.TestCase):
    """Driven through the real route, not the helper."""

    def setUp(self):
        self.original = app.config.get("USER_STORE_PATH")
        self.csrf = app.config.get("WTF_CSRF_ENABLED")
        app.config["WTF_CSRF_ENABLED"] = False
        self.addCleanup(self._restore)
        self.client = app.test_client()

    def _restore(self):
        if self.original is None:
            app.config.pop("USER_STORE_PATH", None)
        else:
            app.config["USER_STORE_PATH"] = self.original
        app.config["WTF_CSRF_ENABLED"] = self.csrf

    def test_unset_renders_a_banner_naming_the_variable(self):
        app.config.pop("USER_STORE_PATH", None)
        body = self.client.get("/signup").get_data(as_text=True)
        self.assertIn("Signup is unavailable", body)
        self.assertIn("USER_STORE_PATH", body)

    def test_unset_refuses_the_post_rather_than_creating(self):
        app.config.pop("USER_STORE_PATH", None)
        resp = self.client.post("/signup", data={
            "username": "someone", "password": "longenough1",
            "confirm_password": "longenough1"})
        self.assertEqual(resp.status_code, 200, "must not redirect to dashboard")
        self.assertIn("USER_STORE_PATH", resp.get_data(as_text=True))

    def test_set_renders_no_banner_and_signup_succeeds(self):
        store = Path(tempfile.mkdtemp()) / "users.json"
        app.config["USER_STORE_PATH"] = str(store)
        body = self.client.get("/signup").get_data(as_text=True)
        self.assertNotIn("Signup is unavailable", body)
        resp = self.client.post("/signup", data={
            "username": "realuser", "password": "longenough1",
            "confirm_password": "longenough1"})
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(store.exists())


class TheProductionShapeIsPinnedTests(unittest.TestCase):
    """Every other persistent store already does this."""

    def test_the_fallback_is_still_reachable_for_reads(self):
        """Login and lookup must keep working either way -- only WRITING
        is refused, because a read of a missing file is simply empty."""
        path = User.user_store_path(config_without())
        self.assertTrue(path.endswith("users.json"))

    def test_lookup_does_not_raise_when_unconfigured(self):
        self.assertIsNone(User.find_stored_user("nobody", config_without()))


if __name__ == "__main__":
    unittest.main()

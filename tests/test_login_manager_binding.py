"""One LoginManager, two applications, and whose config it reads.

`login_manager` is a MODULE-LEVEL singleton in app.py. Every
`create_app()` shares that one instance, and each call's
`@login_manager.user_loader` REPLACES the previous callback rather than
adding to it.

So a callback that closes over its own `app` is a trap: build a second
application and the FIRST one starts resolving users against the SECOND
one's config. A session holding a perfectly good user id then loads as
None, `@login_required` redirects, and every page answers with the login
form.

HOW IT SURFACED

`tests/test_fire_metrics_standalone.py` calls `create_app(TestConfig)` in
setUp with `ADMIN_USERNAME = "test-admin"`. Because module order is
alphabetical it runs before `tests/test_investors_nav.py`, which then
failed asserting the notetaker link appears on `/dashboard` -- it was
reading a login page. That test passed on its own and failed in the
suite, which is the signature of shared state and is why the mechanism
had to be found rather than guessed at.

The defect was ours. The fix is `current_app.config` in the loader, and
his test needed no change.

WHAT THESE TESTS PIN

Not "the notetaker link is present" -- that is the symptom, and a test
that only pins a symptom lets the same bug return through a different
page. These pin the property directly: **two applications authenticate
their own users at the same time.**
"""

import unittest

from flask import current_app

from config import Config


class TestConfigA(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "binding-test-a"
    ADMIN_USERNAME = "admin-alpha"
    ADMIN_PASSWORD_HASH = ""


class TestConfigB(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "binding-test-b"
    ADMIN_USERNAME = "admin-beta"
    ADMIN_PASSWORD_HASH = ""


class TwoAppsAuthenticateTheirOwnUsersTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        # Built in this order on purpose: `first` is the one whose loader
        # the second registration would clobber.
        self.first = create_app(TestConfigA)
        self.second = create_app(TestConfigB)

    def signed_in(self, app, username):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = username
            session["_fresh"] = True
        return client

    def loads(self, app, username):
        """Whether this application resolves that user id to a User."""
        from models import User
        with app.test_request_context():
            from app import login_manager
            return login_manager._user_callback(username) is not None

    def test_the_first_app_still_loads_its_own_admin(self):
        """THE REGRESSION. Before the fix this returned False, because the
        second create_app() had re-pointed the shared loader."""
        self.assertTrue(self.loads(self.first, "admin-alpha"))

    def test_the_second_app_loads_its_own_admin(self):
        self.assertTrue(self.loads(self.second, "admin-beta"))

    def test_neither_app_loads_the_other_s_admin(self):
        """The other half. A loader reading current_app must also REFUSE
        a user that belongs to the other application -- otherwise it is
        not reading the right config, it is reading none."""
        self.assertFalse(self.loads(self.first, "admin-beta"))
        self.assertFalse(self.loads(self.second, "admin-alpha"))

    def test_order_does_not_matter(self):
        """Building a third application must not disturb either of the
        first two, whichever way round they were made."""
        from app import create_app
        create_app(TestConfigB)
        self.assertTrue(self.loads(self.first, "admin-alpha"))
        self.assertTrue(self.loads(self.second, "admin-beta"))

    def test_a_page_behind_login_required_actually_renders(self):
        """End to end, because loading a User is necessary and not
        sufficient -- the redirect is what a person would have seen."""
        body = self.signed_in(self.first, "admin-alpha").get(
            "/dashboard", follow_redirects=True).get_data(as_text=True)
        self.assertIn("<title>Dashboard", body)
        self.assertNotIn("<title>Log in", body)

    def test_positive_control_a_bogus_user_is_still_refused(self):
        """Without this, every assertion above would pass on a loader
        that returned a User for anything it was handed."""
        self.assertFalse(self.loads(self.first, "nobody-at-all"))
        body = self.signed_in(self.first, "nobody-at-all").get(
            "/dashboard", follow_redirects=True).get_data(as_text=True)
        self.assertIn("<title>Log in", body)


class TheLoaderReadsTheRequestsAppTests(unittest.TestCase):
    """States the mechanism directly, so a future reader sees WHY rather
    than only that two apps happen to work."""

    def test_the_loader_is_not_closed_over_an_app_config(self):
        from app import create_app, login_manager
        create_app(TestConfigA)
        callback = login_manager._user_callback
        captured = [c.cell_contents for c in (callback.__closure__ or ())]
        offenders = [c for c in captured
                     if hasattr(c, "config") and hasattr(c, "test_client")]
        self.assertEqual(
            offenders, [],
            "the user loader closes over a Flask app; a second create_app() "
            "will re-point the shared LoginManager at the wrong config")

    def test_current_app_is_bound_where_the_loader_runs(self):
        """The fix's one premise. A user loader only ever runs inside a
        request context, which is what makes current_app safe here."""
        app = create_app_a()
        with app.test_request_context():
            self.assertIs(current_app._get_current_object(), app)


def create_app_a():
    from app import create_app
    return create_app(TestConfigA)


if __name__ == "__main__":
    unittest.main()

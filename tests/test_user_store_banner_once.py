"""The configuration banner is shown once, on the page you asked for.

Michelle, on live production: *"I tried logging into my dashboard thru my
laptop and got this error."* The screenshot was the SIGNUP page, at the
URL /login, carrying the USER_STORE_PATH message twice -- once in a
red-bordered block and once as plain text under it.

TWO SEPARATE DEFECTS PRODUCED THAT ONE SCREENSHOT

* The login route rendered `signup.html`, passing the same string as both
  `error` and `user_store_warning`, which that template renders in two
  different blocks. Submitting the login form therefore returned a
  Create-an-account page with the message doubled.
* `User.create()` refuses the write by raising `ValueError(warning)`, the
  signup route assigns that to `error`, and signup.html rendered it again
  beneath its own banner. So the signup form doubled it too, by a
  completely different route.

The second was found by looking rather than by assuming the first was the
whole of it -- the Part 54 lesson about changes scoped to the case in
hand. Both are covered here, and the template-side guard covers callers
that do not exist yet.

WHAT THIS DELIBERATELY DOES NOT CHANGE

The login guard still returns before `User.verify`, so the env-configured
admin still cannot log in while the variable is unset. That is a separate
and larger decision. `test_login_is_still_blocked` pins the current
behaviour so the decision is made deliberately rather than drifted into.
"""

import unittest

from models import User

MESSAGE_MARK = "USER_STORE_PATH is not set"


class BannerTestCase(unittest.TestCase):
    def setUp(self):
        from app import app
        self.app = app
        self._saved = app.config.get("USER_STORE_PATH")
        app.config["WTF_CSRF_ENABLED"] = False
        # The unset state, expressed the way production expresses it:
        # config.py always resolves a value, so "unset" IS "equal to the
        # default". Popping the key -- what the first version of these
        # tests did -- is a state production never reaches, and it is why
        # a broken guard passed its unit tests in Part 51.
        app.config["USER_STORE_PATH"] = app.config["DEFAULT_USER_STORE_PATH"]
        self.client = app.test_client()

    def tearDown(self):
        if self._saved is not None:
            self.app.config["USER_STORE_PATH"] = self._saved

    def count(self, response):
        return response.get_data(as_text=True).count(MESSAGE_MARK)

    def post_login(self):
        return self.client.post("/login", data={"username": "michelle",
                                                "password": "any-password"})

    def post_signup(self, username="zzz_unused_account_name"):
        return self.client.post("/signup", data={
            "username": username, "password": "abcdefgh",
            "confirm_password": "abcdefgh"})


class ThePreconditionTests(BannerTestCase):
    """If the store read as configured, every test below would pass
    vacuously by showing the banner zero times."""

    def test_the_store_reads_as_unconfigured(self):
        self.assertFalse(User.user_store_is_configured(self.app.config))

    def test_and_there_is_a_warning_to_render(self):
        self.assertIn(MESSAGE_MARK,
                      User.user_store_warning(self.app.config) or "")


class ExactlyOnceTests(BannerTestCase):
    def test_submitting_the_login_form(self):
        self.assertEqual(self.count(self.post_login()), 1)

    def test_submitting_the_signup_form(self):
        self.assertEqual(self.count(self.post_signup()), 1)

    def test_opening_the_signup_page(self):
        self.assertEqual(self.count(self.client.get("/signup")), 1)

    def test_opening_the_login_page_shows_it_not_at_all(self):
        """Nothing is being attempted yet, so there is nothing to refuse."""
        self.assertEqual(self.count(self.client.get("/login")), 0)


class ThePageYouAskedForTests(BannerTestCase):
    """The URL and the template have to agree. A Create-an-account form
    returned from /login is why a client thought she was being asked to
    make a new account to reach her own dashboard."""

    def test_posting_to_login_returns_the_login_page(self):
        body = self.post_login().get_data(as_text=True)
        self.assertIn("Log in", body)
        self.assertNotIn("Create an account", body)
        self.assertNotIn("Confirm Password", body)

    def test_posting_to_signup_still_returns_the_signup_page(self):
        body = self.post_signup().get_data(as_text=True)
        self.assertIn("Create an account", body)


class RealErrorsAreStillShownTests(BannerTestCase):
    """Suppressing the duplicate must not suppress anything else. Without
    these, deleting the `error` block entirely would pass the file."""

    def test_a_short_username_still_says_so(self):
        body = self.post_signup(username="ab").get_data(as_text=True)
        self.assertIn("at least 3 characters", body)

    def test_a_mismatched_password_still_says_so(self):
        body = self.client.post("/signup", data={
            "username": "zzz_unused_account_name", "password": "abcdefgh",
            "confirm_password": "different"}).get_data(as_text=True)
        self.assertIn("do not match", body)

    def test_a_real_error_appears_alongside_the_banner_not_instead_of_it(self):
        body = self.post_signup(username="ab").get_data(as_text=True)
        self.assertIn("at least 3 characters", body)
        self.assertEqual(body.count(MESSAGE_MARK), 1)


class WithTheStoreConfiguredTests(BannerTestCase):
    """The positive control for the whole file: configure the store and
    every banner disappears. If these still showed it, the tests above
    would be counting something other than what they claim."""

    def setUp(self):
        super().setUp()
        self.app.config["USER_STORE_PATH"] = "/some/configured/users.json"

    def test_no_banner_on_login(self):
        self.assertEqual(self.count(self.post_login()), 0)

    def test_no_banner_on_signup(self):
        self.assertEqual(self.count(self.client.get("/signup")), 0)

    def test_the_login_form_is_actually_processed(self):
        """With the store configured the guard is gone, so a bad password
        gets a password answer rather than a configuration one."""
        body = self.post_login().get_data(as_text=True)
        self.assertIn("Invalid username or password", body)


class LoginIsStillBlockedTests(BannerTestCase):
    """PINNED, NOT ENDORSED.

    Part 51 recorded that login is unaffected by the user store "because
    the admin account is env-configured". That claim is false: the guard
    returns before `User.verify` is ever called, so while the variable is
    unset NOBODY can log in, admin included. This branch fixes what the
    page looks like and changes nothing about who gets in.

    This test exists so that when the access decision is taken, it is
    taken on purpose and this file fails loudly to mark it.
    """

    def test_login_is_still_blocked(self):
        calls = []
        real = User.verify

        @staticmethod
        def counting(username, password, app_config):
            calls.append(username)
            return real(username, password, app_config)

        User.verify = counting
        try:
            self.post_login()
        finally:
            User.verify = real
        self.assertEqual(calls, [],
                         "User.verify is now reached while the store is "
                         "unset -- who can log in has changed, which is a "
                         "decision, not a side effect")

    def test_positive_control_verify_is_reached_once_configured(self):
        """Without this, the assertion above would pass if `User.verify`
        had simply been renamed."""
        self.app.config["USER_STORE_PATH"] = "/some/configured/users.json"
        calls = []
        real = User.verify

        @staticmethod
        def counting(username, password, app_config):
            calls.append(username)
            return real(username, password, app_config)

        User.verify = counting
        try:
            self.post_login()
        finally:
            User.verify = real
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()

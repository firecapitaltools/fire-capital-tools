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

WHAT PART 55 DELIBERATELY LEFT ALONE, AND PART 57 THEN DID

Part 55 fixed only what the page looked like. The guard still returned
before `User.verify`, so while the variable was unset nobody could log in
at all -- the env-configured admin included, whose credentials never touch
the store file. That was pinned rather than fixed, because changing who
can log in is an operator's decision and not a side effect of fixing a
doubled banner.

Part 57 took that decision: the guard is out of `login()`, signup keeps
its refusal untouched, and the store's one real consequence (a saved
account cannot be READ) gets its own sentence instead of blocking
everyone. The pin was INVERTED rather than deleted -- see
`LoginIsNoLongerBlockedTests` -- so the file still fails loudly if the
guard ever creeps back.
"""

import re
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
    def test_submitting_the_login_form_shows_it_not_at_all(self):
        """It showed twice, then once, and now never.

        Part 55 stopped the login route rendering the SIGNUP template with
        the message in two variables. Part 57 removed the store guard from
        this route altogether, so a login POST is an ordinary credential
        check and the configuration banner has no business on it. The
        store's one real consequence is stated in its own sentence -- see
        LoginIsNoLongerBlockedTests -- without naming the variable.
        """
        self.assertEqual(self.count(self.post_login()), 0)

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


class LoginIsNoLongerBlockedTests(BannerTestCase):
    """INVERTED, NOT DELETED — and the inversion is the point.

    This class used to assert `User.verify` was NEVER reached while the
    store was unset, under the name `test_login_is_still_blocked`. It was
    written that way deliberately: the behaviour was wrong, fixing it
    changed who could log in, and that decision belonged to the operator
    rather than to whoever was fixing the doubled banner. The test pinned
    the wrong behaviour so the change could not be drifted into quietly.

    The decision has now been taken, so the pin is turned over rather than
    thrown away. A deleted test leaves no trace that the question was ever
    live; an inverted one says what changed, when, and why — and it fails
    just as loudly if the guard ever creeps back into the login route.

    WHY THE GUARD WAS WRONG HERE

    A guard is correct relative to the thing it protects. In `signup()`
    the store guard stands between a person and a write that would be
    silently lost on the next deploy, and that is exactly right. Copied
    into `login()` it stood between a person and a READ that was already
    safe -- `_load_store()` returns `{"users": {}}` for a file that is not
    there, and the admin branch under it reads only ADMIN_USERNAME and
    ADMIN_PASSWORD_HASH. It protected nothing and locked everyone out,
    which is how a client lost access to her own dashboard on 2026-08-24.
    """

    def verify_calls(self):
        calls = []
        real = User.verify

        @staticmethod
        def counting(username, password, app_config):
            calls.append(username)
            return real(username, password, app_config)

        User.verify = counting
        try:
            body = self.post_login().get_data(as_text=True)
        finally:
            User.verify = real
        return calls, body

    def test_login_reaches_verify_even_with_the_store_unset(self):
        calls, _ = self.verify_calls()
        self.assertEqual(len(calls), 1,
                         "the store guard is back in the login route")

    def test_positive_control_it_is_the_unset_state_being_tested(self):
        """Guards against this class passing because the store quietly
        read as configured, which would make the assertion trivial."""
        self.assertFalse(User.user_store_is_configured(self.app.config))

    def test_the_failure_is_about_the_credentials_not_the_configuration(self):
        _, body = self.verify_calls()
        self.assertIn("Invalid username or password", body)

    def test_but_it_says_what_the_store_actually_affects(self):
        """The one real consequence: a signup account cannot be READ, so
        telling that person their password is wrong is a false statement
        about their credentials."""
        _, body = self.verify_calls()
        self.assertIn("Saved accounts cannot be read", body)
        self.assertIn("administrator", body)

    def test_that_sentence_is_absent_once_the_store_is_configured(self):
        self.app.config["USER_STORE_PATH"] = "/some/configured/users.json"
        _, body = self.verify_calls()
        self.assertIn("Invalid username or password", body)
        self.assertNotIn("Saved accounts cannot be read", body)

    def test_the_message_is_the_same_for_every_username(self):
        """No oracle. Choosing the wording by username would make this
        page answer "is this the admin account?" to anyone who asked it
        twice."""
        bodies = []
        for name in ("michelle", "definitely-not-a-real-account", "admin"):
            body = self.client.post("/login", data={
                "username": name, "password": "wrong"}).get_data(as_text=True)
            bodies.append(re.findall(r'class="login-error">([^<]*)', body))
        self.assertEqual(len(set(map(tuple, bodies))), 1, bodies)


class TheLoginPageLeaksNothingTests(BannerTestCase):
    """The operator's detail and the visitor's message are different
    things. `user_store_warning()` names the variable and suggests a path;
    that is right for whoever configures Railway and wrong to print on a
    public login page."""

    def test_the_variable_is_never_named_on_the_login_page(self):
        for response in (self.client.get("/login"), self.post_login()):
            with self.subTest(method=response.request.method):
                body = response.get_data(as_text=True)
                self.assertNotIn("USER_STORE_PATH", body)
                self.assertNotIn("/data/users.json", body)


if __name__ == "__main__":
    unittest.main()

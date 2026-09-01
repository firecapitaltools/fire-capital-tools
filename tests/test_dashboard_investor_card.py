"""The description Michelle could still see, asserted on the rendered page.

WHAT WENT WRONG THE FIRST TIME, AND WHY THIS TEST LOOKS LIKE THIS

In August she asked, about the Investor Report: *"remove top
description"*. It was removed from `templates/tools/investor_report.html`
and recorded as done. She then said twice that it was still there —
*"when I logged in that the orange box description is still there."*

**Both statements were true.** The page subtitle was gone; the dashboard
CARD still carried the same abstract framing text, and the dashboard is
what a logged-in user lands on. The triage confirmed the fix by reading a
template comment that quoted her words back, which is a document agreeing
with itself rather than evidence about a screen.

So this asserts on the RENDERED RESPONSE of the URL a real session lands
on — `/`, followed through its redirect — and not on the presence of a
comment, a template file, or a class name.

WHAT IT DOES NOT ASSERT

That no card anywhere has a description. Eight others still do and she
has never objected to them; a test forbidding all of them would be this
codebase inventing a rule she did not ask for. The scope of the check is
the card she pointed at.
"""

import os
import re
import tempfile
import unittest

_SANDBOX = tempfile.mkdtemp(prefix="dashboard-card-")
for _var in ("SITE_DD_DB_PATH", "DEAL_DIVE_DB_PATH", "RENT_COMPS_DB_PATH",
             "MARKET_DATA_DB_PATH", "UNDERWRITING_DB_PATH",
             "SCORECARD_PRO_DB_PATH", "FIRE_METRICS_DB_PATH",
             "FEEDBACK_DB_PATH", "INVESTOR_REPORT_DB_PATH",
             "INVESTOR_NOTES_DB_PATH", "OPENAI_USAGE_DB_PATH",
             "APP_SETTINGS_DB_PATH"):
    os.environ[_var] = os.path.join(_SANDBOX, _var.lower() + ".db")
os.environ.setdefault("UPLOAD_FOLDER_PATH", os.path.join(_SANDBOX, "uploads"))

# The words she was looking at, kept verbatim so this fails if they return
# under a different tag, a different card, or a different page.
REMOVED_TEXT = "LP/GP distribution waterfalls"


class WhatALoggedInUserLandsOnTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        app.config["WTF_CSRF_ENABLED"] = False
        cls.app = app

    def landing(self):
        """The URL she actually opens, followed where it goes."""
        c = self.app.test_client()
        with c.session_transaction() as s:
            s["_user_id"] = self.app.config.get("ADMIN_USERNAME")
            s["_fresh"] = True
        response = c.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def orange_card(self, html):
        m = re.search(r'<a[^>]*tool-card--orange.*?</a>', html, re.S)
        self.assertIsNotNone(
            m, "the orange Investor Report card is not on the dashboard")
        return m.group(0)

    def test_the_landing_page_is_the_dashboard(self):
        """Assert the thing under test before asserting about it. If `/`
        ever stops leading here, every assertion below would pass by
        checking the wrong screen."""
        html = self.landing()
        self.assertIn("tool-grid", html)
        self.assertIn("Investor Report", html)

    def test_the_orange_card_has_no_description(self):
        card = self.orange_card(self.landing())
        self.assertNotIn("tool-card-desc", card,
                         "the description is back on the card she named")
        self.assertNotIn(REMOVED_TEXT, card)

    def test_the_text_is_absent_from_the_whole_rendered_page(self):
        """Not just moved to another tag on the same screen."""
        self.assertNotIn(REMOVED_TEXT, self.landing())

    def test_the_card_still_works_as_a_card(self):
        """Positive control on the removal: it took the description and
        nothing else. A test that only asserts absence passes just as
        well if the whole card was deleted."""
        card = self.orange_card(self.landing())
        self.assertIn("Investor Report", card)
        self.assertIn("investor-report", card)
        self.assertIn("tool-card-icon", card)
        self.assertIn("tool-tag", card)

    def test_the_other_cards_kept_theirs(self):
        """The scope was one card. If this ever fails, the fix grew past
        what she asked for."""
        html = self.landing()
        self.assertGreaterEqual(html.count("tool-card-desc"), 5)

    def test_it_is_still_the_only_orange_card(self):
        """Her word for it was "the orange box", which only identifies
        one card while that stays true."""
        self.assertEqual(self.landing().count("tool-card--orange"), 1)


class ThePageItselfStayedFixedTests(unittest.TestCase):
    """The August removal was real. This keeps it that way, so a future
    reading of this bug does not conclude the first fix was fictional."""

    @classmethod
    def setUpClass(cls):
        from app import app
        app.config["WTF_CSRF_ENABLED"] = False
        cls.app = app

    def test_no_subtitle_on_the_investor_report_page(self):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s["_user_id"] = self.app.config.get("ADMIN_USERNAME")
            s["_fresh"] = True
        html = c.get("/tools/investor-report/",
                     follow_redirects=True).get_data(as_text=True)
        self.assertIn("Investor Report", html)
        self.assertNotIn(REMOVED_TEXT, html)
        self.assertNotIn("ten conservation invariants", html)


if __name__ == "__main__":
    unittest.main()

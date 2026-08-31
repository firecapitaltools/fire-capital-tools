"""Adding a property from the page she was standing on.

Michelle, in the feedback form, from `/tools/investor-report/?deal_id=2`:
*"i need ability to add a new property/deal"*. Both mechanisms already
existed — Deal Dive makes deals, `investor_notes.add_property` makes
name-only properties — and neither was reachable from that page. **What
was missing was the affordance, not the feature**, which is why this is
an hour rather than a properties table.

TWO THINGS THIS FILE IS REALLY ABOUT

1. **She must not leave the page.** That was the ask. So `add_property`
   learned where it was called from, and the tests follow the redirect
   rather than trusting it.
2. **`return_to` is a KEY, never a URL.** A `next` parameter that accepts
   a path is an open redirect, and this form is reachable by anyone who
   can log in — which, since 2026-08-27, is more than one person.

And the screen has to say what it makes. A property name is something
notes can be matched against; a deal has an address and a waterfall.
Blurring the two is how "Nabob Hill" became a registry entry that
resolves to no deal.
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import investor_notes_db as notes_db
from tools import underwriting_db


class AddPropertyTestCase(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        for module, name in ((notes_db, "notes.db"), (underwriting_db, "uw.db")):
            patch = mock.patch.object(module, "get_db_path", lambda p=tmp / name: p)
            patch.start()
            self.addCleanup(patch.stop)
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def page(self):
        return self.client.get("/tools/investor-report/").get_data(as_text=True)

    def add(self, label, return_to="investor_report", follow=False):
        return self.client.post("/tools/investor-report/notes/properties",
                                data={"property_label": label,
                                      "return_to": return_to},
                                follow_redirects=follow)

    def labels(self):
        with underwriting_db.get_connection() as conn:
            return [s["property_label"] for s in underwriting_db.list_scenarios(conn)]


class ItIsReachableFromWhereSheAskedTests(AddPropertyTestCase):
    """Reachability by navigation, not by URL."""

    def test_the_page_carries_the_form(self):
        body = self.page()
        match = re.search(r'<form[^>]*action="([^"]*notes/properties)"', body)
        self.assertIsNotNone(match, "no add-property form on the Investor Report")

    def test_the_form_posts_to_the_route_that_exists(self):
        body = self.page()
        action = re.search(r'<form[^>]*action="([^"]*notes/properties)"',
                           body).group(1)
        response = self.client.post(action, data={"property_label": "Harvested",
                                                  "return_to": "investor_report"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("Harvested", self.labels())

    def test_it_carries_the_return_key(self):
        self.assertIn('name="return_to" value="investor_report"', self.page())


class SheDoesNotLeaveThePageTests(AddPropertyTestCase):
    """The whole of the ask."""

    def test_adding_returns_to_the_investor_report(self):
        response = self.add("Oxford Pointe")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/tools/investor-report/", response.headers["Location"])
        self.assertNotIn("notes", response.headers["Location"])

    def test_a_duplicate_also_returns_there(self):
        self.add("Oxford Pointe")
        response = self.add("oxford  pointe")
        self.assertIn("/tools/investor-report/", response.headers["Location"])

    def test_an_empty_name_also_returns_there(self):
        response = self.add("   ")
        self.assertIn("/tools/investor-report/", response.headers["Location"])

    def test_the_notetaker_still_returns_to_the_notetaker(self):
        """The original caller must be unaffected by the new one."""
        response = self.add("From the notetaker", return_to="notetaker")
        self.assertIn("/notes", response.headers["Location"])
        self.assertIn("#properties", response.headers["Location"])

    def test_an_absent_return_key_falls_back_to_the_notetaker(self):
        response = self.client.post("/tools/investor-report/notes/properties",
                                    data={"property_label": "No key given"})
        self.assertIn("/notes", response.headers["Location"])


class TheReturnKeyCannotBeAUrlTests(AddPropertyTestCase):
    """An open redirect on a logged-in form, and more than one person can
    log in since 2026-08-27."""

    def test_a_url_in_return_to_is_ignored(self):
        response = self.add("Somewhere", return_to="https://example.com/evil")
        self.assertNotIn("example.com", response.headers["Location"])
        self.assertIn("/notes", response.headers["Location"])

    def test_a_path_in_return_to_is_ignored(self):
        response = self.add("Somewhere else", return_to="//evil.test/x")
        self.assertNotIn("evil.test", response.headers["Location"])

    def test_the_allowlist_is_a_closed_set_of_endpoints(self):
        from tools import investor_notes
        self.assertEqual(set(investor_notes.RETURN_TO),
                         {"notetaker", "investor_report"})


class ItSaysWhatItMakesTests(AddPropertyTestCase):
    """A property name is not a deal, and the Nabob Hill duplicate is what
    happens when a screen lets somebody assume otherwise."""

    def test_the_page_says_it_is_not_a_deal(self):
        body = self.page()
        self.assertIn("This is not a deal", body)

    def test_and_points_at_deal_dive_for_one(self):
        self.assertIn("Deal Dive", self.page())

    def test_the_confirmation_says_the_same_thing(self):
        body = self.add("Papania", follow=True).get_data(as_text=True)
        self.assertIn("It is NOT a deal", body)

    def test_what_it_actually_creates_is_a_named_scenario(self):
        self.add("River Oaks")
        with underwriting_db.get_connection() as conn:
            made = [s for s in underwriting_db.list_scenarios(conn)
                    if s["property_label"] == "River Oaks"]
        self.assertEqual(len(made), 1)
        self.assertIn("Placeholder", made[0]["name"])

    def test_it_does_not_create_a_deal(self):
        from tools import deal_dive_db
        self.add("Cannongate")
        with deal_dive_db.get_connection() as conn:
            self.assertEqual(
                [d for d in deal_dive_db.list_deals(conn)
                 if "Cannongate" in (d.get("address") or "")], [])


if __name__ == "__main__":
    unittest.main()

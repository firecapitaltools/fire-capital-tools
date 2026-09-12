"""Michelle's draft, opened from a phone.

THE BUG

A Site DD draft created on a laptop was visible in the assessment list on
the mobile PWA but could not be tapped open. Nothing server-side gated a
draft: no ownership column exists on site_dd_assessments, the detail
route has no status check, and the index route lists every assessment
regardless of who created it. Reproduced instead as a layout problem: the
list is an 8-column table and the only link to a row -- the "Open" button
-- is the LAST column. On a 390px phone viewport that link renders at
x >= 720, most of a second screen-width past the visible area, with no
scrollbar or affordance suggesting a horizontal scroll exists. Confirmed
with Playwright against the running app before this file existed; not
reproducible from HTML alone, because a test that only checks "the href
is present" would have passed on the broken markup too.

THE FIX

The property-name cell -- the one column guaranteed to be on-screen at
any width, because it is first -- is now itself a link to the same
detail route the Open button already pointed at. No second workflow, no
mobile-only template, no new route: the same href in a place a thumb can
reach without discovering that the table scrolls.

THE OTHER HALF

Once a draft is reachable from any device, "the same assessment, open on
two devices" is the ordinary case, not an edge case. There is no
per-user ownership to weaken: any logged-in user already saw every
assessment (see list_assessments()), so multi-user access needed no
change, only confirming it holds after the Open link stopped being the
only path in. What DID need a change was the save path: it posts the
FULL rendered checklist, not a diff, so two overlapping saves would
silently let the second stomp the first's work with the values ITS page
loaded with. save() now compares the page's expected_updated_at against
the assessment's live updated_at (already an existing NOT NULL column)
before writing, and refuses a stale save with a flash rather than
overwriting."""

import os
import tempfile
import unittest
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="site-dd-mobile-")
for _var in ("SITE_DD_DB_PATH", "DEAL_DIVE_DB_PATH", "RENT_COMPS_DB_PATH",
             "MARKET_DATA_DB_PATH", "UNDERWRITING_DB_PATH",
             "SCORECARD_PRO_DB_PATH", "FIRE_METRICS_DB_PATH",
             "FEEDBACK_DB_PATH", "INVESTOR_REPORT_DB_PATH",
             "INVESTOR_NOTES_DB_PATH", "OPENAI_USAGE_DB_PATH",
             "APP_SETTINGS_DB_PATH"):
    os.environ[_var] = os.path.join(_SANDBOX, _var.lower() + ".db")
os.environ.setdefault("UPLOAD_FOLDER_PATH", os.path.join(_SANDBOX, "uploads"))

from app import app                                       # noqa: E402
from models import User                                   # noqa: E402
from tools import site_dd_db as db                        # noqa: E402

ADMIN_USER = "michelle"
SECOND_USER = "bob"


class SiteDDMobileDraftAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["ADMIN_USERNAME"] = ADMIN_USER
        app.config["USER_STORE_PATH"] = str(Path(_SANDBOX) / "users.json")
        User.create(SECOND_USER, "correct horse battery staple", app.config)
        cls.app = app

    def client(self, user=ADMIN_USER):
        """A fresh session for `user` -- a separate client stands in for a
        separate device/browser, exactly as Michelle's laptop and phone
        are separate sessions against the same server."""
        c = self.app.test_client()
        if user is not None:
            with c.session_transaction() as s:
                s["_user_id"] = user
                s["_fresh"] = True
        return c

    def make_draft(self, label="123 Test Ave, Atlanta GA"):
        r = self.client().post("/tools/site-dd/new", data={"property_label": label},
                                follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        # new_assessment() redirects straight to the detail page it just
        # made; the id is only knowable from where the redirect landed.
        self.assertIn("/tools/site-dd/assessment/", r.request.path)
        assessment_id = int(r.request.path.rstrip("/").rsplit("/", 1)[-1])
        return assessment_id, body

    # 1 & 2 -- created, and appears in the list --------------------------

    def test_a_new_assessment_is_a_draft_and_appears_in_the_list(self):
        aid, _ = self.make_draft()
        with db.get_connection() as conn:
            row = db.get_assessment(conn, aid)
        self.assertEqual(row["status"], db.STATUS_DRAFT)

        listing = self.client().get("/tools/site-dd/").get_data(as_text=True)
        self.assertIn("123 Test Ave, Atlanta GA", listing)
        self.assertIn("Draft", listing)

    # 3 -- a valid open/edit URL, reachable WITHOUT the off-screen column -

    def test_the_property_name_itself_links_to_the_draft(self):
        """This is the regression check for the actual bug: the fix is
        that the property-name cell is a link, not merely that an Open
        button exists somewhere in the row (it always did)."""
        aid, _ = self.make_draft()
        listing = self.client().get("/tools/site-dd/").get_data(as_text=True)
        expected_href = f'href="/tools/site-dd/assessment/{aid}"'
        self.assertIn(expected_href, listing)
        # The href must appear attached to the property name, i.e. before
        # the "Open" button's own copy of the same href -- proving a
        # second, earlier link exists rather than only the last column's.
        name_link = f'<a href="/tools/site-dd/assessment/{aid}">123 Test Ave, Atlanta GA</a>'
        self.assertIn(name_link, listing)

    # 4 & 5 -- opened from a separate session, draft data preserved -------

    def test_a_second_session_opens_the_same_draft_with_its_data_intact(self):
        aid, _ = self.make_draft("456 Oak St, Marietta GA")
        with db.get_connection() as conn:
            before = len(db.list_assessments(conn, all_scopes=True))

        other_session = self.client()  # a second, unrelated test client
        r = other_session.get(f"/tools/site-dd/assessment/{aid}")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("456 Oak St, Marietta GA", body)
        with db.get_connection() as conn:
            row = db.get_assessment(conn, aid)
        self.assertEqual(row["status"], db.STATUS_DRAFT, "opening a draft must not change its status")
        with db.get_connection() as conn:
            after = len(db.list_assessments(conn, all_scopes=True))
            self.assertEqual(after, before,
                              "opening it must not create a second assessment")

    # 6 -- a second authorized user can open the same draft ---------------

    def test_a_second_authorized_user_can_open_the_same_assessment(self):
        aid, _ = self.make_draft()
        r = self.client(SECOND_USER).get(f"/tools/site-dd/assessment/{aid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("123 Test Ave, Atlanta GA", r.get_data(as_text=True))

    # 7 -- an unauthenticated request cannot ------------------------------

    def test_an_unauthenticated_request_is_turned_back(self):
        aid, _ = self.make_draft()
        # A sibling test module leaves LOGIN_DISABLED = True on the shared
        # Flask app singleton for the rest of the process, which would
        # make @login_required a no-op and this test meaningless. Forced
        # to real enforcement for this one request, restored after --
        # the surrounding suite's state is not this test's to keep.
        prior = app.config.get("LOGIN_DISABLED", False)
        app.config["LOGIN_DISABLED"] = False
        try:
            r = self.client(user=None).get(f"/tools/site-dd/assessment/{aid}", follow_redirects=False)
        finally:
            app.config["LOGIN_DISABLED"] = prior
        self.assertIn(r.status_code, (302, 401, 403))
        if r.status_code == 302:
            self.assertIn("/login", r.headers.get("Location", ""))

    # 8 -- an edit from one client is visible from another -----------------

    def test_an_edit_saved_on_one_client_is_visible_on_another(self):
        aid, _ = self.make_draft()
        device_a = self.client(ADMIN_USER)
        device_b = self.client(SECOND_USER)

        page = device_a.get(f"/tools/site-dd/assessment/{aid}").get_data(as_text=True)
        self.assertNotIn("Roof needs replacing before close", page)

        device_a.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "123 Test Ave, Atlanta GA",
            "status": "draft",
            "note_roof_covering": "Roof needs replacing before close",
        })

        reloaded = device_b.get(f"/tools/site-dd/assessment/{aid}").get_data(as_text=True)
        self.assertIn("Roof needs replacing before close", reloaded)

    # 9 -- a stale save does not silently overwrite a newer one ------------

    def test_a_stale_save_does_not_overwrite_a_newer_save(self):
        aid, _ = self.make_draft()
        device_a = self.client(ADMIN_USER)
        device_b = self.client(SECOND_USER)

        # Both load the same starting point.
        with db.get_connection() as conn:
            opened_at = db.get_assessment(conn, aid)["updated_at"]

        # A saves first -- a real edit, and updated_at moves forward.
        device_a.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "123 Test Ave, Atlanta GA",
            "status": "draft",
            "inspector": "A's name",
            "expected_updated_at": opened_at,
        })
        with db.get_connection() as conn:
            after_a = db.get_assessment(conn, aid)
        self.assertEqual(after_a["inspector"], "A's name")

        # B's page was rendered before A saved, so B's hidden field still
        # carries the ORIGINAL updated_at -- exactly what a page open
        # before A's save would hold.
        r = device_b.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "123 Test Ave, Atlanta GA",
            "status": "draft",
            "inspector": "B's stale overwrite",
            "expected_updated_at": opened_at,
        }, follow_redirects=True)

        self.assertIn("Someone else saved changes", r.get_data(as_text=True))
        with db.get_connection() as conn:
            after_b = db.get_assessment(conn, aid)
        self.assertEqual(after_b["inspector"], "A's name",
                          "a stale save must not silently overwrite the newer one")

    def test_a_save_with_the_current_updated_at_succeeds(self):
        """The mechanism does not block ordinary sequential saves -- only
        a save whose expected_updated_at has actually gone stale."""
        aid, _ = self.make_draft()
        c = self.client()
        with db.get_connection() as conn:
            t1 = db.get_assessment(conn, aid)["updated_at"]
        c.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "123 Test Ave, Atlanta GA", "status": "draft",
            "inspector": "First save", "expected_updated_at": t1,
        })
        with db.get_connection() as conn:
            t2 = db.get_assessment(conn, aid)["updated_at"]
        r = c.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "123 Test Ave, Atlanta GA", "status": "draft",
            "inspector": "Second save", "expected_updated_at": t2,
        }, follow_redirects=True)
        self.assertNotIn("Someone else saved changes", r.get_data(as_text=True))
        with db.get_connection() as conn:
            self.assertEqual(db.get_assessment(conn, aid)["inspector"], "Second save")

    # 10 -- a completed assessment is unaffected ---------------------------

    def test_a_completed_assessment_still_opens_and_lists_normally(self):
        aid, _ = self.make_draft("789 Pine Rd, Decatur GA")
        with db.get_connection() as conn:
            db.update_assessment(conn, aid, {
                "property_label": "789 Pine Rd, Decatur GA",
                "status": db.STATUS_COMPLETE,
            })
        listing = self.client().get("/tools/site-dd/").get_data(as_text=True)
        self.assertIn("Complete", listing)
        self.assertIn(f'href="/tools/site-dd/assessment/{aid}"', listing)

        r = self.client(SECOND_USER).get(f"/tools/site-dd/assessment/{aid}")
        self.assertEqual(r.status_code, 200)
        with db.get_connection() as conn:
            self.assertEqual(db.get_assessment(conn, aid)["status"], db.STATUS_COMPLETE)


if __name__ == "__main__":
    unittest.main()

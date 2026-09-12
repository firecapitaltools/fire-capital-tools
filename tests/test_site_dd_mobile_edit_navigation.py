"""The mobile assessment detail page: editable, and PDFs that let go.

THE BUG (reported from a real iPhone, after the previous fix made a
draft tappable at all)

Once inside a draft, there was no way to tell where to edit it. The
editable checklist form was real and always had been -- nothing was
disabled, hidden by CSS, or gated behind another route -- but the first
thing the page showed was a row of document buttons, one of them styled
as THE primary action (Condition Report, in the app's blue "start here"
colour), with the actual form further down and no signpost pointing at
it. And because the document links navigated the SAME window, tapping
one inside the installed iOS PWA replaced the app's one webview with a
PDF that has no browser chrome to escape from -- no tab bar, no back
gesture. Two different problems that both look like "I'm stuck": one is
"I can't find how to edit", the other is "I can't get back".

THE FIX

- A "Continue Assessment" link, #checklist, added right under the page
  title -- signposting the existing form, not a new one. Same page, same
  assessment id, same save button.
- The three document exports demoted from "look like the main action" to
  a consistent secondary style, and target="_blank" rel="noopener" added
  to them and to the per-photo download links, so a document opens
  outside the single-webview PWA shell instead of replacing it.
- An explicit note when nothing has been assessed yet, naming why the
  exports will be empty rather than leaving that to be read as broken.

These tests exercise the rendered HTML rather than a real WebKit
navigation (there is no headless iOS PWA to assert against from here);
what a same-page anchor and target="_blank" do once they leave this
process is standard browser/OS behaviour, not something this app
controls further.
"""

import os
import tempfile
import unittest
from pathlib import Path

_SANDBOX = tempfile.mkdtemp(prefix="site-dd-mobile-edit-")
for _var in ("SITE_DD_DB_PATH", "DEAL_DIVE_DB_PATH", "RENT_COMPS_DB_PATH",
             "MARKET_DATA_DB_PATH", "UNDERWRITING_DB_PATH",
             "SCORECARD_PRO_DB_PATH", "FIRE_METRICS_DB_PATH",
             "FEEDBACK_DB_PATH", "INVESTOR_REPORT_DB_PATH",
             "INVESTOR_NOTES_DB_PATH", "OPENAI_USAGE_DB_PATH",
             "APP_SETTINGS_DB_PATH"):
    os.environ[_var] = os.path.join(_SANDBOX, _var.lower() + ".db")
os.environ.setdefault("UPLOAD_FOLDER_PATH", os.path.join(_SANDBOX, "uploads"))

from app import app                                       # noqa: E402
from tools import site_dd_db as db                        # noqa: E402

ADMIN_USER = "michelle"


class SiteDDMobileEditNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["ADMIN_USERNAME"] = ADMIN_USER
        cls.app = app

    def client(self):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s["_user_id"] = ADMIN_USER
            s["_fresh"] = True
        return c

    def make_draft(self, label="123 Test Ave, Atlanta GA"):
        r = self.client().post("/tools/site-dd/new", data={"property_label": label},
                                follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        assessment_id = int(r.request.path.rstrip("/").rsplit("/", 1)[-1])
        return assessment_id

    def detail(self, assessment_id):
        return self.client().get(f"/tools/site-dd/assessment/{assessment_id}").get_data(as_text=True)

    # 1 & 2 -- an edit/continue action, pointing at the same assessment ----

    def test_the_detail_page_exposes_a_continue_action(self):
        aid = self.make_draft()
        body = self.detail(aid)
        self.assertIn('href="#checklist"', body)
        self.assertIn("Continue Assessment", body)

    def test_the_continue_action_points_at_the_existing_checklist_form_on_this_page(self):
        """Not a new route -- the same page's own editable form. The id
        the link targets must exist, and must be the form that posts to
        site_dd.save for THIS assessment."""
        aid = self.make_draft()
        body = self.detail(aid)
        self.assertIn('id="checklist"', body)
        self.assertIn(f'action="/tools/site-dd/assessment/{aid}/save"', body)

    # 3 -- existing values remain when reopening ----------------------------

    def test_existing_values_are_still_there_after_the_ux_change(self):
        aid = self.make_draft("456 Oak St, Marietta GA")
        c = self.client()
        c.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "456 Oak St, Marietta GA",
            "status": "draft",
            "inspector": "Michelle",
            "note_roof_covering": "Cracked shingles on the north slope",
        })
        body = self.detail(aid)
        self.assertIn("456 Oak St, Marietta GA", body)
        self.assertIn("Michelle", body)
        self.assertIn("Cracked shingles on the north slope", body)
        with db.get_connection() as conn:
            self.assertEqual(db.get_assessment(conn, aid)["status"], db.STATUS_DRAFT)

    # 4 -- document links use safe navigation -------------------------------

    def test_document_links_open_outside_the_page_not_in_place(self):
        aid = self.make_draft()
        body = self.detail(aid)
        for path in (f"/tools/site-dd/assessment/{aid}/report",
                     f"/tools/site-dd/assessment/{aid}/capex.xlsx",
                     f"/tools/site-dd/assessment/{aid}/capex.pdf"):
            with self.subTest(path=path):
                href = f'href="{path}"'
                self.assertIn(href, body)
                # The <a ...> tag containing this href must also carry
                # target="_blank" -- checked on the same tag, not just
                # anywhere on the page, so a stray target elsewhere can't
                # make this pass by accident.
                start = body.index(href)
                tag_start = body.rindex("<a ", 0, start)
                tag_end = body.index(">", start)
                tag = body[tag_start:tag_end]
                self.assertIn('target="_blank"', tag)
                self.assertIn('rel="noopener"', tag)

    def test_the_report_button_is_no_longer_styled_as_the_primary_action(self):
        """The mis-signposting this whole bug report traced back to:
        the download button read as "the" action because it was the one
        button styled btn-primary. Continue Assessment carries that
        styling now; the report link does not."""
        aid = self.make_draft()
        body = self.detail(aid)
        report_start = body.index(f'href="/tools/site-dd/assessment/{aid}/report"')
        tag_start = body.rindex("<a ", 0, report_start)
        tag_end = body.index(">", report_start)
        tag = body[tag_start:tag_end]
        self.assertNotIn("btn-primary", tag)

    # 5 -- missing/unavailable documents do not read as broken -------------

    def test_a_fresh_draft_explains_why_its_exports_will_be_empty(self):
        aid = self.make_draft()
        body = self.detail(aid)
        self.assertIn("Nothing has been recorded yet", body)

    def test_the_explanation_goes_away_once_something_is_recorded(self):
        aid = self.make_draft()
        c = self.client()
        c.post(f"/tools/site-dd/assessment/{aid}/save", data={
            "property_label": "123 Test Ave, Atlanta GA",
            "status": "draft",
            "condition_roof_covering": "repair",
        })
        body = self.detail(aid)
        self.assertNotIn("Nothing has been recorded yet", body)

    # 6 -- desktop is not broken --------------------------------------------

    def test_the_checklist_form_and_save_button_are_still_present(self):
        """The signpost and the safe-navigation links are additions, not
        a rewrite -- the underlying editor is untouched."""
        aid = self.make_draft()
        body = self.detail(aid)
        self.assertIn("Save Assessment", body)
        self.assertIn('name="property_label"', body)
        self.assertIn('name="expected_updated_at"', body)

    def test_a_completed_assessment_still_shows_the_continue_action_and_its_status(self):
        aid = self.make_draft()
        with db.get_connection() as conn:
            db.update_assessment(conn, aid, {
                "property_label": "123 Test Ave, Atlanta GA",
                "status": db.STATUS_COMPLETE,
            })
        body = self.detail(aid)
        self.assertIn("Complete", body)
        self.assertIn('href="#checklist"', body)


if __name__ == "__main__":
    unittest.main()

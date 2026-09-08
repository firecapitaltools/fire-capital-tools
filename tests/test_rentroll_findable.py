"""The rent-roll import has to look like an action, not read like a footnote.

WHAT HAPPENED

The import shipped correct, tested, linked and covered by every sweep we
have — the route is referenced by a template, so it is *reachable*. It was
a link inside a sentence, in subtitle grey, immediately above a manual add
form whose "Add" is a solid primary button.

**On a live call neither Jasper nor Michelle could find it.** Both knew
the feature existed. Both knew it was on that page.

So the page's visual hierarchy recommended typing 152 units in one at a
time and mentioned the thing that does all 152 in prose. **Reachable is
not findable, and no sweep in this repo measures the difference** — a link
in a paragraph passes all of them.

WHAT THIS TEST CAN AND CANNOT DO

It can pin the affordance: that the control renders as a button, that its
weight is right for the state, and that it never disappears. That is
mechanical and worth holding.

**It cannot tell you whether somebody will find it.** No assertion can.
The honest substitute is that a person who did not build the page tries to
use it, and this file is not a replacement for that — see HANDOFF,
*Reachability is not findability*.
"""

import os
import re
import tempfile
import unittest

_SANDBOX = tempfile.mkdtemp(prefix="rentroll-findable-")
for _var in ("SITE_DD_DB_PATH", "DEAL_DIVE_DB_PATH", "RENT_COMPS_DB_PATH",
             "MARKET_DATA_DB_PATH", "UNDERWRITING_DB_PATH",
             "SCORECARD_PRO_DB_PATH", "FIRE_METRICS_DB_PATH",
             "FEEDBACK_DB_PATH", "INVESTOR_REPORT_DB_PATH",
             "INVESTOR_NOTES_DB_PATH", "OPENAI_USAGE_DB_PATH",
             "APP_SETTINGS_DB_PATH"):
    os.environ[_var] = os.path.join(_SANDBOX, _var.lower() + ".db")
os.environ.setdefault("UPLOAD_FOLDER_PATH", os.path.join(_SANDBOX, "uploads"))

from tools import site_dd_db as db  # noqa: E402

IMPORT_TEXT = "Import units from a rent roll"


class TheImportIsAnActionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app import app
        app.config["WTF_CSRF_ENABLED"] = False
        cls.app = app
        with db.get_connection() as conn:
            cls.empty_id = db.create_assessment(
                conn, {"property_label": "Empty Building",
                       "checklist_version": 2})
            cls.full_id = db.create_assessment(
                conn, {"property_label": "Occupied Building",
                       "checklist_version": 2})
            db.create_area(conn, cls.full_id, {"label": "204", "kind": "unit"})

    def page(self, assessment_id):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s["_user_id"] = self.app.config.get("ADMIN_USERNAME")
            s["_fresh"] = True
        r = c.get(f"/tools/site-dd/assessment/{assessment_id}",
                  follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        return r.get_data(as_text=True)

    def control(self, html):
        """The import control as rendered, whatever it is."""
        m = re.search(r'<a[^>]*seed_preview[^>]*>.*?</a>', html, re.S)
        if m is None:
            m = re.search(r'<a[^>]*href="[^"]*seed[^"]*"[^>]*>.*?</a>', html, re.S)
        self.assertIsNotNone(m, "the rent-roll import is not on the page at all")
        return m.group(0)

    def add_button(self, html):
        m = re.search(r'<button[^>]*type="submit"[^>]*>\s*Add\s*</button>', html)
        self.assertIsNotNone(m, "the manual add button is gone")
        return m.group(0)

    # ── it is a button, in both states ────────────────────────────────────

    def test_on_an_empty_assessment_it_is_the_primary_action(self):
        """The moment the import is most useful is the moment the page
        used to offer a single-unit form first."""
        html = self.page(self.empty_id)
        self.assertIn("No units added yet", html)
        ctrl = self.control(html)
        self.assertIn("btn", ctrl, "it is still not a button")
        self.assertIn("btn-primary", ctrl)
        self.assertIn(IMPORT_TEXT, ctrl)

    def test_on_a_populated_assessment_it_steps_back_but_stays_a_button(self):
        """Less prominent by rights. Not absent."""
        ctrl = self.control(self.page(self.full_id))
        self.assertIn("btn", ctrl, "it fell back to a bare link")
        self.assertIn("btn-ghost", ctrl)
        self.assertNotIn("btn-primary", ctrl)
        self.assertIn(IMPORT_TEXT, ctrl)

    def test_it_is_never_only_a_sentence(self):
        """THE REGRESSION THIS FILE EXISTS FOR. A link with no button
        class is what two people could not find."""
        for aid in (self.empty_id, self.full_id):
            with self.subTest(assessment=aid):
                self.assertRegex(self.control(self.page(aid)),
                                 r'class="[^"]*\bbtn\b')

    # ── the manual form is ranked, not removed ────────────────────────────

    def test_the_manual_form_survives_in_both_states(self):
        """Adding one unit is a real thing an inspector does mid-walk.
        This was never about replacing it."""
        for aid in (self.empty_id, self.full_id):
            with self.subTest(assessment=aid):
                html = self.page(aid)
                self.assertIn(f"/assessment/{aid}/areas", html,
                              "the manual add form no longer posts anywhere")
                self.assertIn('name="label"', html)
                self.assertIn("btn", self.add_button(html))

    def test_the_weights_are_opposite_and_never_both_primary(self):
        """Two primary buttons side by side is the same failure wearing
        different clothes: nothing is recommended, so everything competes."""
        empty, full = self.page(self.empty_id), self.page(self.full_id)
        self.assertIn("btn-primary", self.control(empty))
        self.assertIn("btn-ghost", self.add_button(empty))
        self.assertIn("btn-ghost", self.control(full))
        self.assertIn("btn-primary", self.add_button(full))

    # ── the reassurance is why anyone dares press it ──────────────────────

    def test_the_reassurance_survives_in_both_states(self):
        """'Nothing is saved until you say so' is the reason somebody
        clicks an import on real data. Losing it to make room for a
        button would have been a bad trade."""
        for aid in (self.empty_id, self.full_id):
            with self.subTest(assessment=aid):
                html = self.page(aid)
                self.assertIn("Nothing is saved until you approve a preview", html)

    def test_the_import_link_still_points_at_the_preview(self):
        """Positive control on all of the above: a button that goes
        nowhere would satisfy every assertion about its class."""
        ctrl = self.control(self.page(self.empty_id))
        self.assertRegex(ctrl, r'href="[^"]*/seed[^"]*"')


if __name__ == "__main__":
    unittest.main()

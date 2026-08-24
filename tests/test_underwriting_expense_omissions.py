"""save_expenses defends its values, not only its rows.

A PARTIAL DEFENCE IS MORE DANGEROUS THAN NONE

This route was cited — including by me — as the precedent for the whole
absent-means-unchanged pattern, because it carries acquisition lines
through with a comment naming the hazard. It was defending three of six
fields.

Rows were safe: it iterates storage, so nothing is deleted by omission.
`growth_schedule` was safe: already absent-means-unchanged. But
`annual_amount`, `growth_pct` and `is_included` were read straight from
the request, so a save from a page that had not rendered a row left it at

    amount=None  growth=None  is_included=False

The row survived, which is exactly what made it dangerous: nothing looked
deleted. The line simply stopped contributing to NOI and read as
*deliberately excluded* rather than damaged.

THE CHECKBOX NEEDS A COMPANION AND THE TEXT INPUTS DO NOT

A rendered text input always posts, even when empty, so absent means "not
rendered" and the distinction is free. **An unchecked checkbox posts
nothing**, so `included_{id}` absent is genuinely ambiguous — it means
either "rendered and unticked" or "never on the page".

`row_{id}` is a hidden field the template always emits for a rendered
row. Marker present means the form is speaking about this row, so silence
on the checkbox is a real "no". Marker absent means the row was never
shown and everything about it stays as stored.

A SECOND, ACCIDENTAL LAYER WORTH KNOWING ABOUT

`replace_expense_lines` reassigns line ids on every save. A genuinely
stale page therefore carries `amount_{old_id}` fields naming ids that no
longer exist, so every value reads as absent and is preserved. That is
belt-and-braces rather than the mechanism — it would stop protecting
anything the moment ids became stable — so the marker does the real work.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import underwriting_db as db

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "templates" / "tools" / "underwriting_detail.html"


class SaveExpensesCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "uw.db"
        self.patch = mock.patch.object(db, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with db.get_connection() as conn:
            self.sid = db.create_scenario(conn, {
                "property_label": "X", "name": "Base",
                "purchase_price": 5_000_000.0, "hold_years": 5})
            db.replace_expense_lines(conn, self.sid, [{
                "category_key": "taxes", "category_name": "Taxes",
                "gl_code": None, "label": "Property Tax",
                "line_kind": "operating", "annual_amount": 60_000.0,
                "growth_pct": 3.0, "is_included": 1, "growth_schedule": None}])
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        self.url = f"/tools/underwriting/scenario/{self.sid}/expenses"

    def row(self):
        with db.get_connection() as conn:
            return db.list_expense_lines(conn, self.sid)[0]

    def post(self, data):
        return self.client.post(self.url, data=data)


class AStaleRenderChangesNothingTests(SaveExpensesCase):
    def test_the_values_survive_a_save_that_never_mentioned_the_row(self):
        self.post({})
        row = self.row()
        self.assertEqual(row["annual_amount"], 60_000.0)
        self.assertEqual(row["growth_pct"], 3.0)
        self.assertTrue(row["is_included"])

    def test_the_line_still_counts_toward_noi(self):
        """is_included=False was the quiet part: the row stays, the money
        leaves, and the page shows a line that looks deliberately off."""
        self.post({})
        self.assertTrue(self.row()["is_included"])

    def test_the_row_is_not_deleted_either(self):
        self.post({})
        with db.get_connection() as conn:
            self.assertEqual(len(db.list_expense_lines(conn, self.sid)), 1)


class ExplicitValuesStillApplyTests(SaveExpensesCase):
    def test_an_edit_lands(self):
        lid = self.row()["id"]
        self.post({f"row_{lid}": "1", f"amount_{lid}": "70000",
                   f"growth_{lid}": "2.5", f"included_{lid}": "1"})
        row = self.row()
        self.assertEqual(row["annual_amount"], 70_000.0)
        self.assertEqual(row["growth_pct"], 2.5)
        self.assertTrue(row["is_included"])

    def test_unticking_a_rendered_row_really_excludes_it(self):
        """The case the marker exists for: a rendered row whose checkbox
        posts nothing is a deliberate no, not an omission."""
        lid = self.row()["id"]
        self.post({f"row_{lid}": "1", f"amount_{lid}": "60000",
                   f"growth_{lid}": "3.0"})
        self.assertFalse(self.row()["is_included"])

    def test_a_cleared_amount_still_clears(self):
        lid = self.row()["id"]
        self.post({f"row_{lid}": "1", f"amount_{lid}": "",
                   f"growth_{lid}": "3.0", f"included_{lid}": "1"})
        self.assertIsNone(self.row()["annual_amount"])

    def test_the_marker_alone_does_not_wipe_the_values(self):
        """A row marked rendered but carrying no value fields keeps them.

        Only the checkbox is gated on the marker; the text inputs are
        gated on their own presence, because a rendered text input always
        posts.
        """
        lid = self.row()["id"]
        self.post({f"row_{lid}": "1", f"included_{lid}": "1"})
        row = self.row()
        self.assertEqual(row["annual_amount"], 60_000.0)
        self.assertEqual(row["growth_pct"], 3.0)


class TheMarkerIsRenderedTests(unittest.TestCase):
    def test_the_template_emits_a_row_marker(self):
        src = TPL.read_text(encoding="utf-8")
        self.assertIn('name="row_{{ l.id }}"', src)

    def test_it_sits_with_the_checkbox_it_disambiguates(self):
        src = TPL.read_text(encoding="utf-8")
        marker = src.index('name="row_{{ l.id }}"')
        checkbox = src.index('name="included_{{ l.id }}"')
        self.assertLess(abs(checkbox - marker), 200,
                        "the marker must travel with the checkbox")

    def test_the_route_reads_the_marker(self):
        src = (ROOT / "tools" / "underwriting.py").read_text(encoding="utf-8")
        self.assertIn('rendered = f"row_{lid}" in request.form', src)


if __name__ == "__main__":
    unittest.main()

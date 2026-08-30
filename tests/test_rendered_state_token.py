"""Two tabs, one scenario, and the row that used to disappear.

The Part 52 deferral was written with a condition: build this **if
per-account data ships, OR more than one person can log in, OR any of
those three pages becomes part of a two-person workflow.** The second
fired on 2026-08-27 when a second account was created through the signup
form. The condition did its own job; this is the consequence.

THE HAZARD, EXACTLY

`save_loans`, `save_capex` and `save_gp_partners` each rewrite a whole
collection by DELETE-then-INSERT. A row absent from the post is destroyed.
That is CORRECT when the post is current -- it is how a user removes a row
-- and it is silent data loss when the post is stale:

    session A renders 3 loans
    session B adds a 4th and saves
    session A edits a rate and saves -> its post has 3 -> the 4th is gone

No error, no trace. `TwoSessionsTests` is that sequence.

WHY A CONTENT HASH AND NOT A LIST OF ROW IDS

Both reasons from Part 52 were re-checked against current code and both
still hold: the forms carry **no row identity** (loans and partners post
parallel `getlist` arrays, capex posts a loop index), and the **ids churn**
because every save is DELETE-then-INSERT. `IdChurnTests` pins the second,
because it is the reason the obvious design is impossible and it would be
easy to "simplify" this back into a manifest.

WHAT THIS DELIBERATELY DOES NOT DO

It does not merge. Two people editing one collection still cannot both
win; the loss becomes a refusal instead of a silence. And the refusing
route redirects, so the stale session loses its unsaved edits -- see
`TheRefusalCostsTests`, which pins that as a known and stated cost rather
than an oversight.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import investor_report_db as ir_db
from tools import rendered_state
from tools import underwriting_db as db


class TheTokenIgnoresIdsTests(unittest.TestCase):
    """`id` churns on every save. Hashing it would make a collection
    differ from itself and refuse every second save."""

    def test_the_same_content_hashes_the_same_under_different_ids(self):
        a = [{"id": 1, "sort_order": 0, "name": "Senior", "amount": 100.0}]
        b = [{"id": 99, "sort_order": 0, "name": "Senior", "amount": 100.0}]
        self.assertEqual(rendered_state.token(a), rendered_state.token(b))

    def test_a_changed_value_changes_the_token(self):
        a = [{"id": 1, "name": "Senior", "amount": 100.0}]
        b = [{"id": 1, "name": "Senior", "amount": 101.0}]
        self.assertNotEqual(rendered_state.token(a), rendered_state.token(b))

    def test_an_added_row_changes_the_token(self):
        a = [{"id": 1, "name": "Senior"}]
        b = [{"id": 1, "name": "Senior"}, {"id": 2, "name": "Mezz"}]
        self.assertNotEqual(rendered_state.token(a), rendered_state.token(b))

    def test_a_removed_row_changes_the_token(self):
        a = [{"id": 1, "name": "Senior"}, {"id": 2, "name": "Mezz"}]
        b = [{"id": 1, "name": "Senior"}]
        self.assertNotEqual(rendered_state.token(a), rendered_state.token(b))

    def test_reordering_changes_the_token(self):
        """These collections are ordered by sort_order and rendered in it.
        Two rows swapping places is a real edit."""
        a = [{"name": "Senior"}, {"name": "Mezz"}]
        b = [{"name": "Mezz"}, {"name": "Senior"}]
        self.assertNotEqual(rendered_state.token(a), rendered_state.token(b))

    def test_an_empty_collection_has_a_token(self):
        """A scenario with no loans is a real state that can be saved
        into and out of, so it needs a token like any other."""
        self.assertTrue(rendered_state.token([]))
        self.assertEqual(rendered_state.token([]), rendered_state.token(None))

    def test_a_new_column_makes_it_stricter_not_looser(self):
        """Everything but `id` is hashed, so a column added later is
        covered without anyone remembering to add it."""
        a = [{"id": 1, "name": "Senior"}]
        b = [{"id": 1, "name": "Senior", "new_column": "x"}]
        self.assertNotEqual(rendered_state.token(a), rendered_state.token(b))


class AbsentIsAMismatchTests(unittest.TestCase):
    def test_a_post_with_no_token_is_refused(self):
        rows = [{"id": 1, "name": "Senior"}]
        self.assertFalse(rendered_state.matches({}, rows))

    def test_an_empty_token_is_refused(self):
        rows = [{"id": 1, "name": "Senior"}]
        self.assertFalse(rendered_state.matches({rendered_state.FIELD: ""}, rows))

    def test_a_matching_token_passes(self):
        rows = [{"id": 1, "name": "Senior"}]
        form = {rendered_state.FIELD: rendered_state.token(rows)}
        self.assertTrue(rendered_state.matches(form, rows))

    def test_a_token_from_different_rows_is_refused(self):
        form = {rendered_state.FIELD: rendered_state.token([{"name": "Senior"}])}
        self.assertFalse(rendered_state.matches(form, [{"name": "Mezz"}]))


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p1 = mock.patch.object(db, "get_db_path", lambda: self.tmp / "uw.db")
        self.p2 = mock.patch.object(ir_db, "get_db_path", lambda: self.tmp / "ir.db")
        self.p1.start(); self.p2.start()
        self.addCleanup(self.p1.stop); self.addCleanup(self.p2.stop)
        with db.get_connection() as conn:
            self.sid = db.create_scenario(conn, {
                "property_label": "Nabob", "name": "Base",
                "purchase_price": 5_000_000.0, "hold_years": 5})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def loans(self):
        with db.get_connection() as conn:
            return db.list_loans(conn, self.sid)

    def set_loans(self, *specs):
        with db.get_connection() as conn:
            db.replace_loans(conn, self.sid, [
                {"sort_order": i, "name": n, "amount": a, "rate_pct": 5.0,
                 "amort_years": 30, "io_years": None}
                for i, (n, a) in enumerate(specs)])

    def post_loans(self, specs, token):
        data = {"_rendered_state": token}
        for key, values in (("loan_name", [n for n, _ in specs]),
                            ("loan_amount", [str(a) for _, a in specs]),
                            ("loan_rate_pct", ["5.0"] * len(specs)),
                            ("loan_amort_years", ["30"] * len(specs)),
                            ("loan_io_years", [""] * len(specs))):
            data[key] = values
        return self.client.post(
            f"/tools/underwriting/scenario/{self.sid}/loans", data=data,
            follow_redirects=True)


class TwoSessionsTests(RouteTestCase):
    """THE CASE THIS WAS BUILT FOR."""

    def test_the_stale_save_is_refused_and_the_new_row_survives(self):
        # Session A renders three loans and holds the token.
        self.set_loans(("Senior", 3_000_000.0), ("Mezz", 500_000.0),
                       ("Seller", 250_000.0))
        session_a_token = rendered_state.token(self.loans())

        # Session B adds a fourth and saves. (Done directly: it is the
        # other person's save, not the behaviour under test.)
        self.set_loans(("Senior", 3_000_000.0), ("Mezz", 500_000.0),
                       ("Seller", 250_000.0), ("Bridge", 100_000.0))
        self.assertEqual(len(self.loans()), 4)

        # Session A now saves its three, with an edited rate.
        body = self.post_loans([("Senior", 3_100_000.0), ("Mezz", 500_000.0),
                                ("Seller", 250_000.0)], session_a_token
                               ).get_data(as_text=True)

        names = [l["name"] for l in self.loans()]
        self.assertIn("Bridge", names, "the other session's loan was destroyed")
        self.assertEqual(len(self.loans()), 4)
        self.assertIn("older version of this list", body)

    def test_and_the_stale_edit_was_not_applied_either(self):
        """Refused means refused. A partial application would be worse
        than both alternatives."""
        self.set_loans(("Senior", 3_000_000.0))
        stale = rendered_state.token(self.loans())
        self.set_loans(("Senior", 3_000_000.0), ("Bridge", 100_000.0))
        self.post_loans([("Senior", 9_999_999.0)], stale)
        amounts = {l["name"]: l["amount"] for l in self.loans()}
        self.assertEqual(amounts["Senior"], 3_000_000.0)
        self.assertEqual(len(amounts), 2)

    def test_a_current_save_still_works(self):
        """POSITIVE CONTROL. Without this the guard could be refusing
        everything and every assertion above would still pass."""
        self.set_loans(("Senior", 3_000_000.0), ("Mezz", 500_000.0))
        current = rendered_state.token(self.loans())
        self.post_loans([("Senior", 3_100_000.0), ("Mezz", 500_000.0)], current)
        amounts = {l["name"]: l["amount"] for l in self.loans()}
        self.assertEqual(amounts["Senior"], 3_100_000.0)
        self.assertEqual(len(amounts), 2)

    def test_a_DELIBERATE_deletion_still_works(self):
        """The guard must not break the thing omission is FOR. A current
        post with a row removed still removes it."""
        self.set_loans(("Senior", 3_000_000.0), ("Mezz", 500_000.0))
        current = rendered_state.token(self.loans())
        self.post_loans([("Senior", 3_000_000.0)], current)
        self.assertEqual([l["name"] for l in self.loans()], ["Senior"])

    def test_emptying_the_stack_entirely_still_works(self):
        """Posting an empty stack returns the scenario to single-loan
        mode, and the route's docstring calls that the only way back."""
        self.set_loans(("Senior", 3_000_000.0))
        current = rendered_state.token(self.loans())
        self.post_loans([], current)
        self.assertEqual(self.loans(), [])


class IdChurnTests(RouteTestCase):
    """The reason a manifest of row ids is impossible, pinned so nobody
    'simplifies' the token back into one."""

    def test_ids_are_reassigned_by_a_save_that_changes_nothing(self):
        self.set_loans(("Senior", 3_000_000.0), ("Mezz", 500_000.0))
        before = [l["id"] for l in self.loans()]
        current = rendered_state.token(self.loans())
        self.post_loans([("Senior", 3_000_000.0), ("Mezz", 500_000.0)], current)
        after = [l["id"] for l in self.loans()]
        self.assertNotEqual(before, after, "ids no longer churn -- re-read Part 52")

    def test_but_the_token_is_unchanged_by_that_churn(self):
        """Which is the whole reason it hashes content and not ids."""
        self.set_loans(("Senior", 3_000_000.0))
        before = rendered_state.token(self.loans())
        current = before
        self.post_loans([("Senior", 3_000_000.0)], current)
        self.assertEqual(rendered_state.token(self.loans()), before)

    def test_a_second_consecutive_save_is_therefore_accepted(self):
        """If the token hashed ids, this is where it would break."""
        self.set_loans(("Senior", 3_000_000.0))
        for _ in range(3):
            token = rendered_state.token(self.loans())
            self.post_loans([("Senior", 3_000_000.0)], token)
        self.assertEqual(len(self.loans()), 1)


class TheFormsCarryTheTokenTests(unittest.TestCase):
    """A guard the page never sends is a guard that refuses everything."""

    ROOT = Path(__file__).resolve().parents[1] / "templates" / "tools"

    def test_all_three_forms_post_it(self):
        uw = (self.ROOT / "underwriting_detail.html").read_text(encoding="utf-8")
        ir = (self.ROOT / "investor_report_detail.html").read_text(encoding="utf-8")
        self.assertEqual(uw.count('name="_rendered_state"'), 2)
        self.assertEqual(ir.count('name="_rendered_state"'), 1)

    def test_the_field_name_matches_the_helper(self):
        uw = (self.ROOT / "underwriting_detail.html").read_text(encoding="utf-8")
        self.assertIn(f'name="{rendered_state.FIELD}"', uw)

    def test_each_form_gets_its_own_collections_token(self):
        uw = (self.ROOT / "underwriting_detail.html").read_text(encoding="utf-8")
        self.assertIn("{{ loans_state }}", uw)
        self.assertIn("{{ capex_state }}", uw)
        ir = (self.ROOT / "investor_report_detail.html").read_text(encoding="utf-8")
        self.assertIn("{{ partners_state }}", ir)


class OneHelperThreeCallSitesTests(unittest.TestCase):
    """Part 49 fixed the function it found; Part 51 found the same bug
    still live in a route it had not looked at. This is a class fix."""

    ROOT = Path(__file__).resolve().parents[1] / "tools"

    def test_every_guarded_route_calls_the_shared_helper(self):
        uw = (self.ROOT / "underwriting.py").read_text(encoding="utf-8")
        ir = (self.ROOT / "investor_report.py").read_text(encoding="utf-8")
        self.assertEqual(uw.count("rendered_state.matches("), 2)
        self.assertEqual(ir.count("rendered_state.matches("), 1)

    def test_none_of_them_reimplements_the_hash(self):
        for name in ("underwriting.py", "investor_report.py"):
            with self.subTest(module=name):
                src = (self.ROOT / name).read_text(encoding="utf-8")
                self.assertNotIn("hashlib", src)

    def test_they_all_use_the_same_message(self):
        for name in ("underwriting.py", "investor_report.py"):
            with self.subTest(module=name):
                src = (self.ROOT / name).read_text(encoding="utf-8")
                self.assertIn("rendered_state.STALE_MESSAGE", src)


class TheRefusalCostsTests(RouteTestCase):
    """A stated cost, not an oversight.

    The refusing routes redirect, so the stale session's unsaved edits are
    gone. `detail()` is 124 lines of context assembly and re-rendering it
    from a POST would mean rebuilding all of it -- and would show fresh
    data everywhere except the section the user edited, which is its own
    confusion. The same routes already lose the form on a validation
    refusal, so this matches the behaviour beside it rather than
    introducing a new one.
    """

    def test_the_refusal_redirects_rather_than_re_rendering(self):
        self.set_loans(("Senior", 3_000_000.0))
        stale = rendered_state.token(self.loans())
        self.set_loans(("Senior", 3_000_000.0), ("Bridge", 100_000.0))
        r = self.client.post(
            f"/tools/underwriting/scenario/{self.sid}/loans",
            data={"_rendered_state": stale, "loan_name": ["Senior"],
                  "loan_amount": ["3000000.0"], "loan_rate_pct": ["5.0"],
                  "loan_amort_years": ["30"], "loan_io_years": [""]},
            follow_redirects=False)
        self.assertEqual(r.status_code, 302)

    def test_nothing_was_written_before_the_refusal(self):
        """The important half: the cost falls on unsaved edits, never on
        stored data."""
        self.set_loans(("Senior", 3_000_000.0))
        stale = rendered_state.token(self.loans())
        self.set_loans(("Senior", 3_000_000.0), ("Bridge", 100_000.0))
        before = [(l["name"], l["amount"]) for l in self.loans()]
        self.post_loans([("Senior", 1.0)], stale)
        self.assertEqual([(l["name"], l["amount"]) for l in self.loans()], before)


if __name__ == "__main__":
    unittest.main()

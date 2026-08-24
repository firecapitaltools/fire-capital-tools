"""A field the page never rendered is not an instruction to erase it.

WHAT WENT WRONG

`_collect()` read every answer with `(form.get(field) or "").strip()`,
which treats a field the page **never rendered** exactly like one the
inspector **deliberately blanked**. `save_area` and `save_room` then
upsert with plain assignments (`condition = excluded.condition`), so a
save posted from a render that predated an item wrote `None` over a real
answer.

Demonstrated before the fix: `'repair'` and the inspector's own note
became `None`, while the $450 estimate survived — because `_kept_cost()`
already implemented "absent means unchanged" and `condition` did not.

**The money survived and the judgement did not**, and it got worse
downstream: a finding with no condition fails `uc.needs_work()`, so the
line dropped out of the capital budget **while keeping its cost** — not
shown as unpriced, simply absent.

WHY ABSENT AND EMPTY ARE SAFE TO DISTINGUISH

The condition group renders an explicit blank option (`value=""`, checked
when there is no current answer), so a **rendered** item always submits
its field. Field present and empty is a deliberate clear. Field absent
means the page did not render the item at all.

That distinction is what makes the fix safe, and it is asserted here
rather than assumed: clearing must still clear.

HOW A STALE RENDER HAPPENS

Not by losing signal — see `docs/site-dd-partial-post.md`. A dropped
connection cannot produce a partial write, 5,000 urlencoded fields arrive
intact, an oversized body returns 413, and the service worker bypasses
`/tools/` entirely. It happens because a **well-formed POST from an old
page** is an ordinary thing: the back button, or two tabs, or two devices.
"Michelle reviewing while MJ walks" is a described workflow, not a
hypothetical, and it has its own test below.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd as s
from tools import site_dd_bank as bank
from tools import site_dd_capex_export as capex
from tools import site_dd_costs as costs
from tools import site_dd_db as db
from tools import site_dd_unit_checklist as uc

ROOT = Path(__file__).resolve().parents[1]


class SiteDDCase(unittest.TestCase):
    """Each test gets its own database. Production is never opened."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        self.patch = mock.patch.object(db, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with db.get_connection() as conn:
            self.aid = db.create_assessment(conn, {
                "property_label": "Test", "assessed_on": "2026-08-24",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
            self.area = db.create_area(conn, self.aid, {"label": "Unit 1"})
        self.items = list(uc.items_for_unit())
        self.item = self.items[0]
        self.key = self.item["key"]

    def save(self, form):
        with db.get_connection() as conn:
            db.upsert_findings(conn, self.aid, s._collect(
                form, self.items, scope="unit", area_id=self.area,
                room_id=None,
                existing=db.get_findings(conn, self.aid, self.area, None)))

    def row(self, key=None):
        with db.get_connection() as conn:
            found = db.get_findings(conn, self.aid, self.area, None)
        rows = found.get(key or self.key) or []
        return rows[0] if rows else None

    def answer(self, **over):
        form = {f"condition_{self.key}": "repair",
                f"note_{self.key}": "cracked tile by the door",
                f"cost_{self.key}": "450"}
        form.update(over)
        return form


class AStaleRenderNoLongerErasesTests(SiteDDCase):
    def test_the_answer_survives_a_save_that_never_mentioned_it(self):
        self.save(self.answer())
        self.assertEqual(self.row()["condition"], "repair")

        # A well-formed POST from a page rendered before this item existed.
        # Nothing malformed, nothing truncated -- it simply says nothing
        # about this item.
        self.save({f"condition_{self.items[1]['key']}": "good"})

        self.assertEqual(self.row()["condition"], "repair")
        self.assertEqual(self.row()["note"], "cracked tile by the door")

    def test_the_estimate_and_its_provenance_still_survive(self):
        """These already survived; the fix must not regress them."""
        self.save(self.answer())
        self.save({})
        self.assertEqual(self.row()["est_unit_cost"], 450.0)
        self.assertEqual(self.row()["est_cost_source"], costs.SOURCE_MANUAL)

    def test_the_row_is_never_deleted(self):
        self.save(self.answer())
        before = self.row()["id"]
        self.save({})
        self.assertEqual(self.row()["id"], before)


class ClearingStillClearsTests(SiteDDCase):
    """The fix must not make an answer impossible to remove.

    The blank radio is how an inspector says "I was wrong, this is not a
    repair". It posts the field with an empty value, which is a different
    statement from not posting it.
    """

    def test_an_explicit_blank_clears_the_condition(self):
        self.save(self.answer())
        self.assertEqual(self.row()["condition"], "repair")
        self.save({f"condition_{self.key}": ""})
        self.assertIsNone(self.row()["condition"])

    def test_an_explicit_blank_clears_the_note(self):
        self.save(self.answer())
        self.save({f"note_{self.key}": ""})
        self.assertIsNone(self.row()["note"])

    def test_a_changed_answer_still_changes(self):
        self.save(self.answer())
        self.save({f"condition_{self.key}": "good"})
        self.assertEqual(self.row()["condition"], "good")

    def test_an_invalid_value_still_becomes_none(self):
        """A hand-crafted POST cannot invent an answer."""
        self.save(self.answer())
        self.save({f"condition_{self.key}": "immaculate"})
        self.assertIsNone(self.row()["condition"])


class TwoTabsTests(SiteDDCase):
    """Michelle reviewing while MJ walks. A described workflow.

    Both have the unit open. MJ answers an item; Michelle's tab was
    rendered before that and knows nothing about it. Michelle saves.
    """

    def test_the_second_tab_does_not_erase_the_first(self):
        mj_tab = self.answer()
        michelle_tab = {f"condition_{self.items[1]['key']}": "good"}

        self.save(mj_tab)                      # MJ records the repair
        self.save(michelle_tab)                # Michelle saves a stale render

        self.assertEqual(self.row()["condition"], "repair",
                         "MJ's finding must survive Michelle's stale save")
        self.assertEqual(self.row()["note"], "cracked tile by the door")
        self.assertEqual(self.row(self.items[1]["key"])["condition"], "good",
                         "and Michelle's own answer must still land")

    def test_neither_tab_wins_by_being_last(self):
        """Each save owns the fields it carries and nothing else."""
        self.save({f"condition_{self.key}": "repair"})
        self.save({f"condition_{self.items[1]['key']}": "replace"})
        self.save({f"condition_{self.items[2]['key']}": "good"})
        self.assertEqual(self.row()["condition"], "repair")
        self.assertEqual(self.row(self.items[1]["key"])["condition"], "replace")
        self.assertEqual(self.row(self.items[2]["key"])["condition"], "good")


class ItStaysInTheCapitalBudgetTests(SiteDDCase):
    """The downstream consequence, which is worse than the row suggests.

    A null condition fails needs_work(), so before the fix a blanked
    finding left the budget entirely while keeping its estimate.
    """

    def budget_lines(self):
        with db.get_connection() as conn:
            findings = db.list_all_findings(conn, self.aid)
        catalogue = bank.every_item()
        work = [f for f in findings
                if uc.needs_work(catalogue.get(f.get("item_key")),
                                 f.get("condition"), f.get("detail"))]
        priced = [costs.apply_reference(f, None) for f in work]
        return capex.build_lines(priced, {self.key: "Test item"})

    def test_the_finding_is_in_the_budget_after_a_stale_save(self):
        self.save(self.answer())
        self.assertEqual(len(self.budget_lines()), 1)

        self.save({})   # stale render, says nothing about the item

        lines = self.budget_lines()
        self.assertEqual(len(lines), 1,
                         "the line must not vanish from the budget")
        self.assertEqual(lines[0]["unit_cost"], 450.0,
                         "and it must keep its estimate")


class TheStaleFormHeaderIsScopedTests(unittest.TestCase):
    """no-store on the pages that render whole-set forms, and nowhere else."""

    def setUp(self):
        from app import app
        self.app = app
        self.src = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_the_listed_endpoints_are_the_whole_set_form_pages(self):
        block = self.src[self.src.index("STALE_FORM_ENDPOINTS"):]
        block = block[:block.index("@app.after_request")]
        for endpoint in ("site_dd.area_detail", "site_dd.room_detail",
                         "underwriting.detail"):
            self.assertIn(endpoint, block)

    def test_every_listed_endpoint_actually_exists(self):
        """A stale entry would silently protect nothing."""
        known = {r.endpoint for r in self.app.url_map.iter_rules()}
        for endpoint in ("site_dd.area_detail", "site_dd.room_detail",
                         "underwriting.detail"):
            self.assertIn(endpoint, known)

    def test_it_is_no_store_not_no_cache(self):
        """no-cache still permits the back/forward cache to restore it."""
        block = self.src[self.src.index("def no_store_on_editable_forms"):]
        block = block[:block.index("return response")]
        self.assertIn("no-store", block)

    def test_the_header_actually_fires_on_a_real_response(self):
        """Asserted on the response, not on the source that produces it."""
        from flask import Response, request
        seen = {}
        for endpoint in ("site_dd.area_detail", "underwriting.detail",
                         "site_dd.index"):
            with self.app.test_request_context("/"):
                request.url_rule = type("R", (), {"endpoint": endpoint})()
                seen[endpoint] = self.app.process_response(
                    Response("x")).headers.get("Cache-Control")
        self.assertEqual(seen["site_dd.area_detail"], "no-store, max-age=0")
        self.assertEqual(seen["underwriting.detail"], "no-store, max-age=0")
        self.assertIsNone(seen["site_dd.index"],
                          "read-only pages must not be forced to revalidate")

    def test_static_assets_are_untouched(self):
        """Blanket no-store would break the installable PWA."""
        client = self.app.test_client()
        resp = client.get("/static/style.css")
        self.assertNotIn("no-store", resp.headers.get("Cache-Control", ""))

    def test_the_service_worker_shell_is_untouched(self):
        client = self.app.test_client()
        resp = client.get("/service-worker.js")
        self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")


if __name__ == "__main__":
    unittest.main()


class ThePropertyScopeGetsTheSameRuleTests(unittest.TestCase):
    """site_dd.save is the route the Part 49 fix missed.

    It has its own inline collection loop rather than calling _collect(),
    so scoping that fix to the function left this one with the collapsing
    read. Part 51 demonstrated it still blanking `condition`, `note` and
    `overall_notes`.

    The two loops now share `_kept_field()` and its wrappers. They do NOT
    share the loop, deliberately: the property scope has no detail, no
    quantity and no bank item, and bending one loop around fields it does
    not have is how a shared helper becomes worse than two that agree.
    What is shared is the semantics, which is the part that diverged.
    """

    def setUp(self):
        from tools import site_dd_checklist as cl
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        self.patch = mock.patch.object(db, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with db.get_connection() as conn:
            self.aid = db.create_assessment(conn, {
                "property_label": "P", "assessed_on": "2026-08-24",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
        self.key = cl.ITEM_KEYS[0]
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        self.url = f"/tools/site-dd/assessment/{self.aid}/save"

    def post(self, **extra):
        data = {"property_label": "P", "assessed_on": "2026-08-24",
                "inspector": "MJ", "status": "draft"}
        data.update(extra)
        return self.client.post(self.url, data=data)

    def state(self):
        with db.get_connection() as conn:
            rows = db.get_findings(conn, self.aid, None, None).get(self.key) or [{}]
            assessment = db.get_assessment(conn, self.aid)
        return rows[0], assessment

    def answer(self):
        self.post(**{f"condition_{self.key}": "repair",
                     f"note_{self.key}": "ponding at the drain",
                     "overall_notes": "walked the roof"})

    def test_the_answer_lands(self):
        self.answer()
        row, assessment = self.state()
        self.assertEqual(row["condition"], "repair")
        self.assertEqual(row["note"], "ponding at the drain")
        self.assertEqual(assessment["overall_notes"], "walked the roof")

    def test_a_stale_render_preserves_all_three(self):
        self.answer()
        self.post()          # says nothing about the item or the notes
        row, assessment = self.state()
        self.assertEqual(row["condition"], "repair")
        self.assertEqual(row["note"], "ponding at the drain")
        self.assertEqual(assessment["overall_notes"], "walked the roof",
                         "the summary of the whole walk must survive")

    def test_an_explicit_clear_still_clears_all_three(self):
        self.answer()
        self.post(**{f"condition_{self.key}": "", f"note_{self.key}": "",
                     "overall_notes": ""})
        row, assessment = self.state()
        self.assertIsNone(row["condition"])
        self.assertIsNone(row["note"])
        self.assertIsNone(assessment["overall_notes"])

    def test_the_property_label_is_not_reset_to_untitled(self):
        """A missing label used to become 'Untitled', renaming the walk."""
        self.answer()
        self.client.post(self.url, data={"status": "draft"})
        _, assessment = self.state()
        self.assertEqual(assessment["property_label"], "P")


class TheTwoCollectorsShareTheirSemanticsTests(unittest.TestCase):
    """The class-level guarantee, not the route-level one.

    Part 49 fixed the function it found. This asserts both callers go
    through one implementation, so a third collector inherits the rule
    instead of having to remember it.
    """

    def setUp(self):
        self.src = (ROOT / "tools" / "site_dd.py").read_text(encoding="utf-8")

    def test_the_shared_helper_exists(self):
        self.assertIn("def _kept_field(", self.src)

    def test_neither_loop_reads_a_condition_directly(self):
        """`(form.get(...) or "").strip()` on a condition is the bug."""
        self.assertNotIn('(request.form.get(f"condition_', self.src)
        self.assertNotIn('(form.get(f"condition_', self.src)

    def test_both_loops_call_the_shared_wrapper(self):
        self.assertEqual(self.src.count("_kept_condition("), 3,
                         "one definition plus two call sites")
        self.assertEqual(self.src.count("_kept_note("), 3)

"""Which job, on the six items whose condition cannot say.

Michelle: *"I agree with your assessment. We should be more detailed on
what needs to be replaced or repaired."*

Steps 1-3 of `docs/site-dd-detail-values.md`. `detail` gains a second
population: on `KIND_CHOICE` items it holds a PRESENCE fact (what is it,
is it there), and now on six `KIND_CONDITION` items it holds a SCOPE fact
(the condition says work is needed; this says which work).

SIX, NOT THE NINE THE DESIGN LISTED

`appliance_disposal`, `washer` and `dryer` are `KIND_CHOICE` and already
use `detail` for presence, so a scope detail there is the collision the
design's own partition argument says is impossible. They need no schema
change at all -- they carry `with_condition=True`, so jammed/not-working
and service/replace are already separated by the condition -- and they
are routed to step 5, which is where `for_item()` learns to consult the
condition and where budget figures move. The document is corrected.

WHAT MUST NOT MOVE

Assessment 11 is read-only production data whose one work item is a
`walls_ceiling` repair, and `walls_ceiling` is one of the six. Its
finding carries no detail, which must go on meaning "the default job" and
must go on pricing at the researched $5.75/sqft.
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_bank as bank
from tools import site_dd_capex_export as capex
from tools import site_dd_checklist as cl
from tools import site_dd_conditions as cond
from tools import site_dd_costs as costs
from tools import site_dd_db as db
from tools import site_dd_reference_costs as refcosts
from tools import site_dd_unit_checklist as uc

SIX = ("closet", "toilet", "tub_shower", "walls_ceiling",
       "entry_door", "dryer_vent")
THE_THREE_DEFERRED = ("appliance_disposal", "washer", "dryer")
TPL = Path(__file__).resolve().parents[1] / "templates" / "tools"


class TheSixHaveScopeOptionsTests(unittest.TestCase):
    def setUp(self):
        self.items = bank.every_item()

    def test_each_is_a_condition_item_with_options(self):
        for key in SIX:
            with self.subTest(key=key):
                item = self.items[key]
                self.assertEqual(item["kind"], uc.KIND_CONDITION)
                self.assertTrue(item["options"])

    def test_each_still_offers_a_condition(self):
        """The scope is a follow-up, never a replacement. If
        with_condition went false the item would stop asking whether
        there is work at all."""
        for key in SIX:
            with self.subTest(key=key):
                self.assertTrue(self.items[key]["with_condition"])

    def test_no_scope_value_is_a_work_condition_string(self):
        """needs_work() rule 3 returns True for a detail that IS a work
        condition. A scope says WHICH job, never WHETHER there is one, so
        tripping that rule would let a detail alone create a budget line."""
        for key in SIX:
            for value, _ in self.items[key]["options"]:
                with self.subTest(key=key, value=value):
                    self.assertNotIn(value, cond.WORK_CONDITIONS)

    def test_every_scope_set_is_registered_as_implying_no_work(self):
        for key in SIX:
            options = tuple(self.items[key]["options"])
            with self.subTest(key=key):
                self.assertIn(options, uc.WORK_OPTIONS)
                self.assertEqual(uc.WORK_OPTIONS[options], frozenset())

    def test_a_scope_detail_alone_is_not_work(self):
        for key in SIX:
            item = self.items[key]
            for value, _ in item["options"]:
                with self.subTest(key=key, value=value):
                    self.assertFalse(uc.needs_work(item, None, value))

    def test_positive_control_the_condition_still_decides(self):
        """Without this, the assertions above would pass on a needs_work()
        broken into always returning False."""
        for key in SIX:
            item = self.items[key]
            self.assertTrue(uc.needs_work(item, "replace", None))
            self.assertTrue(uc.needs_work(item, "repair", None))
            self.assertFalse(uc.needs_work(item, "good", None))

    def test_the_labels_reach_the_export(self):
        labels = bank.detail_labels()
        for key in SIX:
            for value, label in self.items[key]["options"]:
                with self.subTest(key=key, value=value):
                    self.assertEqual(labels[(key, value)], label)


class TheThreeDeferredAreUntouchedTests(unittest.TestCase):
    """They are choice items whose detail is presence. If this branch had
    given them a scope set, it would have overwritten that meaning."""

    def setUp(self):
        self.items = bank.every_item()

    def test_they_are_still_choice_items_with_presence_options(self):
        for key in THE_THREE_DEFERRED:
            with self.subTest(key=key):
                item = self.items[key]
                self.assertEqual(item["kind"], uc.KIND_CHOICE)
                self.assertEqual(tuple(item["options"]), uc.PRESENCE)

    def test_their_presence_answers_still_imply_work(self):
        for key in THE_THREE_DEFERRED:
            item = self.items[key]
            with self.subTest(key=key):
                self.assertTrue(uc.needs_work(item, None, "absent"))
                self.assertTrue(uc.needs_work(item, None, "hookup_only"))


class NoItemKeyWritesDetailUnderTwoMeaningsTests(unittest.TestCase):
    """The design's real claim, checked against the catalogue AS IT
    STANDS rather than as it stood when the design was written.

    Checked on the EFFECTIVE kind. Room and unit items carry `kind`; the
    twenty bank items carry `default_kind`, so a check written against
    `kind` alone silently examines a fraction of the catalogue and reports
    success -- which is exactly what happened the first time.
    """

    def definitions(self):
        """Every definition from every source, WITHOUT dedup."""
        out = {}
        def add(key, kind, has_options, where):
            out.setdefault(key, []).append((where, kind, has_options))
        for room_type, _ in uc.ROOM_TYPES:
            for it in uc.items_for_room(room_type):
                add(it["key"], it.get("kind"), bool(it.get("options")),
                    "room:" + room_type)
        for it in uc.items_for_unit():
            add(it["key"], it.get("kind"), bool(it.get("options")), "unit")
        for it in getattr(bank, "BANK_ITEMS", ()):
            add(it["key"], it.get("default_kind"), bool(it.get("options")), "bank")
        for key in cl.ITEM_KEYS:
            add(key, uc.KIND_CONDITION, False, "property")
        return out

    def test_the_population_is_the_whole_catalogue(self):
        """ASSERT THE SIZE BEFORE ASSERTING ANYTHING ABOUT THE CONTENTS.

        A partition check over a third of the definitions is not a
        partition check, and it passes."""
        defs = self.definitions()
        total = sum(len(v) for v in defs.values())
        self.assertGreater(len(defs), 80, "too few keys -- a source is missing")
        self.assertGreater(total, 150, "too few definitions -- a source is missing")
        sources = {d[0].split(":")[0] for ds in defs.values() for d in ds}
        self.assertEqual(sources, {"room", "unit", "bank", "property"})

    def test_no_definition_has_an_unknown_kind(self):
        """`None` here means a source names the field differently, which
        is the bug that made the first check vacuous."""
        for key, ds in self.definitions().items():
            for where, kind, _ in ds:
                with self.subTest(key=key, where=where):
                    self.assertIn(kind, (uc.KIND_CONDITION, uc.KIND_CHOICE,
                                         uc.KIND_NUMBER))

    def test_no_key_writes_detail_under_two_meanings(self):
        """The claim the design actually rests on.

        A key may appear with two kinds -- pest_evidence is choice in nine
        room checklists and a condition item in the property checklist --
        and that is harmless because property scope never writes detail.
        What must not happen is one key carrying OPTIONS under two
        different kinds, because then `detail` would mean two things.
        """
        offenders = {}
        for key, ds in self.definitions().items():
            kinds_with_options = {kind for _, kind, has in ds if has}
            if len(kinds_with_options) > 1:
                offenders[key] = ds
        self.assertEqual(offenders, {}, f"detail is ambiguous for: {offenders}")

    def test_the_known_two_kind_key_is_still_only_pest_evidence(self):
        """Pinned so a second one is noticed rather than absorbed."""
        both = {key for key, ds in self.definitions().items()
                if len({d[1] for d in ds}) > 1}
        self.assertEqual(both, {"pest_evidence"})

    def test_property_scope_writes_no_detail(self):
        """Which is what makes pest_evidence harmless. Read from the
        route, not from memory."""
        src = (Path(uc.__file__).parent / "site_dd.py").read_text(encoding="utf-8")
        body = src[src.index("def save(assessment_id)"):]
        body = body[:body.index("def ", 10)]
        self.assertNotIn('"detail"', body)


class TheWriteRuleTests(unittest.TestCase):
    """A scope detail is dropped unless the condition says there is a job."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        self.patch = mock.patch.object(db, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with db.get_connection() as conn:
            self.aid = db.create_assessment(conn, {
                "property_label": "Nabob", "assessed_on": "2026-08-29",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
            self.area_id = db.create_area(conn, self.aid,
                                          {"kind": "unit", "label": "101"})
            self.room_id = db.create_room(conn, self.area_id, "bathroom", "Bath")
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def save(self, **fields):
        return self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}"
            f"/rooms/{self.room_id}/save", data=fields)

    def toilet(self):
        with db.get_connection() as conn:
            rows = db.get_findings(conn, self.aid, self.area_id, self.room_id)
        return (rows.get("toilet") or [{}])[0]

    def test_a_scope_is_stored_when_the_condition_is_work(self):
        self.save(condition_toilet="replace", detail_toilet="replace_seat")
        row = self.toilet()
        self.assertEqual(row["condition"], "replace")
        self.assertEqual(row["detail"], "replace_seat")

    def test_repair_also_counts_as_work(self):
        self.save(condition_toilet="repair", detail_toilet="replace_seat")
        self.assertEqual(self.toilet()["detail"], "replace_seat")

    def test_a_scope_is_DROPPED_when_the_condition_is_not_work(self):
        self.save(condition_toilet="good", detail_toilet="replace_seat")
        row = self.toilet()
        self.assertEqual(row["condition"], "good")
        self.assertIsNone(row["detail"])

    def test_changing_the_condition_to_good_clears_a_stored_scope(self):
        """The absent-means-unchanged path. A form that posts a new
        condition and no detail field must not keep a stale scope."""
        self.save(condition_toilet="replace", detail_toilet="replace_seat")
        self.assertEqual(self.toilet()["detail"], "replace_seat")
        self.save(condition_toilet="good")
        self.assertIsNone(self.toilet()["detail"])

    def test_an_invented_value_is_refused(self):
        self.save(condition_toilet="replace", detail_toilet="gold_plated")
        self.assertIsNone(self.toilet()["detail"])

    def test_no_scope_at_all_is_a_normal_state(self):
        self.save(condition_toilet="replace")
        row = self.toilet()
        self.assertEqual(row["condition"], "replace")
        self.assertIsNone(row["detail"])

    def test_a_choice_items_presence_detail_is_NOT_dropped(self):
        """The rule must not reach choice items. An absent dishwasher is
        absent whatever its condition says."""
        self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}/save",
            data={"label": "101", "status": "occupied", "notes": "",
                  "detail_smoke_alarm_unit": "missing"})
        with db.get_connection() as conn:
            rows = db.get_findings(conn, self.aid, self.area_id, None)
        row = (rows.get("smoke_alarm_unit") or [{}])[0]
        self.assertEqual(row.get("detail"), "missing")


class ExistingFindingsMeanTheDefaultJobTests(unittest.TestCase):
    """Assessment 11's shape, which is the case that must not move."""

    def line(self, detail=None):
        row = {"item_key": "walls_ceiling", "scope": "room",
               "condition": "repair", "detail": detail, "instance_no": 1,
               "instance_label": None, "measure": None, "quantity": None,
               "category_key": "interior_units",
               "est_unit_cost": None, "est_cost_source": costs.SOURCE_NONE}
        lines = capex.build_lines([costs.apply_reference(row, None)],
                                  dict(cl.ITEM_LABELS),
                                  detail_labels=bank.detail_labels())
        self.assertEqual(len(lines), 1)
        return lines[0]

    def test_no_detail_still_prices_at_the_researched_rate(self):
        line = self.line(None)
        self.assertEqual(line["unit_cost"], 5.75)
        self.assertEqual(line["source"], costs.SOURCE_REFERENCE)
        self.assertEqual(line["unit"], refcosts.UNIT_SQFT)
        self.assertIsNone(line["total"])

    def test_a_scope_detail_does_not_change_the_price_yet(self):
        """COST_BY_DETAIL carries no new entries: this branch ships the
        capture, not the figures. Step 5 is where prices move."""
        for value, _ in bank.every_item()["walls_ceiling"]["options"]:
            with self.subTest(value=value):
                self.assertEqual(self.line(value)["unit_cost"], 5.75)

    def test_the_item_is_still_a_rate(self):
        self.assertTrue(self.line(None)["is_rate"])


class TheFormAsksOnlyWhereThereIsAJobTests(unittest.TestCase):
    def markup(self, name):
        raw = (TPL / name).read_text(encoding="utf-8")
        return re.sub(r"\{#.*?#\}", " ", raw, flags=re.S)

    def test_both_capture_templates_render_the_picker(self):
        for name in ("site_dd_room.html", "site_dd_area.html"):
            with self.subTest(template=name):
                m = self.markup(name)
                self.assertIn("scope_row(item", m)
                self.assertIn("sdd-scope-row", m)

    def test_it_offers_an_explicit_unselected_state(self):
        for name in ("site_dd_room.html", "site_dd_area.html"):
            with self.subTest(template=name):
                self.assertIn('value="" {% if not current %}checked{% endif %}',
                              self.markup(name))

    def test_the_reveal_is_css_and_defaults_to_visible(self):
        """Hidden-by-default would make the feature invisible on a browser
        without :has(). The degraded state must be 'always asked'."""
        css = (TPL.parents[1] / "static" / "style.css").read_text(encoding="utf-8")
        rule = css[css.index(".sdd-item:has("):]
        self.assertIn(":not([value=\"repair\"])", rule)
        self.assertIn(":not([value=\"replace\"])", rule)
        self.assertNotIn(".sdd-scope-row { display: none; }", css)

    def test_no_javascript_is_involved(self):
        for name in ("site_dd_room.html", "site_dd_area.html"):
            with self.subTest(template=name):
                m = self.markup(name)
                block = m[m.index("scope_row"):m.index("scope_row") + 1600]
                self.assertNotIn("onchange", block)
                self.assertNotIn("<script", block)


if __name__ == "__main__":
    unittest.main()

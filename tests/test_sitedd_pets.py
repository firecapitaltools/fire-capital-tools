"""Pets at the door — two fields, and three ways they could go wrong.

Michelle: *"One other field I'd like to include are two extra fields for
1) pets present; 2) how many pets. These two would be done early on when
the inspector walks into the door."*

WHERE THEY LIVE, AND WHY IT IS NOT THE CHECKLIST

"When the inspector walks into the door" is a unit-level fact recorded at
the start of a walk, so they are columns on `site_dd_areas` beside
`status` and `notes`, rendered in the unit header above the room list.

That placement is also the whole of the "must not reach the capital
budget" requirement. The budget is built from `site_dd_findings`; area
columns are a different table that `build_lines()` never reads. A
checklist item would have put a dog in the same table as a broken
water heater and left `needs_work()` as the only thing standing between
it and a repair line — a registry entry somebody must remember to
maintain. This way it is structural.

THE THREE HAZARDS, EACH WITH A TEST BELOW

* **Falsy zero.** Zero pets and no answer are different facts. The
  handoff records this class already: `bedrooms or '—'` rendered a studio
  as unknown.
* **Reaching the budget.** Checked from both ends — no finding row
  mentions a pet and no budget line is produced, and `needs_work()` is
  asked directly what it does with an item of this shape. Note the
  findings table is NOT empty: saving a unit upserts the whole unit-wide
  checklist, which it did before this change too.
* **A raw key on screen.** The fifth label map, reached through an
  accessor, per the four that came before it.
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_bank as bank
from tools import site_dd_capex_export as capex
from tools import site_dd_checklist as cl
from tools import site_dd_costs as costs
from tools import site_dd_db as db
from tools import site_dd_unit_checklist as uc

AREA_TPL = Path(__file__).resolve().parents[1] / "templates" / "tools" / "site_dd_area.html"


class PetCountKeepsItsZeroTests(unittest.TestCase):
    """`int(value or 0)` would collapse "" and 0 into the same thing."""

    def test_zero_is_an_answer(self):
        self.assertEqual(db.clean_pet_count("0"), 0)
        self.assertEqual(db.clean_pet_count(0), 0)

    def test_unanswered_is_none(self):
        self.assertIsNone(db.clean_pet_count(""))
        self.assertIsNone(db.clean_pet_count("   "))
        self.assertIsNone(db.clean_pet_count(None))

    def test_and_those_two_are_not_the_same(self):
        """The assertion that actually states the requirement."""
        self.assertIsNot(db.clean_pet_count("0"), db.clean_pet_count(""))
        self.assertNotEqual(db.clean_pet_count("0"), db.clean_pet_count(""))

    def test_a_real_count_survives(self):
        self.assertEqual(db.clean_pet_count("3"), 3)
        self.assertEqual(db.clean_pet_count(" 2 "), 2)

    def test_nonsense_is_none_not_an_error(self):
        for value in ("-1", "abc", "999", db.MAX_PET_COUNT + 1):
            with self.subTest(value=value):
                self.assertIsNone(db.clean_pet_count(value))

    def test_the_ceiling_itself_is_allowed(self):
        self.assertEqual(db.clean_pet_count(db.MAX_PET_COUNT), db.MAX_PET_COUNT)


class PetsPresentHasThreeStatesTests(unittest.TestCase):
    def test_yes_and_no_are_both_answers(self):
        self.assertEqual(db.clean_pets_present("yes"), "yes")
        self.assertEqual(db.clean_pets_present("no"), "no")

    def test_unanswered_is_none(self):
        self.assertIsNone(db.clean_pets_present(None))
        self.assertIsNone(db.clean_pets_present(""))

    def test_an_unknown_value_does_not_become_an_answer(self):
        self.assertIsNone(db.clean_pets_present("maybe"))

    def test_no_is_distinguishable_from_unanswered(self):
        self.assertIsNotNone(db.clean_pets_present("no"))


class TheFifthLabelMapTests(unittest.TestCase):
    """Four label maps already exist for one reason: a stored key must not
    reach a screen. This is the fifth."""

    def test_every_stored_value_has_a_label(self):
        for value in db.PETS_VALUES:
            with self.subTest(value=value):
                self.assertIn(value, db.PETS_LABELS)

    def test_unset_reads_as_a_statement_not_a_gap(self):
        self.assertEqual(db.pets_present_label(None), "Not stated")

    def test_a_stale_value_reads_as_not_stated_rather_than_raw(self):
        self.assertEqual(db.pets_present_label("from_an_older_vocabulary"),
                         "Not stated")

    def test_no_label_is_the_raw_key(self):
        """`|title` on the stored value is what the map replaces."""
        for value, label in db.PETS_LABELS.items():
            with self.subTest(value=value):
                self.assertNotEqual(label, value)

    def test_the_template_calls_the_accessor_not_the_map(self):
        markup = re.sub(r"\{#.*?#\}", " ", AREA_TPL.read_text(encoding="utf-8"),
                        flags=re.S)
        self.assertIn("pets_present_label(", markup)
        self.assertNotIn("PETS_LABELS[", markup)
        self.assertNotIn("area.pets_present|title", markup)


class ItIsNotACostItemTests(unittest.TestCase):
    """Checked from BOTH ends: what the registry would do with an item of
    this shape, and what the budget actually receives."""

    def test_needs_work_says_no_to_an_item_of_this_shape(self):
        """A choice item whose options are yes/no, asked directly.

        This is the item that was NOT built -- pets live on the area, not
        in the checklist -- but the question was worth settling, because
        it is the shape somebody will reach for next time.
        """
        item = {"key": "pets_present", "kind": uc.KIND_CHOICE,
                "options": (("yes", "Pets"), ("no", "No pets"))}
        for detail in ("yes", "no", None):
            with self.subTest(detail=detail):
                self.assertFalse(uc.needs_work(item, None, detail))

    def test_a_pet_count_shaped_number_item_is_not_work_either(self):
        item = {"key": "pet_count", "kind": uc.KIND_NUMBER, "measure": None}
        for detail in (None, "0", "3"):
            with self.subTest(detail=detail):
                self.assertFalse(uc.needs_work(item, None, detail))

    def test_positive_control_needs_work_does_say_yes_to_real_work(self):
        """Without this, the two assertions above would pass if
        needs_work() had been broken into always returning False."""
        self.assertTrue(uc.needs_work(None, "replace", None))
        alarm = {"key": "smoke_alarm", "kind": uc.KIND_CHOICE,
                 "options": uc.ALARM_STATES}
        self.assertTrue(uc.needs_work(alarm, None, "missing"))

    def test_an_unregistered_options_tuple_defaults_to_no_work(self):
        """`WORK_OPTIONS.get(key, frozenset())` -- an option set nobody
        registered cannot imply a cost by accident."""
        self.assertNotIn((("yes", "Pets"), ("no", "No pets")), uc.WORK_OPTIONS)


class NothingReachesTheBudgetTests(unittest.TestCase):
    """The structural claim, exercised through the real route."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        self.patch = mock.patch.object(db, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with db.get_connection() as conn:
            self.aid = db.create_assessment(conn, {
                "property_label": "Nabob", "assessed_on": "2026-08-26",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
            self.area_id = db.create_area(conn, self.aid, {
                "kind": "unit", "label": "101", "status": "occupied"})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def save(self, **extra):
        data = {"label": "101", "status": "occupied", "notes": ""}
        data.update(extra)
        return self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}/save",
            data=data)

    def area(self):
        with db.get_connection() as conn:
            return db.get_area(conn, self.area_id)

    def budget(self):
        with db.get_connection() as conn:
            findings = db.list_all_findings(conn, self.aid)
        catalogue = bank.every_item()
        work = [f for f in findings
                if uc.needs_work(catalogue.get(f.get("item_key")),
                                 f.get("condition"), f.get("detail"))]
        return capex.build_lines([costs.apply_reference(f, None) for f in work],
                                 dict(cl.ITEM_LABELS))

    def test_three_dogs_produce_no_budget_line(self):
        self.save(pets_present="yes", pet_count="3")
        self.assertEqual(self.area()["pet_count"], 3)
        self.assertEqual(self.budget(), [])

    def test_no_finding_MENTIONS_pets(self):
        """Different table, which is the whole argument.

        Not "no findings exist" -- saving a unit upserts the whole
        unit-wide checklist, so ten empty rows are normal and were there
        before this change. The claim is that none of them is about a pet,
        and that no pets value is stored anywhere in that table.
        """
        self.save(pets_present="yes", pet_count="3")
        with db.get_connection() as conn:
            findings = db.list_all_findings(conn, self.aid)
        self.assertTrue(findings, "no findings at all -- this test is vacuous")
        for row in findings:
            with self.subTest(item=row["item_key"]):
                self.assertNotIn("pet", (row["item_key"] or "").lower())
                self.assertNotIn("pet", str(row["detail"] or "").lower())
        self.assertNotIn("3", [str(r["detail"]) for r in findings])

    def test_the_columns_are_not_on_the_findings_table(self):
        with db.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(site_dd_findings)")}
        self.assertNotIn("pets_present", cols)
        self.assertNotIn("pet_count", cols)


class ThroughTheRealFormTests(NothingReachesTheBudgetTests):
    def test_a_counted_zero_round_trips(self):
        self.save(pets_present="no", pet_count="0")
        row = self.area()
        self.assertEqual(row["pet_count"], 0)
        self.assertEqual(row["pets_present"], "no")

    def test_an_unanswered_count_stays_null(self):
        self.save(pets_present="", pet_count="")
        row = self.area()
        self.assertIsNone(row["pet_count"])
        self.assertIsNone(row["pets_present"])

    def test_zero_and_unanswered_are_stored_differently(self):
        self.save(pets_present="no", pet_count="0")
        counted = self.area()["pet_count"]
        self.save(pets_present="", pet_count="")
        unanswered = self.area()["pet_count"]
        self.assertEqual(counted, 0)
        self.assertIsNone(unanswered)

    def test_a_form_that_never_rendered_them_does_not_blank_them(self):
        """ABSENT MEANS UNCHANGED.

        The unit form renders both fields, so this is not reachable
        today -- but the fields are new, and any older cached page or
        future partial post would otherwise wipe a count somebody walked
        into a flat to establish. Same rule _kept_field() applies to
        findings.
        """
        self.save(pets_present="yes", pet_count="2")
        self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}/save",
            data={"label": "101", "status": "occupied", "notes": "roof leak"})
        row = self.area()
        self.assertEqual(row["pet_count"], 2, "a partial post blanked the count")
        self.assertEqual(row["pets_present"], "yes")
        self.assertEqual(row["notes"], "roof leak", "the post did not take effect")

    def test_but_an_explicit_clear_still_clears(self):
        """The counterpart. Absent means unchanged; empty means cleared,
        and without this the field could never be corrected."""
        self.save(pets_present="yes", pet_count="2")
        self.save(pets_present="", pet_count="")
        row = self.area()
        self.assertIsNone(row["pet_count"])
        self.assertIsNone(row["pets_present"])

    def test_the_page_renders_both_fields(self):
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}"
        ).get_data(as_text=True)
        self.assertIn('name="pets_present"', body)
        self.assertIn('name="pet_count"', body)

    def test_a_counted_zero_is_not_rendered_as_an_empty_box(self):
        self.save(pets_present="no", pet_count="0")
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}"
        ).get_data(as_text=True)
        box = re.search(r'name="pet_count"[^>]*value="([^"]*)"', body)
        self.assertIsNotNone(box, "the count input lost its value attribute")
        self.assertEqual(box.group(1), "0")

    def test_an_unanswered_count_renders_empty(self):
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}/areas/{self.area_id}"
        ).get_data(as_text=True)
        box = re.search(r'name="pet_count"[^>]*value="([^"]*)"', body)
        self.assertEqual(box.group(1), "")

    def test_the_assessment_page_shows_it_too(self):
        self.save(pets_present="yes", pet_count="2")
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)
        self.assertIn("Pets", body)


class TheMigrationIsAdditiveTests(unittest.TestCase):
    """A database written before these columns existed must still open."""

    def test_an_older_database_gains_the_columns(self):
        tmp = Path(tempfile.mkdtemp()) / "old.db"
        import sqlite3
        conn = sqlite3.connect(tmp)
        conn.executescript(
            """CREATE TABLE site_dd_areas (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   assessment_id INTEGER NOT NULL,
                   kind TEXT NOT NULL DEFAULT 'common',
                   label TEXT NOT NULL, status TEXT,
                   sort_order INTEGER NOT NULL DEFAULT 0,
                   notes TEXT, created_at TEXT NOT NULL);
               INSERT INTO site_dd_areas
                   (assessment_id, kind, label, status, sort_order, notes, created_at)
               VALUES (1, 'unit', '101', 'occupied', 0, 'walked', '2026-01-01');""")
        conn.commit()
        conn.close()
        with mock.patch.object(db, "get_db_path", lambda: tmp):
            with db.get_connection() as c:
                row = dict(c.execute(
                    "SELECT * FROM site_dd_areas WHERE label='101'").fetchone())
        self.assertIn("pets_present", row)
        self.assertIn("pet_count", row)
        self.assertIsNone(row["pets_present"])
        self.assertIsNone(row["pet_count"])
        self.assertEqual(row["notes"], "walked", "the pre-existing row changed")


if __name__ == "__main__":
    unittest.main()

"""Applying a seed — all of it, or none of it.

152 areas and 894 rooms against a platform whose largest assessment holds
2 areas and 1 room, with **no platform backup** behind it (known-issues 3).
So the properties tested here are not "does it work" but:

* **partial success is impossible** — a seed that dies after 80 units
  leaves 80 areas the next reconcile would faithfully preserve, turning
  the rule that protects inspectors into the thing that entrenches damage;
* **the snapshot is taken by the code**, not by an operator remembering;
* **a lost response is visible on retry**, because otherwise a commit
  whose reply never arrived looks exactly like a no-op;
* **the undo reaches only what the seed created**, and refuses when
  somebody has since walked those rooms.

The figures are checked against the PREVIEW's figures, not against
numbers typed here. If the write and the preview disagree, the preview was
wrong — and the preview is the screen a person approves.
"""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import rendered_state
from tools import site_dd_db as sdb
from tools import site_dd_seed_write as sw
from tools import site_dd_seeding as seed

TABLES = ("site_dd_assessments", "site_dd_areas", "site_dd_rooms",
          "site_dd_findings", "site_dd_media")


def fingerprint(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    blob = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
            for t in TABLES}
    conn.close()
    return (sum(len(v) for v in blob.values()),
            hashlib.sha256(json.dumps(blob, sort_keys=True, default=str)
                           .encode()).hexdigest()[:16])


def unit(label, unit_type="2/1.5 RENOVATED", status="C", **kw):
    row = {"unit": label, "unit_type": unit_type, "sqft": 825.0,
           "status": status, "move_out": None}
    row.update(kw)
    return row


class SeedTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.db = self.dir / "site_dd.db"
        self.patch = mock.patch.object(sdb, "get_db_path", lambda: self.db)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "Oxford Pointe", "assessed_on": "2026-08-30",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})

    def plan_for(self, rows):
        plan = seed.plan_units(rows)
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            rooms = {a["id"]: sdb.list_rooms(conn, a["id"]) for a in areas}
            finds = {a["id"]: sdb.area_finding_rows(conn, a["id"]) for a in areas}
        return plan, seed.plan_reconcile(plan, areas, rooms, finds)

    def token(self):
        with sdb.get_connection() as conn:
            return {rendered_state.FIELD:
                    rendered_state.token(sdb.list_areas(conn, self.aid))}

    def counts(self):
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            rooms = sum(len(sdb.list_rooms(conn, a["id"])) for a in areas)
            finds = len(sdb.list_all_findings(conn, self.aid))
        return len(areas), rooms, finds


class TheMigrationTests(SeedTestCase):
    def test_both_tables_carry_seed_batch(self):
        with sdb.get_connection() as conn:
            for t in ("site_dd_areas", "site_dd_rooms"):
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
                with self.subTest(table=t):
                    self.assertIn("seed_batch", cols)

    def test_a_hand_made_area_carries_NULL(self):
        """Which is what makes the undo safe by construction."""
        with sdb.get_connection() as conn:
            area = sdb.create_area(conn, self.aid, {"kind": "unit", "label": "1"})
            sdb.create_room(conn, area, "kitchen", None)
            self.assertIsNone(sdb.get_area(conn, area)["seed_batch"])
            self.assertIsNone(sdb.list_rooms(conn, area)[0]["seed_batch"])


class TheWriteMatchesThePreviewTests(SeedTestCase):
    """If these disagree the PREVIEW was wrong, and the preview is what a
    person approves."""

    def rows(self):
        return [unit(f"{100 + i}", "2/1.5 RENOVATED") for i in range(20)]

    def test_areas_and_rooms_match_the_reconcile(self):
        plan, rec = self.plan_for(self.rows())
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertEqual(out["created_areas"], rec["create_count"])
        self.assertEqual(out["created_rooms"], rec["rooms_appended"])

    def test_the_database_agrees_with_what_was_reported(self):
        plan, rec = self.plan_for(self.rows())
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        areas, rooms, _ = self.counts()
        self.assertEqual(areas, out["created_areas"])
        self.assertEqual(rooms, out["created_rooms"])

    def test_status_and_notes_are_written(self):
        plan, rec = self.plan_for([
            unit("640", "1/1 CLASSIC", status="NTV", move_out="2026-08-13"),
            unit("212", "2/1.5 CLASSIC", status="")])
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        with sdb.get_connection() as conn:
            by_label = {a["label"]: a for a in sdb.list_areas(conn, self.aid)}
        self.assertEqual(by_label["640"]["status"], sdb.AREA_OCCUPIED)
        self.assertEqual(by_label["640"]["notes"], "Notice to vacate 2026-08-13")
        self.assertEqual(by_label["212"]["status"], sdb.AREA_VACANT)
        self.assertIsNone(by_label["212"]["notes"])

    def test_the_half_bath_keeps_its_label(self):
        plan, rec = self.plan_for([unit("110", "2/1.5 RENOVATED")])
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        with sdb.get_connection() as conn:
            area = sdb.list_areas(conn, self.aid)[0]
            rooms = sdb.list_rooms(conn, area["id"])
        baths = [r for r in rooms if r["room_type"] == "bathroom"]
        self.assertEqual([b["label"] for b in baths], [None, seed.HALF_BATH_LABEL])

    def test_every_written_row_carries_the_batch(self):
        plan, rec = self.plan_for(self.rows())
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            self.assertTrue(all(a["seed_batch"] == out["batch"] for a in areas))
            for a in areas:
                for r in sdb.list_rooms(conn, a["id"]):
                    self.assertEqual(r["seed_batch"], out["batch"])


class PartialSuccessIsImpossibleTests(SeedTestCase):
    def test_a_failure_midway_leaves_NOTHING(self):
        """Not 'few rows'. Zero. 80 orphan areas would be preserved by the
        next reconcile as though somebody had made them."""
        plan, rec = self.plan_for([unit(f"{100 + i}") for i in range(30)])
        before = fingerprint(self.db)
        boom = list(rec["areas"])
        real_append = sw._append_rooms
        calls = {"n": 0}

        def exploding(conn, area_id, wanted, have, batch):
            calls["n"] += 1
            if calls["n"] > 10:
                raise RuntimeError("disk went away")
            return real_append(conn, area_id, wanted, have, batch)

        with mock.patch.object(sw, "_append_rooms", exploding):
            with self.assertRaises(RuntimeError):
                sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertEqual(self.counts(), (0, 0, 0))
        self.assertEqual(fingerprint(self.db), before)

    def test_positive_control_it_would_have_written_without_the_failure(self):
        plan, rec = self.plan_for([unit(f"{100 + i}") for i in range(30)])
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertEqual(self.counts()[0], 30)


class TheSnapshotIsTakenByTheCodeTests(SeedTestCase):
    def test_a_snapshot_exists_after_a_seed(self):
        plan, rec = self.plan_for([unit("110")])
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertTrue(Path(out["snapshot"]).exists())

    def test_it_holds_the_state_from_BEFORE_the_write(self):
        before = fingerprint(self.db)
        plan, rec = self.plan_for([unit(f"{100 + i}") for i in range(10)])
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertEqual(fingerprint(Path(out["snapshot"])), before)
        self.assertNotEqual(fingerprint(self.db), before)

    def test_restoring_it_undoes_the_whole_seed(self):
        """The rollback, end to end, using the runbook's own procedure."""
        import shutil
        before = fingerprint(self.db)
        plan, rec = self.plan_for([unit(f"{100 + i}") for i in range(10)])
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        shutil.copy2(out["snapshot"], self.db)
        self.assertEqual(fingerprint(self.db), before)

    def test_it_is_not_optional(self):
        """No argument turns it off. A rollback that depends on somebody
        opting in is not a rollback."""
        import inspect
        sig = inspect.signature(sw.apply_seed)
        self.assertNotIn("snapshot", sig.parameters)
        self.assertIn("take_snapshot", inspect.getsource(sw.apply_seed))


class IdempotenceTests(SeedTestCase):
    def test_seeding_twice_gives_152_not_304(self):
        rows = [unit(f"{100 + i}") for i in range(40)]
        plan, rec = self.plan_for(rows)
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        first = self.counts()
        plan2, rec2 = self.plan_for(rows)       # reconciled against reality
        sw.apply_seed(self.aid, plan2, rec2, form=self.token())
        self.assertEqual(self.counts(), first)

    def test_the_second_run_creates_nothing(self):
        rows = [unit(f"{100 + i}") for i in range(40)]
        plan, rec = self.plan_for(rows)
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        plan2, rec2 = self.plan_for(rows)
        out = sw.apply_seed(self.aid, plan2, rec2, form=self.token())
        self.assertEqual((out["created_areas"], out["created_rooms"]), (0, 0))
        self.assertEqual(out["reused_areas"], 40)

    def test_a_lost_response_is_VISIBLE_on_retry(self):
        """The commit landed, the reply did not. Without this the retry
        reports 'all reused, nothing created', which is true and reads
        exactly like nothing happened."""
        rows = [unit(f"{100 + i}") for i in range(10)]
        plan, rec = self.plan_for(rows)
        first = sw.apply_seed(self.aid, plan, rec, form=self.token())
        plan2, rec2 = self.plan_for(rows)
        retry = sw.apply_seed(self.aid, plan2, rec2, form=self.token())
        self.assertEqual(retry["previously_seeded"], [first["batch"]])

    def test_a_first_run_reports_no_prior_batches(self):
        plan, rec = self.plan_for([unit("110")])
        self.assertEqual(
            sw.apply_seed(self.aid, plan, rec, form=self.token())["previously_seeded"],
            [])


class TwoSimultaneousSeedsTests(SeedTestCase):
    """The Part 67 problem, using the Part 67 helper."""

    def test_a_stale_token_is_refused_and_writes_nothing(self):
        rows = [unit(f"{100 + i}") for i in range(5)]
        plan, rec = self.plan_for(rows)
        stale = self.token()
        with sdb.get_connection() as conn:            # somebody else acts
            sdb.create_area(conn, self.aid, {"kind": "unit", "label": "999"})
        before = self.counts()
        with self.assertRaises(sw.SeedRefused):
            sw.apply_seed(self.aid, plan, rec, form=stale)
        self.assertEqual(self.counts(), before)

    def test_the_refusal_tells_the_user_what_happened(self):
        plan, rec = self.plan_for([unit("110")])
        stale = self.token()
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid, {"kind": "unit", "label": "999"})
        with self.assertRaises(sw.SeedRefused) as caught:
            sw.apply_seed(self.aid, plan, rec, form=stale)
        self.assertIn("older version", str(caught.exception))

    def test_positive_control_a_current_token_applies(self):
        plan, rec = self.plan_for([unit("110")])
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertEqual(self.counts()[0], 1)


class TheUndoTests(SeedTestCase):
    def seeded(self, n=10):
        plan, rec = self.plan_for([unit(f"{100 + i}") for i in range(n)])
        return sw.apply_seed(self.aid, plan, rec, form=self.token())

    def test_undo_returns_the_database_to_its_pre_seed_content(self):
        before = fingerprint(self.db)
        out = self.seeded()
        sw.undo_seed(self.aid, out["batch"])
        self.assertEqual(fingerprint(self.db), before)

    def test_it_reports_what_it_removed(self):
        out = self.seeded()
        undone = sw.undo_seed(self.aid, out["batch"])
        self.assertEqual(undone["deleted_areas"], out["created_areas"])
        self.assertEqual(undone["deleted_rooms"], out["created_rooms"])

    def test_it_cannot_touch_a_hand_made_area(self):
        with sdb.get_connection() as conn:
            mine = sdb.create_area(conn, self.aid,
                                   {"kind": "unit", "label": "BY HAND"})
            sdb.create_room(conn, mine, "kitchen", None)
        out = self.seeded()
        sw.undo_seed(self.aid, out["batch"])
        with sdb.get_connection() as conn:
            labels = [a["label"] for a in sdb.list_areas(conn, self.aid)]
            self.assertEqual(labels, ["BY HAND"])
            self.assertEqual(len(sdb.list_rooms(conn, mine)), 1)

    def test_it_leaves_a_reused_areas_own_rooms_alone(self):
        """The seed appended; the undo removes only what it appended."""
        with sdb.get_connection() as conn:
            mine = sdb.create_area(conn, self.aid, {"kind": "unit", "label": "110"})
            sdb.create_room(conn, mine, "kitchen", None)
        plan, rec = self.plan_for([unit("110", "2/1.5 RENOVATED")])
        out = sw.apply_seed(self.aid, plan, rec, form=self.token())
        self.assertEqual(out["created_areas"], 0)
        self.assertEqual(out["created_rooms"], 5)
        sw.undo_seed(self.aid, out["batch"])
        with sdb.get_connection() as conn:
            rooms = sdb.list_rooms(conn, mine)
        self.assertEqual([r["room_type"] for r in rooms], ["kitchen"])

    def test_it_REFUSES_when_somebody_has_walked_a_seeded_room(self):
        out = self.seeded()
        with sdb.get_connection() as conn:
            area = sdb.list_areas(conn, self.aid)[0]
            room = sdb.list_rooms(conn, area["id"])[0]
            sdb.upsert_findings(conn, self.aid, [{
                "scope": "room", "area_id": area["id"], "room_id": room["id"],
                "category_key": "interior_units", "item_key": "flooring",
                "instance_no": 1, "condition": "repair", "detail": None,
                "note": "carpet is shot", "quantity": None, "measure": None,
                "est_unit_cost": None, "est_cost_source": "none",
                "instance_label": None, "bank_item_key": None}])
        before = self.counts()
        with self.assertRaises(sw.UndoRefused) as caught:
            sw.undo_seed(self.aid, out["batch"])
        self.assertEqual(self.counts(), before)
        message = str(caught.exception)
        self.assertIn(str(room["id"]), message)
        self.assertIn("1 finding", message)
        self.assertIn("restore-runbook", message)

    def test_the_refusal_names_the_rooms_rather_than_counting_them(self):
        out = self.seeded()
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)[:2]
            rooms = [sdb.list_rooms(conn, a["id"])[0] for a in areas]
            sdb.upsert_findings(conn, self.aid, [{
                "scope": "room", "area_id": a["id"], "room_id": r["id"],
                "category_key": "interior_units", "item_key": "flooring",
                "instance_no": 1, "condition": "repair", "detail": None,
                "note": None, "quantity": None, "measure": None,
                "est_unit_cost": None, "est_cost_source": "none",
                "instance_label": None, "bank_item_key": None}
                for a, r in zip(areas, rooms)])
        with self.assertRaises(sw.UndoRefused) as caught:
            sw.undo_seed(self.aid, out["batch"])
        for r in rooms:
            self.assertIn(str(r["id"]), str(caught.exception))


if __name__ == "__main__":
    unittest.main()


class TheFindingsPreservedNumberTests(SeedTestCase):
    """It is the reassurance on the screen where a 152-unit write is
    approved, and it was wrong: `area_finding_count` filters
    `condition IS NOT NULL`, so an area holding 23 rows with 2 answers
    reported 2 preserved. Understating what is protected is the wrong
    direction to be wrong in."""

    def area_with_mixed_findings(self):
        with sdb.get_connection() as conn:
            area = sdb.create_area(conn, self.aid, {"kind": "unit", "label": "1"})
            room = sdb.create_room(conn, area, "kitchen", None)
            rows = []
            for i in range(15):          # answered: a real walk
                rows.append({"scope": "room", "area_id": area, "room_id": room,
                             "category_key": "interior_units",
                             "item_key": f"answered_{i}", "instance_no": 1,
                             "condition": "repair", "detail": None,
                             "note": None, "quantity": None, "measure": None,
                             "est_unit_cost": None, "est_cost_source": "none",
                             "instance_label": None, "bank_item_key": None})
            for i in range(8):           # unanswered rows, one carrying a note
                rows.append({"scope": "unit", "area_id": area, "room_id": None,
                             "category_key": "interior_units",
                             "item_key": f"unanswered_{i}", "instance_no": 1,
                             "condition": None, "detail": None,
                             "note": "smells damp" if i == 0 else None,
                             "quantity": None, "measure": None,
                             "est_unit_cost": None, "est_cost_source": "none",
                             "instance_label": None, "bank_item_key": None})
            sdb.upsert_findings(conn, self.aid, rows)
        return area

    def test_the_two_counts_differ_and_that_is_the_bug(self):
        area = self.area_with_mixed_findings()
        with sdb.get_connection() as conn:
            self.assertEqual(sdb.area_finding_count(conn, area), 15)
            self.assertEqual(sdb.area_finding_rows(conn, area), 23)

    def test_the_reconcile_reports_EVERY_row_as_preserved(self):
        area = self.area_with_mixed_findings()
        plan = seed.plan_units([unit("1", "2/1.5 RENOVATED")])
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            rooms = {a["id"]: sdb.list_rooms(conn, a["id"]) for a in areas}
            finds = {a["id"]: sdb.area_finding_rows(conn, a["id"]) for a in areas}
        rec = seed.plan_reconcile(plan, areas, rooms, finds)
        self.assertEqual(rec["areas"][0].findings_preserved, 23)
        self.assertEqual(rec["findings_preserved"], 23)

    def test_and_the_write_really_does_preserve_all_23(self):
        """The number and the reality, checked against each other rather
        than the number being trusted."""
        area = self.area_with_mixed_findings()
        plan = seed.plan_units([unit("1", "2/1.5 RENOVATED")])
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            rooms = {a["id"]: sdb.list_rooms(conn, a["id"]) for a in areas}
            finds = {a["id"]: sdb.area_finding_rows(conn, a["id"]) for a in areas}
        rec = seed.plan_reconcile(plan, areas, rooms, finds)
        promised = rec["findings_preserved"]
        sw.apply_seed(self.aid, plan, rec, form=self.token())
        with sdb.get_connection() as conn:
            actually = len(sdb.list_all_findings(conn, self.aid))
        self.assertEqual(promised, actually)
        self.assertEqual(actually, 23)

    def test_an_unanswered_row_carrying_a_note_is_somebodys_work(self):
        """The reason the answered-only count is the wrong instrument: a
        row can hold a note, a cost or a measurement with no condition."""
        area = self.area_with_mixed_findings()
        with sdb.get_connection() as conn:
            notes = [f for f in sdb.list_all_findings(conn, self.aid)
                     if f["note"] and f["condition"] is None]
        self.assertTrue(notes)

    def test_the_preview_route_uses_the_row_count(self):
        """COMMENTS STRIPPED FIRST. The route's own comment explains that
        it used to call `area_finding_count`, so a raw substring search
        finds the explanation rather than a call -- the collision this
        codebase has hit repeatedly. Checked on the AST."""
        import ast, inspect, textwrap
        from tools import site_dd
        tree = ast.parse(textwrap.dedent(inspect.getsource(site_dd.seed_preview)))
        called = {getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                  for n in ast.walk(tree) if isinstance(n, ast.Call)}
        self.assertIn("area_finding_rows", called)
        self.assertNotIn("area_finding_count", called)

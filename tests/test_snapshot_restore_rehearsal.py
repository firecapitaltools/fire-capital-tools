"""Restoring `site_dd.db` from a `VACUUM INTO` snapshot — rehearsed, not assumed.

**This is the gate on the seeding write.** With `maxBackupsCount: 0` on the
Hobby plan there is no platform backup, so the pre-write snapshot is not a
supplement to infrastructure recovery — it is the whole of it. An untested
snapshot is a belief, which is the standard that kept known-issue 1 open
until Beckett's account settled it by ordinary use.

THREE FAILURE SHAPES A BAD SEED WOULD ACTUALLY PRODUCE

1. **Extra areas** — 152 units written where none should have been. A
   `seed_batch` undo handles this: every row it made carries the marker.
2. **Rooms appended to an existing area** — the reconcile's shortfall
   rule, applied to an area it should not have matched. The appended rooms
   carry the marker, so the undo reaches them.
3. **A WRONG REUSE** — an existing area matched by `unit_key` and
   *modified in place*: its label, status or notes overwritten. **No batch
   marker exists**, because the area was not created by the seed. The
   `seed_batch` undo cannot touch it and must not try.

**(3) is the case this file exists to prove.** It is the one where the
snapshot is the only layer that recovers anything, and the claim has never
been tested.

WHAT A REHEARSAL CAN AND CANNOT ESTABLISH

It establishes that the snapshot round-trips: content identical, findings
intact, wrong reuse undone. It cannot establish what happens to a request
in flight during a restore on the live container — that needs production
and production is not available for it. Recorded as a limitation in
`docs/site-dd-restore-runbook.md` rather than glossed.
"""

import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_db as sdb

TABLES = ("site_dd_assessments", "site_dd_areas", "site_dd_rooms",
          "site_dd_findings", "site_dd_media")


def fingerprint(path):
    """Content, not bytes.

    A byte hash is the wrong instrument here and the reason is recorded in
    HANDOFF: `VACUUM INTO` rewrites the file, so page layout, free pages
    and the rowid ordering on disk can differ while every row is
    identical. Byte equality would fail on a correct restore and send
    somebody hunting a defect that is not there.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    blob = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
            for t in TABLES}
    conn.close()
    return (sum(len(v) for v in blob.values()),
            hashlib.sha256(json.dumps(blob, sort_keys=True, default=str)
                           .encode()).hexdigest()[:16])


def snapshot(source: Path, dest: Path) -> Path:
    """The pre-write snapshot, exactly as the runbook specifies it.

    `VACUUM INTO` and not `shutil.copy`: it is transaction-consistent by
    construction. A file copy of a live SQLite database can catch it
    mid-write, and while `journal=delete` + `synchronous=FULL` makes that
    recoverable, "recoverable" is a weaker promise than "consistent" and
    this is the one place not to accept the weaker one.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()
    return dest


def restore(snap: Path, target: Path) -> None:
    """Put the snapshot back. The runbook's step 4."""
    shutil.copy2(snap, target)


class RehearsalTestCase(unittest.TestCase):
    """A scratch database with real-shaped content."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.db = self.dir / "site_dd.db"
        self.patch = mock.patch.object(sdb, "get_db_path", lambda: self.db)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "Nabob Hill", "assessed_on": "2026-08-30",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
            self.areas = {}
            for label in ("110", "111", "226 W/D"):
                area = sdb.create_area(conn, self.aid, {
                    "kind": "unit", "label": label, "status": "occupied",
                    "notes": f"walked {label}"})
                self.areas[label] = area
                for rt in ("living", "kitchen", "bedroom"):
                    sdb.create_room(conn, area, rt, None)
            # Findings on the reused area, which is the case that matters.
            rooms = sdb.list_rooms(conn, self.areas["226 W/D"])
            sdb.upsert_findings(conn, self.aid, [
                {"scope": "room", "area_id": self.areas["226 W/D"],
                 "room_id": rooms[1]["id"], "category_key": "interior_units",
                 "item_key": f"item_{i}", "instance_no": 1,
                 "condition": "repair", "detail": None, "note": f"note {i}",
                 "quantity": None, "measure": None, "est_unit_cost": None,
                 "est_cost_source": "none", "instance_label": None,
                 "bank_item_key": None}
                for i in range(15)])
        self.before = fingerprint(self.db)

    def counts(self):
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        n = tuple(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("site_dd_areas", "site_dd_rooms", "site_dd_findings"))
        conn.close()
        return n


class ThePreconditionTests(RehearsalTestCase):
    """If the fixture were empty every restore below would pass trivially."""

    def test_the_scratch_database_has_real_shaped_content(self):
        areas, rooms, findings = self.counts()
        self.assertEqual((areas, rooms, findings), (3, 9, 15))

    def test_the_fingerprint_is_not_degenerate(self):
        rows, digest = self.before
        self.assertEqual(rows, 3 + 9 + 15 + 1)      # + the assessment
        self.assertEqual(len(digest), 16)


class TheSnapshotRoundTripsTests(RehearsalTestCase):
    def test_a_snapshot_of_an_unchanged_database_matches_it(self):
        snap = snapshot(self.db, self.dir / "snap" / "site_dd.snap.db")
        self.assertEqual(fingerprint(snap), self.before)

    def test_the_snapshot_is_a_separate_file(self):
        snap = snapshot(self.db, self.dir / "snap" / "site_dd.snap.db")
        self.assertTrue(snap.exists())
        self.assertNotEqual(snap.resolve(), self.db.resolve())
        self.assertGreater(snap.stat().st_size, 0)

    def test_writing_after_the_snapshot_does_not_change_it(self):
        """The snapshot is a point in time, not a live view."""
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid, {"kind": "unit", "label": "999"})
        self.assertEqual(fingerprint(snap), self.before)
        self.assertNotEqual(fingerprint(self.db), self.before)


class ABadSeedIsUndoneTests(RehearsalTestCase):
    """The three failure shapes, each mutated destructively then restored."""

    def seed_gone_wrong(self):
        """Extra areas, rooms appended to an existing one, AND a wrong
        reuse that overwrites a real area in place."""
        with sdb.get_connection() as conn:
            for i in range(152):
                sdb.create_area(conn, self.aid,
                                {"kind": "unit", "label": f"seed{i}"})
            # (2) rooms appended to an area that already existed
            for rt in ("bathroom", "bathroom", "living"):
                sdb.create_room(conn, self.areas["110"], rt, None)
            # (3) THE WRONG REUSE: an existing area modified in place.
            sdb.update_area(conn, self.areas["226 W/D"], {
                "label": "226", "status": "vacant",
                "notes": "Rent roll status: overwritten"})

    def test_the_mutation_really_damages_it(self):
        """POSITIVE CONTROL. A restore that 'works' on an unchanged
        database proves nothing."""
        self.seed_gone_wrong()
        self.assertNotEqual(fingerprint(self.db), self.before)
        areas, rooms, _ = self.counts()
        self.assertEqual(areas, 3 + 152)
        self.assertEqual(rooms, 9 + 3)

    def test_restoring_returns_the_exact_prior_content(self):
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        self.seed_gone_wrong()
        restore(snap, self.db)
        self.assertEqual(fingerprint(self.db), self.before)

    def test_the_extra_areas_are_gone(self):
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        self.seed_gone_wrong()
        restore(snap, self.db)
        self.assertEqual(self.counts(), (3, 9, 15))

    def test_the_appended_rooms_are_gone(self):
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        self.seed_gone_wrong()
        restore(snap, self.db)
        with sdb.get_connection() as conn:
            rooms = sdb.list_rooms(conn, self.areas["110"])
        self.assertEqual([r["room_type"] for r in rooms],
                         ["living", "kitchen", "bedroom"])

    def test_THE_WRONG_REUSE_IS_UNDONE(self):
        """The case the seed_batch undo cannot reach, because the area
        carries no marker — it was modified, not created."""
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        self.seed_gone_wrong()
        with sdb.get_connection() as conn:
            damaged = sdb.get_area(conn, self.areas["226 W/D"])
        self.assertEqual(damaged["label"], "226")
        self.assertEqual(damaged["status"], "vacant")

        restore(snap, self.db)

        with sdb.get_connection() as conn:
            healed = sdb.get_area(conn, self.areas["226 W/D"])
        self.assertEqual(healed["label"], "226 W/D")
        self.assertEqual(healed["status"], "occupied")
        self.assertEqual(healed["notes"], "walked 226 W/D")

    def test_the_findings_on_the_reused_area_survive_intact(self):
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        self.seed_gone_wrong()
        restore(snap, self.db)
        with sdb.get_connection() as conn:
            findings = sdb.list_all_findings(conn, self.aid)
        self.assertEqual(len(findings), 15)
        self.assertEqual({f["note"] for f in findings},
                         {f"note {i}" for i in range(15)})

    def test_a_seed_batch_undo_could_NOT_have_fixed_the_reuse(self):
        """States the gap the snapshot exists to cover, rather than
        leaving it as prose in a design document.

        REVISITED 2026-08-30, exactly as this test asked to be. It was
        written before `seed_batch` existed and asserted the column was
        absent, with a note saying to come back if areas ever carried a
        marker. They do now, so the real property is pinned instead of
        the proxy -- and the real property is stronger:

        **A REUSED AREA'S `seed_batch` IS NULL.** The seed did not create
        it, so it carries no marker, so `DELETE ... WHERE seed_batch = ?`
        cannot reach it. It is indistinguishable from an area a person
        edited by hand, which is exactly why the undo must not guess and
        why only a point-in-time copy recovers it.
        """
        from tools import site_dd_seed_write as sw
        from tools import site_dd_seeding as seeding
        from tools import rendered_state

        plan = seeding.plan_units([{"unit": "110", "unit_type": "2/1.5 RENOVATED",
                                    "sqft": 825.0, "status": "C",
                                    "move_out": None}])
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            rooms = {a["id"]: sdb.list_rooms(conn, a["id"]) for a in areas}
            finds = {a["id"]: sdb.area_finding_rows(conn, a["id"]) for a in areas}
            form = {rendered_state.FIELD: rendered_state.token(areas)}
        rec = seeding.plan_reconcile(plan, areas, rooms, finds)
        out = sw.apply_seed(self.aid, plan, rec, form=form)

        # 110 already existed, so it was REUSED rather than created.
        self.assertEqual(out["created_areas"], 0)
        with sdb.get_connection() as conn:
            reused = sdb.get_area(conn, self.areas["110"])
        self.assertIsNone(reused["seed_batch"],
                          "a reused area must carry no batch marker")

        # So the undo leaves the area itself entirely alone.
        sw.undo_seed(self.aid, out["batch"])
        with sdb.get_connection() as conn:
            still = sdb.get_area(conn, self.areas["110"])
        self.assertIsNotNone(still, "the undo deleted a reused area")
        self.assertEqual(still["label"], "110")


class RestoringIsNotItselfReversibleTests(RehearsalTestCase):
    """The runbook's first step, demonstrated rather than asserted."""

    def test_restoring_an_old_snapshot_discards_current_work(self):
        old = snapshot(self.db, self.dir / "snap" / "old.db")
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid,
                            {"kind": "unit", "label": "REAL NEW WORK"})
        after_work = fingerprint(self.db)
        restore(old, self.db)
        self.assertEqual(fingerprint(self.db), self.before)
        self.assertNotEqual(fingerprint(self.db), after_work)

    def test_which_is_why_you_snapshot_BEFORE_restoring(self):
        """Take a fresh snapshot first and the discarded work is
        recoverable; skip it and it is gone."""
        old = snapshot(self.db, self.dir / "snap" / "old.db")
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid,
                            {"kind": "unit", "label": "REAL NEW WORK"})
        current = snapshot(self.db, self.dir / "snap" / "before-restore.db")
        after_work = fingerprint(self.db)

        restore(old, self.db)
        self.assertEqual(fingerprint(self.db), self.before)

        restore(current, self.db)
        self.assertEqual(fingerprint(self.db), after_work)


class TheSnapshotIsVerifiableBeforeItIsReliedOnTests(RehearsalTestCase):
    """A snapshot nobody checked is the same belief in a different file."""

    def test_a_good_snapshot_opens_and_reports_its_contents(self):
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        rows, _ = fingerprint(snap)
        self.assertEqual(rows, self.before[0])

    def test_a_truncated_snapshot_is_detected_rather_than_trusted(self):
        snap = snapshot(self.db, self.dir / "snap" / "s.db")
        snap.write_bytes(snap.read_bytes()[: snap.stat().st_size // 2])
        with self.assertRaises(sqlite3.DatabaseError):
            fingerprint(snap)

    def test_an_empty_file_is_detected(self):
        snap = self.dir / "snap" / "empty.db"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(b"")
        with self.assertRaises(sqlite3.DatabaseError):
            fingerprint(snap)


if __name__ == "__main__":
    unittest.main()

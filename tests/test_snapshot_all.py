"""The snapshot-everything command, and mostly its refusals.

Writing twelve files is the easy half. The three properties that make it
worth having are all about what it must NOT do, so that is what this
file is mostly about:

* **read-only at every source** — the specific thing three improvised
  scripts each risked;
* **a partial set cannot appear** — a set missing three databases is the
  partial-defence problem, and it must not be possible to end up with one
  silently;
* **it verifies before you rely on it** — a snapshot nobody checked is
  the same belief in a different file.

And one thing about naming rather than behaviour: the set must be
invisible to the seed pruner, by the same structural exemption that
protects `site_dd.before-first-seed…` — not by an exclusion list.
"""

import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_db as sdb
from tools import snapshot_all as sa


def make_db(path, rows=2, table="t"):
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany(f"INSERT INTO {table} (v) VALUES (?)",
                     [(f"row{i}",) for i in range(rows)])
    conn.commit()
    conn.close()


class SnapshotTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "uploads").mkdir()
        (self.root / "uploads" / "a.txt").write_text("one", encoding="utf-8")
        (self.root / "users.json").write_text('{"users": {}}', encoding="utf-8")
        for i, name in enumerate(("alpha.db", "beta.db", "gamma.db")):
            make_db(self.root / name, rows=i + 1)
        patch = mock.patch.object(sdb, "get_db_path",
                                  lambda: self.root / "alpha.db")
        patch.start()
        self.addCleanup(patch.stop)

    def sets(self):
        return sorted((self.root / "backups").glob("keep-set-*"))

    def partials(self):
        return sorted((self.root / "backups").glob(".partial-*"))


class ItWritesTheWholeVolumeTests(SnapshotTestCase):

    def test_every_database_is_in_the_set(self):
        out = sa.snapshot_all()
        names = {e["name"] for e in out["entries"]}
        for db in ("alpha.db", "beta.db", "gamma.db"):
            with self.subTest(db=db):
                self.assertIn(db, names)
                self.assertTrue((Path(out["path"]) / db).exists())

    def test_the_user_store_and_the_uploads_come_too(self):
        out = sa.snapshot_all()
        names = {e["name"] for e in out["entries"]}
        self.assertIn("users.json", names)
        self.assertIn("uploads.tar.gz", names)

    def test_the_uploads_archive_holds_the_files(self):
        import tarfile
        out = sa.snapshot_all()
        with tarfile.open(Path(out["path"]) / "uploads.tar.gz") as tar:
            self.assertIn("a.txt", tar.getnames())

    def test_it_does_not_snapshot_its_own_snapshots(self):
        """`/data/backups` holds copies of the same databases. A snapshot
        of the snapshots is useless and unbounded."""
        first = sa.snapshot_all(label="first")
        second = sa.snapshot_all(label="second")
        self.assertEqual(second["databases"], first["databases"])
        self.assertNotIn("keep-set-first",
                         {e["name"] for e in second["entries"]})

    def test_the_manifest_states_its_own_algorithm(self):
        """An unreproducible fingerprint is not a check, so the set says
        how its numbers were made without anybody reading this module."""
        out = sa.snapshot_all()
        manifest = json.loads(
            (Path(out["path"]) / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertIn("sha256", manifest["fingerprint_algorithm"])
        self.assertEqual(manifest["databases"], 3)


class EveryCopyMatchesItsSourceTests(SnapshotTestCase):

    def test_the_fingerprints_agree(self):
        out = sa.snapshot_all()
        for entry in out["entries"]:
            if entry["kind"] != "database":
                continue
            with self.subTest(db=entry["name"]):
                self.assertEqual(
                    sa.content_fingerprint(self.root / entry["name"]),
                    entry["fingerprint"])

    def test_two_databases_with_different_content_differ(self):
        """POSITIVE CONTROL. Every assertion above is an equality, and a
        fingerprint that returned a constant would satisfy all of them."""
        out = sa.snapshot_all()
        prints = {e["name"]: e["fingerprint"] for e in out["entries"]
                  if e["kind"] == "database"}
        self.assertEqual(len(set(prints.values())), 3, prints)

    def test_a_changed_row_changes_the_fingerprint(self):
        before = sa.content_fingerprint(self.root / "alpha.db")
        conn = sqlite3.connect(self.root / "alpha.db")
        conn.execute("UPDATE t SET v = 'changed' WHERE id = 1")
        conn.commit()
        conn.close()
        self.assertNotEqual(before, sa.content_fingerprint(self.root / "alpha.db"))

    def test_row_order_does_not_change_it(self):
        """The reason rows are sorted: VACUUM INTO rewrites in rowid
        order, so a physical reordering must not read as corruption."""
        original = sa.content_fingerprint(self.root / "beta.db")
        conn = sqlite3.connect(self.root / "beta.db")
        rows = conn.execute("SELECT id, v FROM t").fetchall()
        conn.execute("DELETE FROM t")
        conn.executemany("INSERT INTO t (id, v) VALUES (?, ?)", reversed(rows))
        conn.commit()
        conn.close()
        self.assertEqual(original, sa.content_fingerprint(self.root / "beta.db"))


class ItIsReadOnlyAtTheSourceTests(SnapshotTestCase):
    """The specific thing three improvised scripts each risked."""

    def test_the_sources_are_byte_identical_afterwards(self):
        before = {p.name: p.read_bytes()
                  for p in self.root.glob("*.db")}
        sa.snapshot_all()
        for name, data in before.items():
            with self.subTest(db=name):
                self.assertEqual((self.root / name).read_bytes(), data)

    def test_the_connection_really_is_read_only(self):
        """POSITIVE CONTROL on `mode=ro` itself: it must FAIL CLOSED. If
        this ever stops raising, the guarantee above is decoration."""
        conn = sqlite3.connect(f"file:{self.root / 'alpha.db'}?mode=ro", uri=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("INSERT INTO t (v) VALUES ('nope')")
        finally:
            conn.close()

    def test_every_connect_in_the_module_asks_for_mode_ro(self):
        """ON THE AST, and the first version of this test was wrong in
        the way this codebase keeps finding: it counted the string
        "?mode=ro" against the count of "sqlite3.connect" and failed 3
        != 2, because the module DOCSTRING mentions `mode=ro` while
        explaining the guarantee. A checker confounded by prose about the
        thing it checks is the dead-reader defect again.
        """
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(sa))
        connects = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", None) == "connect"]
        self.assertTrue(connects, "no sqlite3.connect calls found at all")
        for call in connects:
            arg = call.args[0]
            rendered = ast.unparse(arg)
            with self.subTest(call=rendered):
                self.assertIn("mode=ro", rendered)
                self.assertTrue(
                    any(kw.arg == "uri" for kw in call.keywords),
                    "mode=ro in the string does nothing without uri=True")


class APartialSetCannotAppearTests(SnapshotTestCase):

    def test_a_failure_leaves_no_set_behind(self):
        real = sa.content_fingerprint

        def explode(path):
            if Path(path).name == "gamma.db":
                raise sqlite3.DatabaseError("disk I/O error")
            return real(path)

        with mock.patch.object(sa, "content_fingerprint", explode):
            with self.assertRaises(sqlite3.DatabaseError):
                sa.snapshot_all()
        self.assertEqual(self.sets(), [])
        self.assertEqual(self.partials(), [])

    def test_a_mismatched_copy_refuses_the_whole_set(self):
        calls = {"n": 0}
        real = sa.content_fingerprint

        def drifting(path):
            calls["n"] += 1
            return "deadbeefdeadbeef" if calls["n"] == 2 else real(path)

        with mock.patch.object(sa, "content_fingerprint", drifting):
            with self.assertRaises(sa.SnapshotRefused) as ctx:
                sa.snapshot_all()
        self.assertIn("does not match its source", str(ctx.exception))
        self.assertEqual(self.sets(), [])
        self.assertEqual(self.partials(), [])

    def test_a_volume_with_no_databases_is_refused(self):
        empty = Path(tempfile.mkdtemp())
        with self.assertRaises(sa.SnapshotRefused) as ctx:
            sa.snapshot_all(source=empty)
        self.assertIn("not a snapshot", str(ctx.exception))

    def test_it_will_not_overwrite_an_existing_set(self):
        sa.snapshot_all(label="fixed")
        with self.assertRaises(sa.SnapshotRefused):
            sa.snapshot_all(label="fixed")

    def test_positive_control_the_happy_path_does_produce_a_set(self):
        """Three tests above assert an absence; without this they would
        pass against a command that never wrote anything."""
        sa.snapshot_all()
        self.assertEqual(len(self.sets()), 1)


class VerifySetChecksRatherThanTrustsTests(SnapshotTestCase):

    def test_a_fresh_set_is_sound(self):
        out = sa.snapshot_all()
        self.assertTrue(sa.verify_set(out["path"])["sound"])

    def test_a_tampered_database_is_caught(self):
        out = sa.snapshot_all()
        conn = sqlite3.connect(Path(out["path"]) / "alpha.db")
        conn.execute("INSERT INTO t (v) VALUES ('sneaked in')")
        conn.commit()
        conn.close()
        result = sa.verify_set(out["path"])
        self.assertFalse(result["sound"])
        self.assertEqual(result["mismatched"], ["alpha.db"])

    def test_a_missing_file_is_caught(self):
        out = sa.snapshot_all()
        (Path(out["path"]) / "beta.db").unlink()
        result = sa.verify_set(out["path"])
        self.assertFalse(result["sound"])
        self.assertIn("beta.db", result["missing"])

    def test_a_directory_that_is_not_a_set_is_refused(self):
        stray = self.root / "backups" / "keep-set-handmade"
        stray.mkdir(parents=True)
        with self.assertRaises(sa.SnapshotRefused) as ctx:
            sa.verify_set(stray)
        self.assertIn("nothing here can vouch for it", str(ctx.exception))


class ThePrunerCannotSeeASetTests(SnapshotTestCase):
    """Exempt by construction, like every hand-taken snapshot."""

    def test_the_seed_pruner_leaves_it_alone(self):
        import os
        import time
        from tools import site_dd_seed_write as sw

        out = sa.snapshot_all()
        backups = self.root / "backups"
        # A seed snapshot old enough to be pruned, so the pruner is doing
        # something when it runs rather than nothing.
        for i in range(12):
            old = backups / f"site_dd.seed-2026{i:04d}-000000-abc{i:03x}.db"
            old.write_bytes(b"x")
            when = time.time() - (400 - i) * 86400
            os.utime(old, (when, when))
        removed = sw.prune_snapshots(db_path=self.root / "alpha.db")
        self.assertTrue(removed, "the pruner did nothing, so this proves nothing")
        self.assertTrue(Path(out["path"]).is_dir())
        self.assertTrue(sa.verify_set(out["path"])["sound"])

    def test_the_set_name_carries_the_keep_convention(self):
        out = sa.snapshot_all()
        self.assertTrue(Path(out["path"]).name.startswith("keep-set-"))


class ItSaysWhatItIsNotTests(unittest.TestCase):
    """The docstring is load-bearing here: a snapshot mechanism nobody
    triggers reads as cover while covering nothing."""

    def test_the_module_refuses_to_call_itself_a_backup_regime(self):
        self.assertIn("It is not a backup regime", sa.__doc__)
        self.assertIn("Nothing runs it", sa.__doc__)

    def test_the_report_repeats_it_where_an_operator_will_see_it(self):
        manifest = {"path": "/x", "taken_at": "now", "databases": 1,
                    "bytes": 10, "seconds": 0.1,
                    "entries": [{"name": "a.db", "bytes": 10,
                                 "fingerprint": "abc"}]}
        self.assertIn("not a backup regime", sa._report(manifest))


if __name__ == "__main__":
    unittest.main()

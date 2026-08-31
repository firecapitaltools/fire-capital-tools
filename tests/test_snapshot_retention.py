"""Snapshots are bounded, and the bound cannot reach the ones that matter.

Every seed takes a snapshot and nothing ever removed one. The cost is not
space -- 5 GB against a snapshot the size of the database is years away
from mattering -- it is that a directory of fifty near-identical files is
where somebody restores the wrong one in a hurry.

WHAT THESE TESTS ARE REALLY ABOUT

A pruner is a deleting instrument pointed at the only rollback this
platform has (known-issues 3: `maxBackupsCount` is 0, there is no
platform backup behind these files). So the tests are weighted towards
what it must NOT touch:

* a hand-taken snapshot, whatever its age -- exempt because it cannot
  match `site_dd.seed-*.db`, not because it appears on a list;
* the newest seed snapshot, whatever its age;
* anything inside the 30-day window, however many there are.

And the positive control matters more than usual here: a pruner that
deletes nothing passes every "it did not delete X" assertion in this
file. `ItDoesDeleteWhenItShouldTests` is what makes the rest mean
something.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_seed_write as sw

DAY = 86400


class RetentionTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.db = self.root / "site_dd.db"
        self.db.write_bytes(b"")
        self.backups = self.root / sw.SNAPSHOT_DIR
        self.backups.mkdir()
        self.now = time.time()

    def snap(self, name, age_days):
        """One snapshot file, aged by its mtime."""
        path = self.backups / name
        path.write_bytes(b"x" * 16)
        when = self.now - age_days * DAY
        os.utime(path, (when, when))
        return path

    def seeds(self, count, *, oldest_days, step_days=1):
        """`count` seed snapshots. RETURNED NEWEST FIRST, which is the
        order the pruner considers them in -- so `made[0]` is the one
        that must never be deleted and `made[-1]` is the first to go."""
        made = []
        for i in range(count):
            age = oldest_days - i * step_days
            made.append(self.snap(f"site_dd.seed-2026{i:04d}-000000-abc{i:03x}.db", age))
        return list(reversed(made))

    def prune(self):
        return sw.prune_snapshots(db_path=self.db, now=self.now)

    def names(self):
        return sorted(p.name for p in self.backups.iterdir())


class ItDoesDeleteWhenItShouldTests(RetentionTestCase):
    """THE POSITIVE CONTROL. Every other test here asserts something was
    kept, and a pruner that never deletes would pass all of them."""

    def test_an_old_surplus_snapshot_is_removed(self):
        self.seeds(12, oldest_days=400, step_days=10)
        removed = self.prune()
        self.assertTrue(removed, "the pruner deleted nothing at all")

    def test_it_removes_exactly_the_two_oldest_of_twelve(self):
        """Twelve snapshots, all far outside the window: the newest ten
        stay by count and the other two go."""
        made = self.seeds(12, oldest_days=400, step_days=10)
        oldest_two = sorted(p.name for p in made[-2:])
        self.assertEqual(self.prune(), oldest_two)
        self.assertEqual(len(self.names()), 10)

    def test_the_files_are_actually_gone(self):
        made = self.seeds(12, oldest_days=400, step_days=10)
        self.prune()
        for path in made[-2:]:
            self.assertFalse(path.exists())
        for path in made[:10]:
            self.assertTrue(path.exists())

    def test_it_reports_what_it_removed(self):
        made = self.seeds(11, oldest_days=400, step_days=10)
        self.assertEqual(self.prune(), [made[-1].name])


class ItDeletesNothingWhenNothingQualifiesTests(RetentionTestCase):
    """The other half of the control: a directory of recent and
    hand-taken snapshots must come back untouched."""

    def test_a_directory_of_recent_snapshots_is_left_alone(self):
        self.seeds(25, oldest_days=20, step_days=0)
        before = self.names()
        self.assertEqual(self.prune(), [])
        self.assertEqual(self.names(), before)

    def test_a_directory_of_hand_taken_snapshots_is_left_alone(self):
        self.snap("site_dd.before-first-seed.20260831-033837.db", age_days=900)
        self.snap("site_dd.keep-before-the-migration.db", age_days=900)
        self.snap("underwriting.keep-pre_part14.db", age_days=900)
        before = self.names()
        self.assertEqual(self.prune(), [])
        self.assertEqual(self.names(), before)

    def test_an_empty_directory_is_fine(self):
        self.assertEqual(self.prune(), [])

    def test_a_missing_directory_is_fine(self):
        import shutil
        shutil.rmtree(self.backups)
        self.assertEqual(self.prune(), [])


class BothRulesNotEitherTests(RetentionTestCase):
    """Ten in an afternoon must not evict a month, and a quiet year must
    not leave one file."""

    def test_thirty_recent_snapshots_all_survive_the_count_rule(self):
        """Inside the window, so the count does not apply."""
        self.seeds(30, oldest_days=25, step_days=0)
        self.assertEqual(self.prune(), [])
        self.assertEqual(len(self.names()), 30)

    def test_ten_ancient_snapshots_all_survive_the_age_rule(self):
        """Outside the window, so the count is what keeps them."""
        self.seeds(10, oldest_days=900, step_days=10)
        self.assertEqual(self.prune(), [])
        self.assertEqual(len(self.names()), 10)

    def test_the_boundary_at_thirty_days(self):
        """One day either side of the window, with the count already
        spent on NEWER files -- otherwise the count keeps them both and
        the test says nothing about the window."""
        self.seeds(10, oldest_days=5, step_days=0)         # fills the count
        just_inside = self.snap("site_dd.seed-20250101-000000-aaaaaa.db", 29)
        just_outside = self.snap("site_dd.seed-20250101-000000-bbbbbb.db", 31)
        removed = self.prune()
        self.assertIn(just_outside.name, removed)
        self.assertNotIn(just_inside.name, removed)
        self.assertTrue(just_inside.exists())


class ItCannotReachAHandTakenSnapshotTests(RetentionTestCase):
    """Exempt by pattern, not by memory. This is the guarantee the whole
    design rests on, so it is tested against the real filename rather
    than a stand-in."""

    def test_the_pre_first_seed_snapshot_survives_a_full_prune(self):
        self.seeds(40, oldest_days=900, step_days=10)
        real = self.snap("site_dd.before-first-seed.20260831-033837.db", 900)
        removed = self.prune()
        self.assertTrue(removed, "nothing was pruned, so this proves nothing")
        self.assertTrue(real.exists())
        self.assertNotIn(real.name, removed)

    def test_a_keep_named_snapshot_survives(self):
        self.seeds(40, oldest_days=900, step_days=10)
        kept = self.snap("site_dd.keep-before-the-2027-migration.db", 900)
        self.prune()
        self.assertTrue(kept.exists())

    def test_another_databases_snapshot_is_not_its_business(self):
        self.seeds(40, oldest_days=900, step_days=10)
        other = self.snap("underwriting.seed-20260101-000000-aaaaaa.db", 900)
        self.prune()
        self.assertTrue(other.exists())

    def test_the_glob_is_the_mechanism_and_not_a_list(self):
        """Read from the code: an exclusion list would pass every test
        above and would be a different design -- one with something to
        forget."""
        import inspect
        src = inspect.getsource(sw.prune_snapshots)
        self.assertIn("SNAPSHOT_PRUNE_GLOB", src)
        self.assertNotIn("before-first-seed", src)


class TheNewestIsNeverDeletedTests(RetentionTestCase):
    def test_a_single_ancient_snapshot_survives(self):
        only = self.snap("site_dd.seed-20200101-000000-aaaaaa.db", 3650)
        self.assertEqual(self.prune(), [])
        self.assertTrue(only.exists())

    def test_the_newest_of_many_ancient_ones_survives(self):
        made = self.seeds(15, oldest_days=900, step_days=10)
        self.prune()
        self.assertTrue(made[0].exists(), "the newest snapshot was deleted")

    def test_even_with_the_count_configured_to_zero(self):
        """The rule does not depend on SNAPSHOT_KEEP_COUNT being sane."""
        made = self.seeds(3, oldest_days=900, step_days=10)
        with mock.patch.object(sw, "SNAPSHOT_KEEP_COUNT", 0):
            removed = sw.prune_snapshots(db_path=self.db, now=self.now)
        self.assertTrue(made[0].exists(), "a zero count emptied the directory")
        self.assertEqual(len(removed), 2)


class ItNeverFailsTheSeedTests(RetentionTestCase):
    def test_a_file_that_cannot_be_removed_is_skipped_not_raised(self):
        made = self.seeds(12, oldest_days=400, step_days=10)
        stuck = made[-1].name                      # the oldest, first to go
        real_unlink = Path.unlink

        def stubborn(self, *a, **kw):
            if self.name == stuck:
                raise OSError("in use")
            return real_unlink(self, *a, **kw)

        with mock.patch.object(Path, "unlink", stubborn):
            removed = sw.prune_snapshots(db_path=self.db, now=self.now)
        self.assertEqual(len(removed), 1)          # the other one still went
        self.assertNotIn(stuck, removed)
        self.assertTrue((self.backups / stuck).exists())


class ThePruneRunsInsideTheSeedTests(unittest.TestCase):
    """Wired, not merely written -- the same claim the seed write itself
    spent a merge being unable to make."""

    def test_apply_seed_calls_it_right_after_the_snapshot(self):
        import ast, inspect, textwrap
        tree = ast.parse(textwrap.dedent(inspect.getsource(sw.apply_seed)))
        calls = [n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn("take_snapshot", calls)
        self.assertIn("prune_snapshots", calls)
        self.assertLess(calls.index("take_snapshot"), calls.index("prune_snapshots"))

    def test_the_result_reports_what_was_pruned(self):
        import inspect
        self.assertIn('"pruned_snapshots": pruned', inspect.getsource(sw.apply_seed))

    def test_the_confirmation_message_says_so(self):
        import inspect
        from tools import site_dd
        src = inspect.getsource(site_dd.seed_apply)
        self.assertIn("pruned_snapshots", src)
        self.assertIn("retention window", src)


if __name__ == "__main__":
    unittest.main()

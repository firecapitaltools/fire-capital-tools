"""A storage monitor must not report healthy because it cannot see.

`_media_storage()` computed `used_pct` as `0.0` when the volume's size
came back falsy, and 0.0% used falls through both thresholds to `"ok"`.
The panel then rendered green with the reassuring sentence: *"Video is
capped ... photos are the default"*. A volume nobody could measure was
reported as a volume with plenty of room.

**Neither half was a live defect and that is why this is small.**
`statvfs` returning a zero block count on a live mount is not a state
anybody has produced. But the OTHER half of the same behaviour is
reached constantly: every Windows development machine takes the
`AttributeError` branch, which also said `"ok"`.

The direction is the whole point. A monitor that fails towards "fine" is
worse than one that fails loudly, because the failure looks exactly like
the thing it is supposed to detect not happening.

SAME SHAPE AS THE ONE BEFORE IT. `pct_change` returned 0.0 for a trend it
could not compute; this returned 0.0% for a volume it could not read.
Absent written as zero, both times, and in both cases a consumer then
graded the fabricated number.
"""

import unittest
from unittest import mock

from tools import admin


class FakeStatvfs:
    def __init__(self, blocks, bavail, frsize=4096):
        self.f_blocks = blocks
        self.f_bavail = bavail
        self.f_frsize = frsize


def storage(statvfs_result=None, raises=None):
    """`_media_storage` with the volume read stubbed. The media totals
    come from the real Site DD database, which is what the rest of the
    panel is about and is not under test here."""
    def fake(_path):
        if raises is not None:
            raise raises
        return statvfs_result
    # `create=True` because this test file runs on Windows too, where
    # `os.statvfs` does not exist -- which is the very condition the
    # AttributeError branch below is about.
    with mock.patch.object(admin.os, "statvfs", fake, create=True):
        return admin._media_storage()


class ThePreconditionTests(unittest.TestCase):
    """Every assertion below is about the level. They pass vacuously if
    the panel stops reporting one at all."""

    def test_a_readable_volume_reports_a_level_and_a_percentage(self):
        out = storage(FakeStatvfs(blocks=1000, bavail=900))
        self.assertEqual(out["level"], "ok")
        self.assertAlmostEqual(out["volume_used_pct"], 10.0)


class AnUnreadableVolumeIsNotAHealthyOneTests(unittest.TestCase):

    def test_a_zero_sized_volume_is_unknown_not_ok(self):
        out = storage(FakeStatvfs(blocks=0, bavail=0))
        self.assertEqual(out["level"], "unknown")

    def test_and_reports_no_percentage_rather_than_zero(self):
        out = storage(FakeStatvfs(blocks=0, bavail=0))
        self.assertIsNone(out["volume_used_pct"])

    def test_it_says_why(self):
        out = storage(FakeStatvfs(blocks=0, bavail=0))
        self.assertIn("zero", out["volume_reason"])

    def test_statvfs_missing_is_unknown_too(self):
        """The reachable half: every Windows dev machine takes this."""
        out = storage(raises=AttributeError("no statvfs"))
        self.assertEqual(out["level"], "unknown")
        self.assertIsNone(out["volume_used_pct"])
        self.assertIn("could not be read", out["volume_reason"])

    def test_an_oserror_is_unknown_too(self):
        out = storage(raises=OSError("gone"))
        self.assertEqual(out["level"], "unknown")

    def test_the_rest_of_the_panel_still_arrives(self):
        """A volume that cannot be read must not take the media figures
        down with it -- that is what this function's docstring promises."""
        out = storage(raises=OSError("gone"))
        self.assertTrue(out["available"])
        self.assertIn("human", out)
        self.assertIn("max_video_mb", out)


class TheThresholdsStillWorkTests(unittest.TestCase):
    """The change must not have moved where warn and critical begin."""

    def level_at(self, pct):
        blocks = 1000
        bavail = int(round(blocks * (1 - pct / 100)))
        return storage(FakeStatvfs(blocks=blocks, bavail=bavail))["level"]

    def test_below_the_warn_line_is_ok(self):
        self.assertEqual(self.level_at(50), "ok")

    def test_at_the_warn_line_is_warn(self):
        self.assertEqual(self.level_at(admin.STORAGE_WARN_PCT), "warn")

    def test_at_the_critical_line_is_critical(self):
        self.assertEqual(self.level_at(admin.STORAGE_CRITICAL_PCT), "critical")

    def test_a_genuinely_empty_volume_is_still_ok(self):
        """0.0% used is a real answer when the volume was actually read,
        and it must still say so -- the same distinction the category
        trend fix drew between a real zero and an unknown."""
        out = storage(FakeStatvfs(blocks=1000, bavail=1000))
        self.assertEqual(out["volume_used_pct"], 0.0)
        self.assertEqual(out["level"], "ok")


class ThePageSaysSoTests(unittest.TestCase):
    """The panel is hidden when there are no figures, so without this the
    absence would read as silence rather than as an answer."""

    def markup(self):
        from pathlib import Path
        return (Path(admin.__file__).parents[1] / "templates" / "admin"
                / "service_costs.html").read_text(encoding="utf-8")

    def test_the_template_has_an_unknown_branch(self):
        self.assertIn("storage.level == 'unknown'", self.markup())

    def test_it_prints_the_reason(self):
        self.assertIn("storage.volume_reason", self.markup())

    def test_and_says_it_is_not_a_clean_bill_of_health(self):
        self.assertIn("not a report that storage is fine", self.markup())

    def test_the_unknown_branch_comes_before_the_reassuring_one(self):
        """It used to fall through to the else, which is the sentence
        about photos being the default. Order is the fix."""
        src = self.markup()
        self.assertLess(src.index("storage.level == 'unknown'"),
                        src.index("photos are the default"))


if __name__ == "__main__":
    unittest.main()

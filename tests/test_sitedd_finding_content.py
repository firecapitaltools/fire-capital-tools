"""What counts as somebody having put something there.

Three counts over one table, and this file is about the third:

    area_finding_count          answered items      (condition IS NOT NULL)
    area_finding_rows           every row           (what survives a write)
    area_findings_with_content  rows with something in them

The first two are both right and neither answers *"how much work is
here"*. Saving a page writes a row per item -- sixty of them from three
empty saves -- so the row count reads as effort nobody spent, and the
answered-only count misses a note, a cost or a photo recorded without a
condition.

THE COLUMNS WERE SETTLED BY RUNNING THE SAVE, NOT BY READING THE LIST

The brief proposed condition, note, cost, measure and quantity. **Measure
does not survive contact with the code**: an empty save writes 'gal' and
'yr' into it, because a NUMBER item's unit comes from the catalogue
rather than from a person -- which `site_dd_capex_export._stated_cost_unit`
already records for a different reason. Counting it would have made every
water heater and every HVAC unit look walked. `est_cost_source` is the
same shape, written as 'none' by the same save.

Three columns went the other way and are not in the brief's list:
`instance_label`, `bank_item_key` and a second `instance_no` are all
things only a person produces.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_db as sdb

BLANK = {"scope": "room", "category_key": "interior_units",
         "item_key": "walls_ceiling", "instance_no": 1, "condition": None,
         "detail": None, "note": None, "quantity": None, "measure": None,
         "est_unit_cost": None, "est_cost_source": "none",
         "instance_label": None, "bank_item_key": None}


class ContentTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "s.db"
        patch = mock.patch.object(sdb, "get_db_path", lambda: self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "X", "assessed_on": "2026-08-31",
                "inspector": None, "checklist_version": 2, "deal_id": None})
            self.area = sdb.create_area(conn, self.aid, {"kind": "unit", "label": "110"})
            self.room = sdb.create_room(conn, self.area, "kitchen", None)

    def write(self, **overrides):
        """One finding, blank except for what is named."""
        row = dict(BLANK, area_id=self.area, room_id=self.room)
        row["item_key"] = overrides.pop("item_key", f"item_{len(overrides)}_{id(overrides) % 997}")
        row.update(overrides)
        with sdb.get_connection() as conn:
            sdb.upsert_findings(conn, self.aid, [row])
            return [f for f in sdb.list_all_findings(conn, self.aid)
                    if f["item_key"] == row["item_key"]][0]["id"]

    def counts(self):
        with sdb.get_connection() as conn:
            return (sdb.area_finding_count(conn, self.area),
                    sdb.area_finding_rows(conn, self.area),
                    sdb.area_findings_with_content(conn, self.area))

    def content(self):
        return self.counts()[2]


class TheThreeControlsTests(ContentTestCase):
    """The cases named in the brief, and the third is the one that makes
    the other two mean anything."""

    def test_a_finding_with_only_a_note_counts(self):
        self.write(note="water stain by the window")
        self.assertEqual(self.content(), 1)

    def test_a_finding_with_only_a_photo_counts(self):
        """You photograph the crack, then decide what it is. The media
        table's own comment says captures often precede the finding."""
        fid = self.write()
        with sdb.get_connection() as conn:
            sdb.add_media(conn, self.aid, "walls_ceiling", "crack.jpg",
                          "a1.jpg", None, kind=sdb.MEDIA_PHOTO,
                          finding_id=fid, size_bytes=100,
                          area_id=self.area, room_id=self.room)
        self.assertEqual(self.content(), 1)

    def test_an_entirely_empty_finding_does_not_count(self):
        self.write()
        rows_before = self.counts()[1]
        self.assertEqual(rows_before, 1, "the row was not written at all")
        self.assertEqual(self.content(), 0)


class ZeroIsAnAnswerAndBlankIsNotTests(ContentTestCase):

    def test_a_zero_cost_counts(self):
        """Somebody wrote down that putting this right costs nothing."""
        self.write(est_unit_cost=0.0)
        self.assertEqual(self.content(), 1)

    def test_a_zero_quantity_counts(self):
        """DECIDED, not incidental: `to_float` returns None for a blank
        field, so a 0 in the box was typed by a person."""
        self.write(quantity=0.0)
        self.assertEqual(self.content(), 1)

    def test_an_empty_string_note_does_not_count(self):
        """A form posts '' for a field somebody cleared."""
        self.write(note="")
        self.assertEqual(self.content(), 0)

    def test_a_whitespace_note_does_not_count(self):
        self.write(note="   ")
        self.assertEqual(self.content(), 0)

    def test_an_empty_condition_does_not_count(self):
        self.write(condition="")
        self.assertEqual(self.content(), 0)


class TheColumnsTheRouteWritesByItselfTests(ContentTestCase):
    """The half that had to be measured. These look like content and are
    not: an empty save produces them without anybody answering."""

    def test_a_measure_alone_does_not_count(self):
        """'gal' on a water heater comes from the catalogue."""
        self.write(measure="gal")
        self.assertEqual(self.content(), 0)

    def test_but_a_quantity_with_that_measure_does(self):
        self.write(measure="gal", quantity=40.0)
        self.assertEqual(self.content(), 1)

    def test_est_cost_source_none_does_not_count(self):
        self.write(est_cost_source="none")
        self.assertEqual(self.content(), 0)

    def test_est_cost_source_manual_does(self):
        self.write(est_cost_source="manual")
        self.assertEqual(self.content(), 1)


class TheColumnsOnlyAPersonProducesTests(ContentTestCase):
    """Not in the brief's list, and each is somebody's deliberate act."""

    def test_a_typed_instance_label_counts(self):
        self.write(instance_label="hallway")
        self.assertEqual(self.content(), 1)

    def test_a_bank_item_counts(self):
        self.write(bank_item_key="washer_dryer")
        self.assertEqual(self.content(), 1)

    def test_a_second_instance_counts(self):
        """Instance 1 is emitted for every item whether or not anybody
        asked. Instance 2 exists because somebody added it."""
        self.write(instance_no=2)
        self.assertEqual(self.content(), 1)

    def test_the_first_instance_alone_does_not(self):
        self.write(instance_no=1)
        self.assertEqual(self.content(), 0)


class TheThreeCountsDisagreeOnPurposeTests(ContentTestCase):
    """The assessment-11 shape, in miniature: many rows, few answers, and
    real work that carries no condition."""

    def build(self):
        self.write(item_key="answered_1", condition="repair")
        self.write(item_key="answered_2", condition="replace")
        self.write(item_key="noted", note="smells damp")
        for i in range(20):
            self.write(item_key=f"untouched_{i}")

    def test_all_three_give_different_numbers(self):
        self.build()
        answered, rows, content = self.counts()
        self.assertEqual((answered, rows, content), (2, 23, 3))

    def test_and_each_is_right_about_its_own_question(self):
        """Stated as a sentence so the difference is not read as a bug:
        two items were judged, twenty-three rows exist, three carry
        something a person put there."""
        self.build()
        answered, rows, content = self.counts()
        self.assertLess(answered, content)
        self.assertLess(content, rows)


class AnEmptySaveProducesNoContentTests(unittest.TestCase):
    """End to end through the routes, which is where the sixty rows came
    from in the first place."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "s.db"
        patch = mock.patch.object(sdb, "get_db_path", lambda: self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "X", "assessed_on": "2026-08-31",
                "inspector": None, "checklist_version": 2, "deal_id": None})
            self.area = sdb.create_area(conn, self.aid, {"kind": "unit", "label": "110"})
            self.room = sdb.create_room(conn, self.area, "kitchen", None)
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def test_empty_saves_write_rows_but_no_content(self):
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/areas/{self.area}/save", data={})
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/areas/{self.area}"
                         f"/rooms/{self.room}/save", data={})
        with sdb.get_connection() as conn:
            rows = sdb.area_finding_rows(conn, self.area)
            content = sdb.area_findings_with_content(conn, self.area)
        self.assertGreater(rows, 20, "the materialising save stopped materialising")
        self.assertEqual(content, 0)

    def test_and_one_real_answer_moves_it_to_one(self):
        """The positive control on the test above: it is zero because
        nothing was answered, not because the count is broken."""
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/areas/{self.area}"
                         f"/rooms/{self.room}/save",
                         data={"condition_walls_ceiling": "repair"})
        with sdb.get_connection() as conn:
            self.assertEqual(sdb.area_findings_with_content(conn, self.area), 1)


class ThePreviewUsesItTests(unittest.TestCase):
    def test_the_seeding_read_state_asks_for_content(self):
        """COMMENTS STRIPPED FIRST -- the route's comment names all three
        counts, so a substring search finds the explanation."""
        import ast, inspect, textwrap
        from tools import site_dd
        tree = ast.parse(textwrap.dedent(inspect.getsource(site_dd._seed_read_state)))
        called = {getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                  for n in ast.walk(tree) if isinstance(n, ast.Call)}
        self.assertIn("area_findings_with_content", called)
        self.assertNotIn("area_finding_rows", called)
        self.assertNotIn("area_finding_count", called)

    def test_the_screen_says_what_the_number_means(self):
        tpl = (Path(sdb.__file__).parents[1] / "templates" / "tools"
               / "site_dd_seed_preview.html").read_text(encoding="utf-8")
        self.assertIn("answers, notes, costs and photos", tpl)


if __name__ == "__main__":
    unittest.main()

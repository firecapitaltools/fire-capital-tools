"""Site DD Lite: vacant units and common areas only.

Michelle settled this herself — *"the normal tool should be fine if we
make it toggleable enough"* — and it has been designed-but-unbuilt since
Part 31, blocked by nothing. What changed is that it became useful:
assessment 21 holds 152 units, 18 of them vacant. Walking 18 is a job;
walking 152 is not.

WHAT THESE TESTS ARE ACTUALLY GUARDING

A filter is easy and the two ways it goes wrong are not:

1. **A number that follows the view.** A completion percentage meaning
   "complete for the units I am looking at" is fabricated. Every figure
   on the page is computed before the filter, and that is asserted here
   by comparing the filtered page's figures against the unfiltered
   page's rather than by reading the code.
2. **A view that hides its own scope.** "18 units" and "18 of 152" are
   different claims, and the first is how somebody decides a walk is
   finished.

AND ONE DECISION, WHICH IS THE INTERESTING ONE

An area with NULL status is neither occupied nor vacant. Lite SHOWS it,
because excluding it would hide an area from the walk list on the
strength of missing data — absent read as a value, which this codebase
has now had wrong in three directions. Production holds one such area.
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import site_dd_db as sdb


class LiteTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "s.db"
        patch = mock.patch.object(sdb, "get_db_path", lambda: self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "Oxford Pointe", "assessed_on": "2026-08-31",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
            self.ids = {}
            for label, kind, status in (
                    ("110", sdb.AREA_UNIT, sdb.AREA_OCCUPIED),
                    ("111", sdb.AREA_UNIT, sdb.AREA_OCCUPIED),
                    ("112", sdb.AREA_UNIT, sdb.AREA_VACANT),
                    ("113", sdb.AREA_UNIT, sdb.AREA_DOWN),
                    ("Untitled", sdb.AREA_UNIT, None),
                    ("Lobby", sdb.AREA_COMMON, None),
                    ("Gym", sdb.AREA_COMMON, sdb.AREA_OCCUPIED)):
                self.ids[label] = sdb.create_area(conn, self.aid, {
                    "kind": kind, "label": label, "status": status})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def page(self, view=None):
        url = f"/tools/site-dd/assessment/{self.aid}"
        if view:
            url += f"?view={view}"
        return self.client.get(url).get_data(as_text=True)

    def squash(self, body):
        """Prose assertions run on collapsed whitespace.

        A sentence in a Jinja template is wrapped for the source file's
        line length, so "not an empty page" arrives with a newline and
        eight spaces in the middle of it. Asserting the unwrapped string
        fails for a reason that has nothing to do with the page — and
        re-wrapping a paragraph must not break a test about its content.
        """
        return " ".join(body.split())

    def listed(self, body):
        """The area labels the page actually rendered, harvested from the
        links rather than from a count."""
        return re.findall(r'font-weight:600; color:#111827;">([^<]+)</span>', body)


class TheFilterShowsTheRightAreasTests(LiteTestCase):

    def test_everything_shows_every_area(self):
        self.assertEqual(len(self.listed(self.page())), 7)

    def test_lite_shows_vacant_units(self):
        self.assertIn("112", self.listed(self.page("lite")))

    def test_lite_shows_every_common_area_whatever_its_status(self):
        shown = self.listed(self.page("lite"))
        self.assertIn("Lobby", shown)
        self.assertIn("Gym", shown)

    def test_lite_hides_occupied_units(self):
        shown = self.listed(self.page("lite"))
        self.assertNotIn("110", shown)
        self.assertNotIn("111", shown)

    def test_lite_hides_a_unit_that_is_DOWN(self):
        """`down` is a real status somebody chose, and it is not vacant.
        Her ask was vacant units and common areas."""
        self.assertNotIn("113", self.listed(self.page("lite")))

    def test_an_unrecognised_view_value_shows_everything(self):
        """A typo must not silently hide 5 of 7 areas."""
        self.assertEqual(len(self.listed(self.page("liet"))), 7)


class AnUnstatedStatusIsShownNotAssumedTests(LiteTestCase):
    """The decision, and the reason it goes this way."""

    def test_a_unit_with_no_status_appears_in_lite(self):
        self.assertIn("Untitled", self.listed(self.page("lite")))

    def test_and_the_page_says_that_is_what_it_did(self):
        body = self.squash(self.page("lite"))
        self.assertIn("no status recorded", body)
        self.assertIn("rather than assumed occupied", body)

    def test_the_predicate_says_so_directly(self):
        from tools import site_dd
        self.assertTrue(site_dd._lite_area({"kind": "unit", "status": None}))
        self.assertFalse(site_dd._lite_area({"kind": "unit", "status": "occupied"}))
        self.assertTrue(site_dd._lite_area({"kind": "common", "status": "occupied"}))


class TheScopeIsOnTheScreenTests(LiteTestCase):

    def test_it_says_how_many_of_how_many(self):
        self.assertIn("4 of 7", self.page("lite"))

    def test_it_breaks_the_count_down_by_kind(self):
        body = self.page("lite")
        self.assertIn("2 units", body)
        self.assertIn("2 common areas", body)

    def test_the_unfiltered_view_says_its_own_scope_too(self):
        self.assertIn("All 7 areas", self.page())


class NoNumberFollowsTheFilterTests(LiteTestCase):
    """The failure that would make this feature dishonest, checked by
    comparing the two rendered pages rather than by reading the route."""

    def figures(self, body):
        return {
            "completion": re.findall(r'stat-box-value">(\d+)%</div>', body),
            "assessed": re.findall(r'(\d+) of (\d+) assessed', body),
            "need_work": re.findall(r'<strong>(\d+)</strong> items? need', body),
        }

    def test_the_property_summary_is_identical_in_both_views(self):
        self.assertEqual(self.figures(self.page()),
                         self.figures(self.page("lite")))

    def test_the_completion_percentage_does_not_move(self):
        full = re.search(r'stat-box-value">(\d+)%</div>', self.page())
        lite = re.search(r'stat-box-value">(\d+)%</div>', self.page("lite"))
        self.assertEqual(full.group(1), lite.group(1))

    def test_a_filtered_areas_own_rollup_is_unchanged(self):
        """Each area's percentage comes from its own rooms, so the filter
        cannot touch it. Asserted because 'obviously' is how the other
        two directions of this got shipped."""
        with sdb.get_connection() as conn:
            area = self.ids["112"]
            room = sdb.create_room(conn, area, "kitchen", None)
            sdb.upsert_findings(conn, self.aid, [{
                "scope": "room", "area_id": area, "room_id": room,
                "category_key": "interior_units", "item_key": "flooring",
                "instance_no": 1, "condition": "repair", "detail": None,
                "note": None, "quantity": None, "measure": None,
                "est_unit_cost": None, "est_cost_source": "none",
                "instance_label": None, "bank_item_key": None}])
        full = self.page()
        lite = self.page("lite")
        for body in (full, lite):
            self.assertIn("1 need work", body)


class ItIsReachableByNavigationTests(LiteTestCase):

    def test_the_toggle_is_on_the_page(self):
        body = self.page()
        self.assertIn("Vacant &amp; common only", body)
        self.assertIn("Everything", body)

    def test_the_toggle_link_is_the_url_that_filters(self):
        """Harvested and followed, not typed."""
        body = self.page()
        href = re.search(r'href="([^"]*view=lite[^"]*)"', body).group(1)
        followed = self.client.get(href.replace("&amp;", "&")).get_data(as_text=True)
        self.assertIn("4 of 7", followed)

    def test_the_way_back_is_there_too(self):
        body = self.page("lite")
        self.assertRegex(body, r'href="[^"]*/assessment/\d+#units"')


class AnEmptyLiteViewSaysWhyTests(unittest.TestCase):
    """152 occupied units and no common areas is a real answer, and it
    must not look like a broken page."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "s.db"
        patch = mock.patch.object(sdb, "get_db_path", lambda: self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "All full", "assessed_on": "2026-08-31",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
            for i in range(3):
                sdb.create_area(conn, self.aid, {
                    "kind": sdb.AREA_UNIT, "label": f"{i}",
                    "status": sdb.AREA_OCCUPIED})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        self.client = app.test_client()

    def squash(self, body):
        return " ".join(body.split())

    def test_it_explains_rather_than_showing_an_empty_list(self):
        body = self.squash(self.client.get(
            f"/tools/site-dd/assessment/{self.aid}?view=lite").get_data(as_text=True))
        self.assertIn("That is an answer, not an empty page", body)
        self.assertIn("None of this assessment's 3 areas", body)
        self.assertNotIn("No units added yet", body)

    def test_and_the_unfiltered_view_still_lists_them(self):
        body = self.squash(self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True))
        self.assertNotIn("That is an answer", body)
        self.assertIn("All 3 areas", body)


if __name__ == "__main__":
    unittest.main()

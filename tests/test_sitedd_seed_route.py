"""The route that applies a seed, and the route that undoes one.

WHY THIS FILE IS SEPARATE FROM test_sitedd_seed_write.py

That file tests the write. This one tests the only way a person can reach
it, which is a different claim: five features in this codebase have
shipped correct, tested and unreachable, and the seed write spent one
merge as the sixth on purpose.

So every test here goes through the app the way a browser does, and the
navigation tests HARVEST the link and the form action out of rendered
HTML rather than typing a URL. A route reached by a URL somebody wrote
into a test is not evidence anybody can reach it.

THE THREE GATES, AND EACH HAS A POSITIVE CONTROL

An apply that refuses everything would pass a suite full of "it refused"
assertions. Each gate is therefore tested both ways: the refusal, and the
same request with only that gate satisfied going through and writing.
"""

import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import openpyxl

from tools import site_dd_db as sdb

HEADER = ["Unit", "Type", "Sq. Feet", "Residents", "Status", "Market Rent",
          "Ledger", "Description", "Amount", "Move In", "Lease Start",
          "Lease End", "Move Out"]


def rent_roll_bytes(units):
    """A ResMan-shaped rent roll, in memory.

    `units` is (label, type string, sqft, status). The charge lines matter:
    `_header_index` requires Description/Amount, and a roll without them
    is refused before any of this is reached.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rent Roll"
    for row in (["Oxford Pointe"], ["Some Property Management"], ["Rent Roll"],
                ["8/30/2026"], ["Printed"], [], ["Current"], [], HEADER):
        ws.append(row)
    for label, unit_type, sqft, status in units:
        ws.append([label, unit_type, sqft, "A Resident" if status else None,
                   status, 1200, "Resident", "Rent", 1150, None, None, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


TWO_UNITS = [("110", "2/1.5 RENOVATED", 825, "C"),
             ("226 W/D", "3/2.0 CLASSIC", 1100, None)]


class SeedRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        patch = mock.patch.object(sdb, "get_db_path", lambda: self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "Oxford Pointe", "assessed_on": "2026-08-30",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    # ── navigation, not URLs ─────────────────────────────────────────────

    def preview_url(self):
        """Harvested from the assessment page, never typed."""
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)
        found = re.findall(r'href="([^"]*seed-preview[^"]*)"', body)
        self.assertTrue(found, "the assessment page does not link to the preview")
        return found[0]

    def preview(self, units=TWO_UNITS, filename="rent_roll.xlsx"):
        """POST a roll to the preview and return its HTML."""
        return self.client.post(
            self.preview_url(),
            data={"rentroll": (io.BytesIO(rent_roll_bytes(units)), filename)},
            content_type="multipart/form-data").get_data(as_text=True)

    def apply_form(self, html):
        """The action and every hidden field of the apply form, read out of
        the rendered page. What the browser would post, not what a test
        thinks it should."""
        match = re.search(r'<form[^>]*action="([^"]*seed-apply[^"]*)"', html)
        self.assertIsNotNone(match, "the preview page carries no apply form")
        action = match.group(1)
        block = html[match.start():]
        block = block[:block.index("</form>")]
        fields = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', block))
        return action, fields

    def counts(self):
        with sdb.get_connection() as conn:
            areas = sdb.list_areas(conn, self.aid)
            rooms = sum(len(sdb.list_rooms(conn, a["id"])) for a in areas)
        return len(areas), rooms

    def applied(self, tamper=None, drop=()):
        html = self.preview()
        action, fields = self.apply_form(html)
        fields["understood"] = "on"
        for key in drop:
            fields.pop(key, None)
        if tamper:
            fields.update(tamper)
        return self.client.post(action, data=fields, follow_redirects=True)


class TheApplyIsReachableTests(SeedRouteTestCase):
    """Reachability is a distinct claim from correctness."""

    def test_the_preview_page_carries_an_apply_form(self):
        html = self.preview()
        action, fields = self.apply_form(html)
        self.assertIn(f"/assessment/{self.aid}/seed-apply", action)
        self.assertIn("preview_id", fields)
        self.assertIn("_rendered_state", fields)

    def test_the_button_names_the_figures_rather_than_saying_apply(self):
        """894 rooms is not a thing to write from a button that says Apply."""
        html = self.preview()
        self.assertIn("Create 2 units", html)
        self.assertIn("13 rooms", html)          # 6 for the 2/1.5, 7 for the 3/2.0
        self.assertIn("2 new units", html)

    def test_the_panel_states_what_is_preserved(self):
        html = self.preview()
        self.assertIn("left exactly as", html)
        self.assertIn("no finding is created, changed or removed", html)

    def test_the_apply_writes_the_previewed_units(self):
        self.assertEqual(self.counts(), (0, 0))
        self.applied()
        self.assertEqual(self.counts(), (2, 13))

    def test_the_write_carries_a_batch_id_on_every_row(self):
        self.applied()
        with sdb.get_connection() as conn:
            batches = sdb.list_seed_batches(conn, self.aid)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["areas"], 2)
        self.assertEqual(batches[0]["rooms"], 13)
        self.assertEqual(batches[0]["walked"], 0)

    def test_it_creates_no_findings(self):
        self.applied()
        with sdb.get_connection() as conn:
            self.assertEqual(sdb.list_all_findings(conn, self.aid), [])

    def test_the_confirmation_names_the_batch_and_the_snapshot(self):
        body = self.applied().get_data(as_text=True)
        self.assertIn("Seeded 2 units", body)
        self.assertIn("seed-", body)
        self.assertIn("snapshot was taken first", body)


class ThePreviewStillWritesNothingTests(SeedRouteTestCase):
    """The apply is a second POST. Rendering the preview is not a write,
    and adding a button to the page must not have made it one."""

    def test_previewing_creates_nothing(self):
        self.preview()
        self.assertEqual(self.counts(), (0, 0))

    def test_previewing_twice_creates_nothing(self):
        self.preview()
        self.preview()
        self.assertEqual(self.counts(), (0, 0))


class TheRenderedStateGateTests(SeedRouteTestCase):
    """Two people previewing the same assessment and both applying."""

    def test_a_stale_token_refuses_and_writes_nothing(self):
        html = self.preview()
        action, fields = self.apply_form(html)
        fields["understood"] = "on"
        # Somebody else adds a unit between the preview and the apply.
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid, {"kind": "unit", "label": "999"})
        body = self.client.post(action, data=fields,
                                follow_redirects=True).get_data(as_text=True)
        self.assertIn("older version", body)
        self.assertEqual(self.counts()[0], 1)     # only the hand-made one

    def test_a_missing_token_is_a_mismatch_not_a_pass(self):
        body = self.applied(drop=("_rendered_state",)).get_data(as_text=True)
        self.assertIn("older version", body)
        self.assertEqual(self.counts(), (0, 0))

    def test_positive_control_the_same_post_with_its_token_applies(self):
        self.applied()
        self.assertEqual(self.counts(), (2, 13))


class TheFiguresGateTests(SeedRouteTestCase):
    """The gate the other two cannot cover: file and token both fine, and
    the plan means something different than the screen said."""

    def test_a_tampered_figure_refuses_and_names_both_numbers(self):
        body = self.applied(tamper={"expect_areas": "1"}).get_data(as_text=True)
        self.assertIn("you approved 1", body)
        self.assertIn("now plans 2", body)
        self.assertEqual(self.counts(), (0, 0))

    def test_an_unreadable_figure_refuses(self):
        body = self.applied(tamper={"expect_rooms": ""}).get_data(as_text=True)
        self.assertIn("Nothing was written", body)
        self.assertEqual(self.counts(), (0, 0))

    def test_the_world_changing_under_the_preview_moves_a_figure(self):
        """The realistic version of the same failure, with no tampering:
        an area created between preview and apply changes what the plan
        reconciles to. The token catches this one first, which is correct
        -- both gates describing the same event is not a duplicate, it is
        two independent reasons not to write."""
        html = self.preview()
        action, fields = self.apply_form(html)
        fields["understood"] = "on"
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid, {"kind": "unit", "label": "110"})
        body = self.client.post(action, data=fields,
                                follow_redirects=True).get_data(as_text=True)
        self.assertIn("Nothing was", body)
        self.assertEqual(self.counts()[0], 1)

    def test_positive_control_untampered_figures_apply(self):
        self.applied()
        self.assertEqual(self.counts(), (2, 13))


class TheHeldFileGateTests(SeedRouteTestCase):
    def test_an_unknown_preview_id_refuses(self):
        body = self.applied(tamper={"preview_id": "f" * 32}).get_data(as_text=True)
        self.assertIn("no longer available", body)
        self.assertEqual(self.counts(), (0, 0))

    def test_a_preview_id_that_is_not_an_id_cannot_become_a_path(self):
        body = self.applied(
            tamper={"preview_id": "../../etc/passwd"}).get_data(as_text=True)
        self.assertIn("no longer available", body)
        self.assertEqual(self.counts(), (0, 0))

    def test_the_held_file_is_removed_after_an_apply(self):
        """It exists for one approval and no longer -- whether that
        approval wrote or was refused."""
        from tools import site_dd as route
        html = self.preview()
        action, fields = self.apply_form(html)
        held = route._seed_pending_path(self.aid, fields["preview_id"])
        self.assertTrue(held and held.exists(), "the preview held nothing")
        self.client.post(action, data={**fields, "understood": "on"},
                         follow_redirects=True)
        self.assertEqual(self.counts(), (2, 13))
        self.assertFalse(held.exists())

    def test_it_is_removed_after_a_REFUSED_apply_too(self):
        from tools import site_dd as route
        html = self.preview()
        action, fields = self.apply_form(html)
        held = route._seed_pending_path(self.aid, fields["preview_id"])
        self.client.post(action, data={**fields, "understood": "on",
                                       "expect_areas": "99"},
                         follow_redirects=True)
        self.assertEqual(self.counts(), (0, 0))
        self.assertFalse(held.exists())

    def test_nothing_is_held_on_the_volume(self):
        """A file kept for an unapproved write must not outlive a
        container, so it goes to the system temp directory."""
        from tools import site_dd as route
        self.assertIn(tempfile.gettempdir(), str(route._seed_pending_dir()))


class TheUndoIsReachableTests(SeedRouteTestCase):
    def setUp(self):
        super().setUp()
        self.applied()
        with sdb.get_connection() as conn:
            self.batch = sdb.list_seed_batches(conn, self.aid)[0]["batch"]

    def detail(self):
        return self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)

    def test_the_assessment_page_shows_the_batch(self):
        self.assertIn(self.batch, self.detail())

    def test_and_carries_an_undo_form_for_it(self):
        body = self.detail()
        self.assertIn(f"/assessment/{self.aid}/seed-undo", body)

    def test_the_undo_removes_exactly_what_the_import_created(self):
        body = self.detail()
        action = re.search(r'action="([^"]*seed-undo[^"]*)"', body).group(1)
        self.client.post(action, data={"batch": self.batch, "understood": "on"},
                         follow_redirects=True)
        self.assertEqual(self.counts(), (0, 0))

    def test_it_leaves_a_hand_made_area_alone(self):
        with sdb.get_connection() as conn:
            sdb.create_area(conn, self.aid, {"kind": "unit", "label": "999"})
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/seed-undo",
                         data={"batch": self.batch}, follow_redirects=True)
        self.assertEqual(self.counts()[0], 1)

    def test_an_unnamed_batch_removes_nothing(self):
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/seed-undo",
                         data={}, follow_redirects=True)
        self.assertEqual(self.counts(), (2, 13))


class TheUndoRefusesWhenSomebodyHasWalkedItTests(SeedRouteTestCase):
    """An undo that destroys an inspector's work to correct ours is not an
    undo. The refusal names the rooms rather than counting them."""

    def setUp(self):
        super().setUp()
        self.applied()
        with sdb.get_connection() as conn:
            self.batch = sdb.list_seed_batches(conn, self.aid)[0]["batch"]
            area = sdb.list_areas(conn, self.aid)[0]
            room = sdb.list_rooms(conn, area["id"])[0]
            self.room_id = room["id"]
            sdb.upsert_findings(conn, self.aid, [{
                "scope": "room", "area_id": area["id"], "room_id": room["id"],
                "category_key": "interior_units", "item_key": "walls_ceiling",
                "instance_no": 1, "condition": "repair", "detail": None,
                "note": "cracked", "quantity": None, "measure": None,
                "est_unit_cost": None, "est_cost_source": "none",
                "instance_label": None, "bank_item_key": None}])

    def test_the_route_refuses_and_names_the_room(self):
        body = self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/seed-undo",
            data={"batch": self.batch}, follow_redirects=True).get_data(as_text=True)
        self.assertIn(f"room {self.room_id}", body)
        self.assertIn("cannot be undone", body)
        self.assertEqual(self.counts(), (2, 13))

    def test_the_page_says_so_before_the_button_is_pressed(self):
        """Not as an error afterwards."""
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)
        self.assertIn("Cannot be undone here", body)
        self.assertIn("restore-runbook", body)

    def test_and_offers_no_undo_button_for_that_batch(self):
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)
        self.assertNotIn("Undo this import", body)

    def test_positive_control_an_unwalked_batch_does_offer_one(self):
        with sdb.get_connection() as conn:
            for f in sdb.list_all_findings(conn, self.aid):
                conn.execute("DELETE FROM site_dd_findings WHERE id = ?", (f["id"],))
            conn.commit()
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)
        self.assertIn("Undo this import", body)


class TheRoundTripTests(SeedRouteTestCase):
    """Seed, undo, seed again -- through the routes, because that is the
    sequence the first real seed will run."""

    def test_the_second_seed_is_a_fresh_batch_of_the_same_size(self):
        self.applied()
        with sdb.get_connection() as conn:
            first = sdb.list_seed_batches(conn, self.aid)[0]["batch"]
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/seed-undo",
                         data={"batch": first}, follow_redirects=True)
        self.assertEqual(self.counts(), (0, 0))
        self.applied()
        with sdb.get_connection() as conn:
            batches = sdb.list_seed_batches(conn, self.aid)
        self.assertEqual(len(batches), 1)
        self.assertNotEqual(batches[0]["batch"], first)
        self.assertEqual(self.counts(), (2, 13))


if __name__ == "__main__":
    unittest.main()

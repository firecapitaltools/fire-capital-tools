"""Which building the problem is on, recorded per instance.

Michelle: *"It varies by property, but typically buildings have numbers
associated with them."*

So a building is FREE TEXT on an instance, not a registry. She said the
numbering varies by property, which makes a fixed list of buildings wrong,
and a building-management feature is not what she asked for.

WHAT WAS ALREADY THERE AND WHAT WAS NOT

`instance_no`, `instance_label` and `add_instance()` have existed since
repeatable items landed, and `add_instance()` already worked at every
scope. `build_lines()` already grouped on the instance label, so two
buildings were already two lines.

Two things were missing, both in the property scope only:

* **The page rendered one instance.** `(items.get(key) or [none])[0]` --
  the first and nothing else. A second roof existed in storage and was
  invisible on the page that was supposed to edit it.
* **There was no cost input at all.** The engine has always accepted a
  manual cost here and a typed figure overrides the researched one, but
  the property form rendered no box, so the path was unreachable at this
  scope. "Roof, Building 3, $35,000" needs both halves.

And one thing was wrong in the export: the instance label REPLACED the
item name, so the line read "Building 3" with no indication that the
$35,000 was a roof.

A LIMITATION THIS DOES NOT REMOVE, PINNED BELOW

Six property items are rate-priced -- roof covering, paving, roof
drainage, facade, flooring, walls -- and for those a manual figure is
still read as a RATE, because the unit belongs to the item rather than to
whoever priced it. So Michelle's own example, a roof at $35,000, records
the building correctly and still produces no total. That is the settled
rule from the $5.75 repaint bug and is not quietly changed here.
"""

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
from tools.site_dd_capex_export import _line_label

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "templates" / "tools" / "site_dd_detail.html"


class TheLineIsNamedForBothTests(unittest.TestCase):
    LABELS = {"roof_covering": "Roof covering", "hvac_units": "HVAC units"}

    def test_a_catalogue_item_keeps_its_own_name(self):
        self.assertEqual(_line_label("roof_covering", "Building 3", self.LABELS),
                         "Roof covering — Building 3")

    def test_two_buildings_read_differently(self):
        self.assertNotEqual(_line_label("roof_covering", "Building 3", self.LABELS),
                            _line_label("roof_covering", "Building 5", self.LABELS))

    def test_no_building_leaves_the_name_alone(self):
        self.assertEqual(_line_label("roof_covering", None, self.LABELS),
                         "Roof covering")
        self.assertEqual(_line_label("roof_covering", "   ", self.LABELS),
                         "Roof covering")

    def test_a_custom_item_is_still_just_its_own_name(self):
        """Somebody adds "Gazebo"; the line should say Gazebo, not
        "None — Gazebo"."""
        self.assertEqual(_line_label("custom_abc", "Gazebo", self.LABELS), "Gazebo")

    def test_it_does_not_repeat_itself(self):
        self.assertEqual(_line_label("hvac_units", "HVAC units", self.LABELS),
                         "HVAC units")


class TwoBuildingsBecomeTwoBudgetLinesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        self.patch = mock.patch.object(db, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with db.get_connection() as conn:
            self.aid = db.create_assessment(conn, {
                "property_label": "Nabob", "assessed_on": "2026-08-24",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def record(self, key, first, second):
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/instance",
                         data={"item_key": key, "scope": "property"})
        base = {"property_label": "Nabob", "assessed_on": "2026-08-24",
                "inspector": "MJ", "status": "draft"}
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/save", data={
            **base,
            f"condition_{key}": "replace", f"label_{key}": first[0],
            f"cost_{key}": str(first[1]),
            f"condition_{key}__2": "replace", f"label_{key}__2": second[0],
            f"cost_{key}__2": str(second[1])})

    def budget(self):
        with db.get_connection() as conn:
            findings = db.list_all_findings(conn, self.aid)
            assessment = db.get_assessment(conn, self.aid)
        catalogue = bank.every_item()
        work = [f for f in findings
                if uc.needs_work(catalogue.get(f.get("item_key")),
                                 f.get("condition"), f.get("detail"))]
        lines = capex.build_lines(
            [costs.apply_reference(f, None) for f in work], dict(cl.ITEM_LABELS))
        return assessment, lines, capex.summarize(lines)

    def test_each_building_is_its_own_line_with_its_own_cost(self):
        self.record("hvac_units", ("Building 3", 35000), ("Building 5", 50000))
        _, lines, summary = self.budget()
        self.assertEqual(len(lines), 2)
        self.assertEqual({l["label"] for l in lines},
                         {"HVAC units — Building 3", "HVAC units — Building 5"})
        self.assertEqual({l["unit_cost"] for l in lines}, {35000.0, 50000.0})
        self.assertEqual(summary["total"], 85000.0)

    def test_the_two_are_not_collapsed_into_one_line(self):
        """The grouping key already carried the instance label; this pins
        it, because collapsing them would average two real roofs."""
        self.record("hvac_units", ("Building 3", 35000), ("Building 5", 50000))
        _, lines, _ = self.budget()
        self.assertEqual(len(lines), 2)

    def test_the_building_reaches_BOTH_exports(self):
        """The PDF and the XLSX have diverged before."""
        from openpyxl import load_workbook
        from pypdf import PdfReader
        self.record("hvac_units", ("Building 3", 35000), ("Building 5", 50000))
        assessment, lines, summary = self.budget()
        d = Path(tempfile.mkdtemp())
        capex.build_xlsx(d / "b.xlsx", assessment, lines, summary,
                         dict(cl.ITEM_LABELS))
        capex.build_pdf(d / "b.pdf", assessment, lines, summary)
        xlsx = " ".join(str(c.value) for row in load_workbook(d / "b.xlsx").active
                        for c in row if c.value is not None)
        pdf = " ".join(p.extract_text() for p in PdfReader(str(d / "b.pdf")).pages)
        for probe in ("Building 3", "Building 5", "HVAC units"):
            with self.subTest(probe=probe):
                self.assertIn(probe, xlsx)
                self.assertIn(probe, pdf)

    def test_a_rate_priced_item_records_the_building_but_still_has_no_total(self):
        """The limitation, pinned rather than papered over.

        A roof is priced per square foot, so a manual $35,000 is read as a
        rate and excluded from the total -- the settled rule from the $5.75
        repaint bug, where the unit belongs to the item rather than to
        whoever typed the figure. The BUILDING is still recorded correctly;
        only the total is withheld.
        """
        self.record("roof_covering", ("Building 3", 35000), ("Building 5", 50000))
        _, lines, summary = self.budget()
        self.assertEqual(len(lines), 2)
        self.assertEqual({l["label"] for l in lines},
                         {"Roof covering — Building 3", "Roof covering — Building 5"})
        self.assertIsNone(summary["total"])
        for line in lines:
            self.assertIsNone(line["total"])
            self.assertTrue(line["is_rate"])


class ThePropertyPageRendersInstancesTests(unittest.TestCase):
    def setUp(self):
        import re
        raw = TPL.read_text(encoding="utf-8")
        self.src = raw
        # Strip {# #} comments before asserting on markup: the comment
        # above this table QUOTES the old expression to explain why it
        # changed, so a raw search finds the explanation rather than the
        # code. Third instance of that collision this session.
        self.markup = re.sub(r"\{#.*?#\}", " ", raw, flags=re.S)

    def test_it_no_longer_renders_only_the_first(self):
        self.assertNotIn("(items.get(key) or [none])[0]", self.markup)

    def test_it_loops_every_instance(self):
        self.assertIn("for row in (items.get(key) or [none])", self.src)

    def test_the_building_is_free_text(self):
        self.assertIn('name="label_{{ key }}{{ sfx }}"', self.src)
        self.assertIn("e.g. Building 3", self.src)

    def test_there_is_a_cost_box_at_last(self):
        self.assertIn('name="cost_{{ key }}{{ sfx }}"', self.src)

    def test_add_another_posts_to_its_own_form(self):
        """A nested form silently misroutes the save; that bug was found
        and fixed once in this module already."""
        self.assertIn('form="propertyInstanceForm"', self.src)
        self.assertIn('id="propertyInstanceForm"', self.src)
        add = self.src.index('id="propertyInstanceForm"')
        checklist_end = self.src.index("</form>", self.src.index("Save Assessment"))
        self.assertGreater(add, checklist_end,
                           "the additive form must sit outside the checklist form")


if __name__ == "__main__":
    unittest.main()

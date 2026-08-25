"""A person who types the figure gets to say what it means.

Michelle: *"Seven buildings, two roofs -- I'd want to manually input
$35,000 or $50,000 myself."* A roof covering is a per-square-foot item, so
until now her own $35,000 was read as a RATE and produced no total. The
tool declined to add up two numbers she had just typed.

THIS IS NOT THE $5.75 DECISION BEING REOPENED

The rule that came out of the repaint bug is about the REFERENCE table: a
researched national average is published per square foot and is a rate
whoever is looking at it. Nothing here touches that -- the toggle is
consulted only when the cost's provenance is `manual`, and a reference
figure on a rate item is still a rate no matter what the toggle says.
`test_a_reference_rate_is_never_converted` is the guard.

What changes is the manual case, and she has already approved the
mechanism: *"yes, please add the toggle for 'per sq ft' or 'per job'. It's
worth the extra click to ensure the data is accurate."*

AND UNSET STILL MEANS UNSET

An unanswered toggle is not resolved to "per job". It falls through and
the line behaves exactly as it did before this branch -- rate, no total,
reference sentence. That absence must not resolve to a default that
decides money is the Part 46 lesson, and the pinned assessment-11 shape
below is the regression test for it.
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
from tools import site_dd_reference_costs as refcosts
from tools import site_dd_unit_checklist as uc
from tools.site_dd_capex_export import _stated_cost_unit

LABELS = dict(cl.ITEM_LABELS)

# Priced per square foot in the reference table -- the case Michelle hit.
RATE_ITEM = "roof_covering"
# Priced per item; it already totalled and must go on doing so.
ITEM_ITEM = "hvac_units"


def finding(item_key, **kw):
    row = {"item_key": item_key, "scope": "property", "condition": "replace",
           "category_key": cl.ITEM_CATEGORY.get(item_key), "detail": None,
           "instance_no": 1, "instance_label": None, "measure": None,
           "est_unit_cost": None, "est_cost_source": costs.SOURCE_NONE,
           "quantity": None}
    row.update(kw)
    return row


def manual(item_key, cost, measure=None, **kw):
    return finding(item_key, est_unit_cost=cost, measure=measure,
                   est_cost_source=costs.SOURCE_MANUAL, **kw)


def one(rows):
    lines = capex.build_lines(rows, LABELS)
    assert len(lines) == 1, lines
    return lines[0]


class TheItemIsStillRatePricedTests(unittest.TestCase):
    """The premise the rest of the file rests on, checked rather than
    assumed. If roof covering stopped being a per-sq-ft item every other
    test here would pass vacuously."""

    def test_roof_covering_is_a_rate_item(self):
        self.assertTrue(refcosts.is_rate(refcosts.for_item(RATE_ITEM).unit))

    def test_hvac_units_is_not(self):
        self.assertFalse(refcosts.is_rate(refcosts.for_item(ITEM_ITEM).unit))


class PerJobOnARatePricedItemTests(unittest.TestCase):
    def test_a_manual_per_job_figure_totals(self):
        line = one([manual(RATE_ITEM, 35000.0, "each")])
        self.assertFalse(line["is_rate"])
        self.assertEqual(line["total"], 35000.0)
        self.assertEqual(line["unit_cost"], 35000.0)

    def test_it_carries_no_why_no_estimate_text(self):
        """A priced line's reason column must be empty; that column is
        headed "Why no estimate" and there now is one."""
        self.assertEqual(one([manual(RATE_ITEM, 35000.0, "each")])["reason"], "")

    def test_two_buildings_at_two_prices_add_up(self):
        lines = capex.build_lines(
            [manual(RATE_ITEM, 35000.0, "each", instance_label="Building 3"),
             manual(RATE_ITEM, 50000.0, "each", instance_no=2,
                    instance_label="Building 5")], LABELS)
        self.assertEqual(len(lines), 2)
        self.assertEqual({l["label"] for l in lines},
                         {"Roof covering — Building 3",
                          "Roof covering — Building 5"})
        self.assertEqual(capex.summarize(lines)["total"], 85000.0)

    def test_the_figure_is_still_labelled_as_a_persons(self):
        """Provenance does not get flattened by gaining a total. A
        $35,000 roof from an inspector must not read like a priced line
        item from a table."""
        line = one([manual(RATE_ITEM, 35000.0, "each")])
        self.assertEqual(line["source"], costs.SOURCE_MANUAL)
        self.assertIn("Inspector", line["source_label"])
        self.assertNotEqual(line["source_label"],
                            capex.SOURCE_COLUMN[costs.SOURCE_REFERENCE])


class TheRuleThatStandsTests(unittest.TestCase):
    def test_per_sq_ft_behaves_exactly_as_before(self):
        line = one([manual(RATE_ITEM, 5.75, "sqft")])
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])
        self.assertIn("Inspector's rate", line["reason"])
        self.assertIn("not included in the budget total", line["reason"])

    def test_a_reference_rate_is_never_converted(self):
        """THE GUARD. A researched national average is published per
        square foot and stays one whatever the toggle says -- the toggle
        describes the number a person typed, and nobody typed this."""
        row = finding(RATE_ITEM, measure="each")
        line = one([costs.apply_reference(row, None)])
        self.assertEqual(line["source"], costs.SOURCE_REFERENCE)
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])
        self.assertIn("Researched reference rate", line["reason"])

    def test_unset_stays_unset_on_a_rate_item(self):
        """No measure at all: the pre-existing behaviour, unchanged. If
        absence resolved to "per job" this would total."""
        line = one([manual(RATE_ITEM, 35000.0)])
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])

    def test_a_per_item_figure_is_unaffected(self):
        line = one([manual(ITEM_ITEM, 7500.0)])
        self.assertFalse(line["is_rate"])
        self.assertEqual(line["total"], 7500.0)

    def test_per_sq_ft_on_a_per_item_item_withholds_rather_than_invents(self):
        """The toggle can only ever move a line toward saying less. An
        inspector who says their $9 hvac figure is per square foot is
        telling us it is a rate, and a rate with nothing measured has no
        total."""
        line = one([manual(ITEM_ITEM, 9.0, "sqft")])
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])


class TheSharedMeasureColumnTests(unittest.TestCase):
    """`measure` also holds the unit of a NUMBER item's READING -- a water
    heater's "gal", an HVAC's "yr" -- written by the route from the item
    catalogue, not by anyone answering the cost toggle. The two
    vocabularies do not overlap today; this makes sure they cannot."""

    def test_todays_reading_units_do_not_collide(self):
        readings = {i["measure"] for i in bank.every_item().values()
                    if i.get("kind") == uc.KIND_NUMBER and i.get("measure")}
        self.assertTrue(readings, "no NUMBER items -- this test is vacuous")
        self.assertEqual(readings & set(refcosts.UNITS), set())

    def test_a_number_items_reading_is_never_read_as_a_cost_unit(self):
        number_key = next(k for k, i in bank.every_item().items()
                          if i.get("kind") == uc.KIND_NUMBER)
        self.assertIsNone(
            _stated_cost_unit(manual(number_key, 200.0, "sqft")))

    def test_positive_control_the_same_measure_is_read_elsewhere(self):
        """Without this, the assertion above would pass if the helper
        simply always returned None."""
        self.assertEqual(_stated_cost_unit(manual(RATE_ITEM, 200.0, "sqft")),
                         "sqft")


class AssessmentElevenShapeTests(unittest.TestCase):
    """Michelle's read-only assessment carries a walls_ceiling line with a
    researched $5.75 per-sq-ft rate, no stored cost and no measure. Its
    line must be identical across this change: same wording, same absent
    total. If that moves, the change is too broad."""

    def line(self):
        return one([costs.apply_reference(
            finding("walls_ceiling", scope="room", condition="repair"), None)])

    def test_no_total(self):
        self.assertIsNone(self.line()["total"])
        self.assertTrue(self.line()["is_rate"])

    def test_the_sentence_is_word_for_word_what_it_was(self):
        ref = refcosts.for_item("walls_ceiling")
        self.assertEqual(
            self.line()["reason"],
            f"Priced by scope, not by this walk: the walk records this "
            f"item's condition, not its area. Researched reference rate "
            f"${ref.unit_cost:,.2f} {refcosts.UNIT_LABELS[ref.unit]} "
            f"(national average, {refcosts.RESEARCHED_ON}), kept as "
            f"reference information for scoping the work — not a total, "
            f"and not included in the budget total.")


class ThroughTheRealRouteTests(unittest.TestCase):
    """The toggle has to arrive from a form at the scope where the cost is
    typed, not just work when handed straight to build_lines()."""

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

    def record(self, measure):
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/instance",
                         data={"item_key": RATE_ITEM, "scope": "property"})
        self.client.post(f"/tools/site-dd/assessment/{self.aid}/save", data={
            "property_label": "Nabob", "assessed_on": "2026-08-24",
            "inspector": "MJ", "status": "draft",
            f"condition_{RATE_ITEM}": "replace",
            f"label_{RATE_ITEM}": "Building 3",
            f"cost_{RATE_ITEM}": "35000", f"measure_{RATE_ITEM}": measure,
            f"condition_{RATE_ITEM}__2": "replace",
            f"label_{RATE_ITEM}__2": "Building 5",
            f"cost_{RATE_ITEM}__2": "50000",
            f"measure_{RATE_ITEM}__2": measure})

    def budget(self):
        with db.get_connection() as conn:
            findings = db.list_all_findings(conn, self.aid)
            assessment = db.get_assessment(conn, self.aid)
        catalogue = bank.every_item()
        work = [f for f in findings
                if uc.needs_work(catalogue.get(f.get("item_key")),
                                 f.get("condition"), f.get("detail"))]
        lines = capex.build_lines(
            [costs.apply_reference(f, None) for f in work], LABELS)
        return assessment, lines, capex.summarize(lines)

    def test_michelles_two_roofs_add_up_to_85000(self):
        self.record("each")
        _, lines, summary = self.budget()
        self.assertEqual(len(lines), 2)
        self.assertEqual({l["label"] for l in lines},
                         {"Roof covering — Building 3",
                          "Roof covering — Building 5"})
        self.assertEqual(summary["total"], 85000.0)

    def test_the_same_two_roofs_per_sq_ft_still_have_no_total(self):
        self.record("sqft")
        _, _, summary = self.budget()
        self.assertIsNone(summary["total"])

    def test_the_stored_measure_survives_the_round_trip(self):
        self.record("each")
        with db.get_connection() as conn:
            rows = db.get_findings(conn, self.aid, None, None)[RATE_ITEM]
        self.assertEqual({r["measure"] for r in rows}, {"each"})

    def test_both_exports_carry_both_buildings(self):
        from openpyxl import load_workbook
        from pypdf import PdfReader
        self.record("each")
        assessment, lines, summary = self.budget()
        d = Path(tempfile.mkdtemp())
        capex.build_xlsx(d / "b.xlsx", assessment, lines, summary, LABELS)
        capex.build_pdf(d / "b.pdf", assessment, lines, summary)
        xlsx = " ".join(str(c.value) for row in load_workbook(d / "b.xlsx").active
                        for c in row if c.value is not None)
        pdf = " ".join(p.extract_text() for p in PdfReader(str(d / "b.pdf")).pages)
        for probe in ("Building 3", "Building 5", "Roof covering"):
            with self.subTest(probe=probe):
                self.assertIn(probe, xlsx)
                self.assertIn(probe, pdf)

    def test_the_pdf_states_the_total(self):
        from pypdf import PdfReader
        self.record("each")
        assessment, lines, summary = self.budget()
        d = Path(tempfile.mkdtemp())
        capex.build_pdf(d / "b.pdf", assessment, lines, summary)
        pdf = " ".join(p.extract_text() for p in PdfReader(str(d / "b.pdf")).pages)
        self.assertIn("85,000", pdf)


class TheToggleIsWhereverACostIsTests(unittest.TestCase):
    """A toggle the export honours but the page never shows is a feature
    only a test can reach."""

    ROOT = Path(__file__).resolve().parents[1] / "templates" / "tools"

    def test_every_cost_input_has_a_unit_select_beside_it(self):
        found = 0
        for tpl in self.ROOT.glob("site_dd_*.html"):
            src = tpl.read_text(encoding="utf-8")
            if 'name="cost_' not in src:
                continue
            found += 1
            with self.subTest(template=tpl.name):
                self.assertIn('name="measure_', src)
        self.assertGreaterEqual(found, 3,
                                "expected a cost input at property, unit and "
                                "room scope -- fewer means the glob missed one")


if __name__ == "__main__":
    unittest.main()

"""Pricing by scope: the arithmetic, end to end.

This is the step where budget figures move, so the tests are weighted
towards the three ways it could move them WRONGLY:

1. a scope with no researched figure silently inheriting the item's --
   the concrete-flooring trap from Part 62, which will reappear on every
   item that gains an option set;
2. a finding recorded before today changing price;
3. the two exports disagreeing, or the coverage sentence describing a
   different budget from the one the lines add up to.

WHAT WAS ACTUALLY BROKEN BEFORE THIS, and it is not what the design
predicted. The design argued from under-pricing -- a rate item that can
never be totalled. The live exposure was the opposite: an EXPENSIVE item
lending its price to a CHEAP job. `toilet` scoped `replace_seat` priced
at $600, the whole toilet, and `entry_door` scoped `tighten_hardware`
priced at $1,450. Nobody had recorded either, so nothing in production
moved -- the exposure was waiting for the first inspector to use the
picker.
"""

import unittest

from tools import site_dd_bank as bank
from tools import site_dd_capex_export as capex
from tools import site_dd_checklist as cl
from tools import site_dd_conditions as cond
from tools import site_dd_costs as costs
from tools import site_dd_reference_costs as refcosts


def finding(item_key, condition="repair", detail=None, **kw):
    row = {"item_key": item_key, "scope": "room", "area_id": 1, "room_id": 2,
           "category_key": "interior_units", "condition": condition,
           "detail": detail, "instance_no": 1, "instance_label": None,
           "quantity": None, "measure": None, "est_unit_cost": None,
           "est_cost_source": costs.SOURCE_NONE, "bank_item_key": None}
    row.update(kw)
    return row


def line_for(row):
    lines = capex.build_lines([costs.apply_reference(row, None)],
                              dict(cl.ITEM_LABELS),
                              detail_labels=bank.detail_labels())
    assert len(lines) == 1
    return lines[0]


class TheScopePriceIsUsedTests(unittest.TestCase):
    """A finding with a scope detail prices at the scope figure."""

    def test_a_seat_is_not_a_toilet(self):
        seat = line_for(finding("toilet", detail="replace_seat"))
        self.assertEqual(seat["unit_cost"], 156.00)

    def test_and_a_toilet_still_is_one(self):
        whole = line_for(finding("toilet", detail="replace_toilet"))
        self.assertEqual(whole["unit_cost"], 600.00)

    def test_reglazing_is_not_a_new_tub(self):
        self.assertEqual(line_for(finding("tub_shower", detail="resurface"))["unit_cost"],
                         479.00)
        self.assertEqual(line_for(finding("tub_shower", detail="replace_tub"))["unit_cost"],
                         3275.00)

    def test_a_lockset_is_not_a_door(self):
        self.assertEqual(
            line_for(finding("entry_door", detail="replace_hardware"))["unit_cost"],
            265.75)
        self.assertEqual(
            line_for(finding("entry_door", detail="replace_door"))["unit_cost"],
            1450.00)

    def test_the_saving_is_the_point(self):
        """Stated as the comparison, because a reader checking this file
        should see the size of what was wrong."""
        before = refcosts.REFERENCE_COSTS["toilet"].unit_cost
        after = line_for(finding("toilet", detail="replace_seat"))["unit_cost"]
        self.assertGreater(before / after, 3.5)


class ARateItemBecomesTotallableTests(unittest.TestCase):
    """The argument for the whole feature: naming the job is something an
    inspector does standing in the room; measuring the walls is not."""

    def test_walls_ceiling_with_no_detail_is_still_an_untotallable_rate(self):
        line = line_for(finding("walls_ceiling"))
        self.assertEqual(line["unit_cost"], 5.75)
        self.assertEqual(line["unit"], refcosts.UNIT_SQFT)
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])

    def test_paint_only_is_a_per_room_job_price_and_totals(self):
        line = line_for(finding("walls_ceiling", detail="paint"))
        self.assertEqual(line["unit_cost"], 637.50)
        self.assertEqual(line["unit"], refcosts.UNIT_EACH)
        self.assertFalse(line["is_rate"])
        self.assertEqual(line["total"], 637.50)

    def test_the_note_says_it_is_a_typical_room(self):
        """A per-room figure is a different kind of claim from $600 for a
        toilet, and the reference sheet must not present them as the
        same. Required by the design, so asserted rather than trusted."""
        entry = refcosts.for_item("walls_ceiling", "paint")
        self.assertIn("PER TYPICAL ROOM", entry.note)
        self.assertIn("100–250", entry.note)

    def test_repair_and_paint_falls_back_and_stays_a_rate(self):
        """No researched figure for the drywall half, so it keeps the
        item rate -- unchanged behaviour, and visibly different from
        paint-only on the same walk."""
        line = line_for(finding("walls_ceiling", detail="repair_and_paint"))
        self.assertEqual(line["unit_cost"], 5.75)
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])


class AnUnpricedItemBecomesPricedTests(unittest.TestCase):
    """dryer_vent was UNPRICED because the item conflated two jobs. The
    scope picker separates them, so both can now be priced -- the feature
    turning an unpriceable item into a budget line."""

    def test_the_item_alone_is_still_unpriced(self):
        line = line_for(finding("dryer_vent"))
        self.assertIsNone(line["unit_cost"])
        self.assertIn("does not say which", line["reason"])

    def test_cleaning_is_priced(self):
        self.assertEqual(line_for(finding("dryer_vent", detail="clean"))["total"],
                         138.75)

    def test_installing_is_priced_higher(self):
        self.assertEqual(line_for(finding("dryer_vent", detail="install"))["total"],
                         385.33)

    def test_the_items_reason_no_longer_claims_the_checklist_cannot_tell(self):
        """It said "the checklist item does not distinguish them", which
        stopped being true the moment the scope picker shipped."""
        self.assertNotIn("does not distinguish",
                         refcosts.UNPRICED["dryer_vent"])


class TheConcreteFlooringTrapTests(unittest.TestCase):
    """A recognised scope we declined to price must NOT fall through to
    the item figure. This is the Part 62 defect, re-tested on the item
    where the fallback would be most expensive."""

    def test_tighten_hardware_is_unpriced_not_a_new_door(self):
        line = line_for(finding("entry_door", detail="tighten_hardware"))
        self.assertIsNone(line["unit_cost"],
                          "tightening a screw was priced as an entry door")
        self.assertIsNone(line["total"])

    def test_the_original_case_still_holds(self):
        self.assertIsNone(refcosts.for_item("flooring", "concrete"))

    def test_positive_control_an_UNRECOGNISED_detail_does_fall_back(self):
        """The other half of the same rule: a value nobody registered is
        not a decision to decline, so it gets the item's figure."""
        self.assertEqual(
            refcosts.for_item("entry_door", "bamboo_something").unit_cost,
            1450.00)


class RemovingAFigureMakesTheLineUnpricedTests(unittest.TestCase):
    """POSITIVE CONTROL ON THE WHOLE MECHANISM. If a scope entry is
    deleted, the line must become unpriced rather than silently reverting
    to the item price -- which is what a reader would assume happened
    given the fallback rule, and is exactly what must not."""

    def test_removing_the_paint_figure_does_not_revert_to_the_rate(self):
        from unittest import mock
        without = {k: v for k, v in refcosts.COST_BY_DETAIL.items()
                   if k != ("walls_ceiling", "paint")}
        unpriced = refcosts.UNPRICED_DETAIL | {("walls_ceiling", "paint")}
        with mock.patch.object(refcosts, "COST_BY_DETAIL", without), \
             mock.patch.object(refcosts, "UNPRICED_DETAIL", unpriced):
            line = line_for(finding("walls_ceiling", detail="paint"))
        self.assertIsNone(line["unit_cost"])

    def test_and_with_the_figure_present_it_prices(self):
        self.assertEqual(
            line_for(finding("walls_ceiling", detail="paint"))["unit_cost"], 637.50)


class TheThreeAppliancesArePricedByConditionTests(unittest.TestCase):
    """Their detail carries PRESENCE, so the job is named by the
    condition beside it. Verified by rendering the form in
    test_sitedd_scope_details; here it is the arithmetic."""

    def test_a_washer_that_needs_repair_is_a_service_call(self):
        line = line_for(finding("washer", condition="repair", detail="present"))
        self.assertEqual(line["unit_cost"], 220.00)

    def test_a_washer_that_needs_replacing_is_a_machine(self):
        line = line_for(finding("washer", condition="replace", detail="present"))
        self.assertEqual(line["unit_cost"], 925.00)

    def test_a_missing_washer_is_a_machine(self):
        """No condition at all -- the work is implied by the presence
        value, and the item figure is the right one."""
        line = line_for(finding("washer", condition=None, detail="absent"))
        self.assertEqual(line["unit_cost"], 925.00)

    def test_a_hookup_with_no_machine_is_also_a_machine(self):
        line = line_for(finding("washer", condition=None, detail="hookup_only"))
        self.assertEqual(line["unit_cost"], 925.00)

    def test_the_dryer_and_the_disposal_behave_the_same_way(self):
        self.assertEqual(
            line_for(finding("dryer", condition="repair", detail="present"))["unit_cost"],
            200.00)
        self.assertEqual(
            line_for(finding("dryer", condition="replace", detail="present"))["unit_cost"],
            925.00)
        self.assertEqual(
            line_for(finding("appliance_disposal", condition="repair",
                             detail="present"))["unit_cost"], 202.50)
        self.assertEqual(
            line_for(finding("appliance_disposal", condition="replace",
                             detail="present"))["unit_cost"], 375.00)

    def test_the_presence_detail_is_not_touched(self):
        """The Part 62 collision, checked rather than argued: pricing by
        condition must leave the detail column meaning presence."""
        row = costs.apply_reference(
            finding("washer", condition="repair", detail="present"), None)
        self.assertEqual(row["detail"], "present")

    def test_no_condition_priced_item_also_has_a_detail_entry(self):
        """The precedence between the two tables is stated in for_item.
        Nothing relies on it today, and this fails the moment something
        does -- at which point the rule needs a test of its own rather
        than an assumption."""
        overlap = ({k[0] for k in refcosts.CONDITION_COSTS}
                   & {k[0] for k in refcosts.COST_BY_DETAIL})
        self.assertEqual(overlap, set())


class NothingRecordedBeforeTodayMovesTests(unittest.TestCase):
    """The migration story, and assessment 11 is the live case."""

    def test_a_condition_with_no_detail_prices_at_the_item_figure(self):
        for key, expected in (("walls_ceiling", 5.75), ("toilet", 600.00),
                              ("tub_shower", 3275.00), ("entry_door", 1450.00)):
            with self.subTest(key=key):
                self.assertEqual(line_for(finding(key))["unit_cost"], expected)

    def test_assessment_11s_line_is_identical(self):
        """Its walls_ceiling row: condition repair, detail NULL. Same
        price, same unit, same rate status, still untotallable."""
        line = line_for(finding("walls_ceiling", condition=cond.REPAIR))
        self.assertEqual(line["unit_cost"], 5.75)
        self.assertEqual(line["unit"], refcosts.UNIT_SQFT)
        self.assertTrue(line["is_rate"])
        self.assertIsNone(line["total"])
        self.assertIn("Priced by scope, not by this walk", line["reason"])

    def test_an_unpriced_item_with_no_scope_is_still_unpriced(self):
        self.assertIsNone(line_for(finding("closet"))["unit_cost"])
        self.assertIsNone(line_for(finding("dryer_vent"))["unit_cost"])


class ClosetStaysUnpricedAndSaysWhyTests(unittest.TestCase):
    """A partial table is honest; a complete one built from estimates is
    not. Closet is the item where the temptation was strongest, because
    the option set is already written."""

    def test_every_closet_scope_is_unpriced(self):
        for value, _ in bank.every_item()["closet"]["options"]:
            with self.subTest(value=value):
                self.assertIsNone(refcosts.for_item("closet", value))

    def test_the_reason_names_what_was_looked_at_and_rejected(self):
        reason = refcosts.UNPRICED["closet"]
        self.assertIn("curtain", reason.lower())
        self.assertIn("linear foot", reason.lower())

    def test_no_closet_scope_sneaked_into_the_table(self):
        self.assertEqual([k for k in refcosts.COST_BY_DETAIL if k[0] == "closet"], [])


class BothExportsAgreeTests(unittest.TestCase):
    """The XLSX and the PDF read the same lines, and the coverage
    sentence must describe the same budget the lines add up to."""

    def rows(self):
        return [costs.apply_reference(f, None) for f in (
            finding("walls_ceiling", detail="paint"),
            finding("toilet", detail="replace_seat"),
            finding("dryer_vent", detail="clean"),
            finding("entry_door", detail="tighten_hardware"),
            finding("closet"),
        )]

    def test_the_summary_totals_only_the_priced_lines(self):
        lines = capex.build_lines(self.rows(), dict(cl.ITEM_LABELS),
                                  detail_labels=bank.detail_labels())
        summary = capex.summarize(lines)
        self.assertEqual(summary["priced_total"], 637.50 + 156.00 + 138.75)
        self.assertEqual(summary["line_count"], 5)
        self.assertEqual(summary["unpriced_count"], 2)

    def test_the_coverage_sentence_counts_the_same_lines(self):
        lines = capex.build_lines(self.rows(), dict(cl.ITEM_LABELS),
                                  detail_labels=bank.detail_labels())
        summary = capex.summarize(lines)
        sentence = summary["coverage_sentence"]
        self.assertIn("3", sentence)
        self.assertIn("5", sentence)

    def test_the_xlsx_writes_the_same_totals(self):
        import tempfile
        from pathlib import Path
        import openpyxl
        lines = capex.build_lines(self.rows(), dict(cl.ITEM_LABELS),
                                  detail_labels=bank.detail_labels())
        summary = capex.summarize(lines)
        out = Path(tempfile.mkdtemp()) / "b.xlsx"
        capex.build_xlsx(out, {"property_label": "X", "assessed_on": "2026-08-31",
                               "inspector": "MJ", "id": 1},
                         lines, summary, dict(cl.ITEM_LABELS))
        values = {c.value for ws in openpyxl.load_workbook(out).worksheets
                  for row in ws.iter_rows() for c in row}
        for figure in (637.50, 156.00, 138.75):
            self.assertIn(figure, values)

    def test_the_pdf_builds_at_this_shape(self):
        """It paginates by measured height, so a new unit label or a
        longer note is the kind of thing that breaks it."""
        import tempfile
        from pathlib import Path
        lines = capex.build_lines(self.rows(), dict(cl.ITEM_LABELS),
                                  detail_labels=bank.detail_labels())
        out = Path(tempfile.mkdtemp()) / "b.pdf"
        capex.build_pdf(out, {"property_label": "X", "assessed_on": "2026-08-31",
                              "inspector": "MJ", "id": 1},
                        lines, capex.summarize(lines))
        self.assertGreater(out.stat().st_size, 1000)


class TheDateTravelsWithTheEntryTests(unittest.TestCase):
    """Bumping RESEARCHED_ON would have asserted that all 36 original
    figures were re-verified today. They were not."""

    def test_the_module_date_is_unchanged(self):
        self.assertEqual(refcosts.RESEARCHED_ON, "2026-08-15")

    def test_an_original_entry_still_reports_the_original_date(self):
        self.assertEqual(refcosts.REFERENCE_COSTS["toilet"].dated, "2026-08-15")

    def test_a_scope_entry_reports_its_own(self):
        self.assertEqual(refcosts.for_item("toilet", "replace_seat").dated,
                         "2026-08-31")

    def test_the_capture_screen_shows_the_entrys_date(self):
        hint = costs.reference_hint(finding("toilet", detail="replace_seat"))
        self.assertEqual(hint["researched_on"], "2026-08-31")


if __name__ == "__main__":
    unittest.main()

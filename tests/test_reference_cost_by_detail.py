"""Reference prices that depend on WHICH JOB, not only which item.

Step 4 of `docs/site-dd-detail-values.md`, built first because Part 58
promoted it from housekeeping to prerequisite.

WHY IT HAD TO COME FIRST

Part 54 built a unit-resolution layer in `build_lines()` where a MANUAL
figure's unit can be overridden by the per-job toggle and a REFERENCE
figure's cannot. So whatever `for_item()` returns is the last word on how
a reference-priced line is measured. `COST_BY_DETAIL` invites
detail-dependent units -- "repaint" per square foot and "replace drywall"
per job on one item key -- and if the detail does not reach `for_item()`
the line is measured wrongly with nobody able to correct it.

THIS STEP CHANGES NO PRICES AND NO BEHAVIOUR

`COST_BY_DETAIL` carries only the flooring entries that already existed,
derived from `FLOORING_BY_TYPE` rather than transcribed from it. The
proof is `TheOutputIsUnchangedTests` below and, on real data, assessment
11's capex output hashing identically before and after.

THE DISTINCTION THE DESIGN SKETCH DROPPED

Section 4 proposes falling through to the item-level entry whenever the
detail is not in `COST_BY_DETAIL`. That is right for an unrecognised
detail and wrong for one we deliberately declined to price: concrete
flooring returns None today, and falling through would have quietly
repriced it at $6.50/sqft. `UNPRICED_DETAIL` keeps the two apart, and
`ConcreteIsNotRepricedTests` is the guard.
"""

import unittest

from tools import site_dd_costs as costs
from tools import site_dd_reference_costs as refcosts


class TheFlooringTableIsUnchangedTests(unittest.TestCase):
    """Every material must resolve exactly as it did when flooring was a
    hard-coded `if` inside for_item()."""

    EXPECTED = {
        None: 6.50, "": 6.50,
        "carpet": 3.50, "laminate": 5.00, "vinyl": 6.50,
        "hardwood": 12.75, "tile": 13.50,
        "concrete": None,
        "bamboo": 6.50,          # unrecognised -> the item's own figure
    }

    def test_every_material_resolves_as_before(self):
        for detail, expected in self.EXPECTED.items():
            with self.subTest(detail=detail):
                got = refcosts.for_item("flooring", detail)
                if expected is None:
                    self.assertIsNone(got)
                else:
                    self.assertIsNotNone(got)
                    self.assertEqual(got.unit_cost, expected)

    def test_the_unit_is_still_per_square_foot(self):
        for detail in ("carpet", "tile", None, "bamboo"):
            with self.subTest(detail=detail):
                self.assertEqual(refcosts.for_item("flooring", detail).unit,
                                 refcosts.UNIT_SQFT)

    def test_the_note_still_names_the_material(self):
        self.assertIn("Carpet", refcosts.for_item("flooring", "carpet").note)
        self.assertIn("Tile", refcosts.for_item("flooring", "tile").note)


class OneSourceOfTruthForTheRatesTests(unittest.TestCase):
    """Six rates copied by hand is six chances to mistype a price into a
    budget. COST_BY_DETAIL is derived from FLOORING_BY_TYPE."""

    def test_every_priced_material_is_in_the_lookup(self):
        for material, rate in refcosts.FLOORING_BY_TYPE.items():
            if not rate:
                continue
            with self.subTest(material=material):
                entry = refcosts.COST_BY_DETAIL[("flooring", material)]
                self.assertEqual(entry.unit_cost, rate)

    def test_the_scope_entries_are_exactly_the_researched_ones(self):
        """WAS `nothing else has been added yet`, which pinned the state
        between shipping the mechanism and doing the research. The
        research landed in Part 81, so the assertion becomes the list --
        an entry appearing here without a source and a note is a budget
        change nobody reviewed, which is the thing that test was really
        protecting against.
        """
        non_flooring = {k for k in refcosts.COST_BY_DETAIL if k[0] != "flooring"}
        self.assertEqual(non_flooring, {
            ("walls_ceiling", "paint"),
            ("toilet", "replace_seat"),
            ("tub_shower", "resurface"),
            ("entry_door", "paint"),
            ("entry_door", "repair_door"),
            ("entry_door", "replace_hardware"),
            ("dryer_vent", "clean"),
            ("dryer_vent", "install"),
        })

    def test_every_scope_entry_carries_sources_a_note_and_a_date(self):
        """The no-fabricated-authority rule, as an assertion rather than
        a habit."""
        for key, entry in refcosts.COST_BY_DETAIL.items():
            if key[0] == "flooring":
                continue
            with self.subTest(key=key):
                self.assertTrue(entry.sources, "no source named")
                self.assertGreater(len(entry.note), 80, "no stated arithmetic")
                self.assertTrue(entry.researched_on, "no research date")
                self.assertGreater(entry.unit_cost, 0)

    def test_the_entries_keep_the_item_key_not_the_detail(self):
        """A flooring line is still a flooring line."""
        for (item_key, _), entry in refcosts.COST_BY_DETAIL.items():
            with self.subTest(item_key=item_key):
                self.assertEqual(entry.key, item_key)


class ConcreteIsNotRepricedTests(unittest.TestCase):
    """The case the design sketch would have broken."""

    def test_concrete_still_has_no_figure(self):
        self.assertIsNone(refcosts.for_item("flooring", "concrete"))

    def test_it_is_listed_as_deliberate_rather_than_missing(self):
        self.assertIn(("flooring", "concrete"), refcosts.UNPRICED_DETAIL)

    def test_positive_control_an_unknown_material_DOES_fall_back(self):
        """Without this, the assertion above would pass on a lookup that
        returned None for every detail it did not recognise -- which
        would silently unprice every flooring finding."""
        got = refcosts.for_item("flooring", "terrazzo")
        self.assertIsNotNone(got)
        self.assertEqual(got.unit_cost,
                         refcosts.REFERENCE_COSTS["flooring"].unit_cost)

    def test_the_two_answers_are_different(self):
        self.assertNotEqual(refcosts.for_item("flooring", "concrete"),
                            refcosts.for_item("flooring", "terrazzo"))


class TheDetailComesFromTheFindingTests(unittest.TestCase):
    """`reference_for` had to be told the detail or it would price a seat
    replacement as a whole toilet. It reads the finding by default."""

    def finding(self, **kw):
        row = {"item_key": "toilet", "detail": None, "condition": "replace",
               "est_cost_source": costs.SOURCE_NONE, "est_unit_cost": None}
        row.update(kw)
        return row

    def test_it_reads_the_findings_own_detail(self):
        seen = {}
        real = refcosts.for_item

        def spy(item_key, detail=None):
            seen["args"] = (item_key, detail)
            return real(item_key, detail)

        refcosts.for_item = spy
        try:
            costs.reference_for(self.finding(detail="replace_seat"))
        finally:
            refcosts.for_item = real
        self.assertEqual(seen["args"], ("toilet", "replace_seat"))

    def test_an_explicit_argument_wins(self):
        """Flooring keeps its material on a SIBLING row, so the caller
        passes it in. That override must beat the finding's own detail,
        which for a flooring finding is NULL."""
        got = costs.reference_for(
            self.finding(item_key="flooring", detail=None), "tile")
        self.assertEqual(got.unit_cost, 13.50)

    def test_no_detail_anywhere_gives_the_item_figure(self):
        got = costs.reference_for(self.finding())
        self.assertEqual(got.unit_cost,
                         refcosts.REFERENCE_COSTS["toilet"].unit_cost)

    def test_apply_reference_takes_the_same_argument(self):
        out = costs.apply_reference(
            self.finding(item_key="flooring", detail=None), "carpet")
        self.assertEqual(out["est_unit_cost"], 3.50)
        self.assertEqual(out["est_cost_source"], costs.SOURCE_REFERENCE)

    def test_reference_hint_takes_the_same_argument(self):
        hint = costs.reference_hint(
            self.finding(item_key="flooring", detail=None), "hardwood")
        self.assertEqual(hint["unit_cost"], 12.75)

    def test_a_manual_figure_is_still_never_overwritten(self):
        out = costs.apply_reference(
            self.finding(detail="replace_seat",
                         est_cost_source=costs.SOURCE_MANUAL,
                         est_unit_cost=90.0))
        self.assertEqual(out["est_unit_cost"], 90.0)
        self.assertEqual(out["est_cost_source"], costs.SOURCE_MANUAL)


class TheExportNoLongerNamesFlooringTests(unittest.TestCase):
    """The call site that passed None on every call it was written for."""

    def test_the_special_case_is_gone_from_the_code(self):
        import re
        from pathlib import Path
        src = Path(refcosts.__file__).parent / "site_dd_capex_export.py"
        code = re.sub(r"#.*", "", src.read_text(encoding="utf-8"))
        self.assertNotIn('== "flooring"', code)

    def test_the_lookup_is_given_the_findings_detail(self):
        import re
        from pathlib import Path
        src = Path(refcosts.__file__).parent / "site_dd_capex_export.py"
        code = re.sub(r"#.*", "", src.read_text(encoding="utf-8"))
        self.assertIn('refcosts.for_item(f.get("item_key"), f.get("detail"))',
                      code)


class TheOutputIsUnchangedTests(unittest.TestCase):
    """Assessment 11's shape, which is the read-only production case.

    Its one work item is a walls_ceiling repair with no stored cost, so
    `apply_reference` supplies the researched $5.75/sqft rate. Nothing in
    this step may move it."""

    def test_walls_ceiling_still_prices_at_the_researched_rate(self):
        row = {"item_key": "walls_ceiling", "detail": None,
               "condition": "repair", "est_cost_source": costs.SOURCE_NONE,
               "est_unit_cost": None}
        out = costs.apply_reference(row, None)
        self.assertEqual(out["est_unit_cost"], 5.75)
        self.assertEqual(out["est_cost_source"], costs.SOURCE_REFERENCE)
        self.assertEqual(out["_reference"].unit, refcosts.UNIT_SQFT)

    def test_every_item_level_price_is_untouched(self):
        """The whole table, not a sample: this step must not have moved
        any figure at all."""
        for key, entry in refcosts.REFERENCE_COSTS.items():
            with self.subTest(key=key):
                self.assertIs(refcosts.for_item(key), entry)


if __name__ == "__main__":
    unittest.main()

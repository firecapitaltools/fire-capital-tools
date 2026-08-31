"""A decision not to price something owns its reason.

THE MECHANISM, STATED ONCE

An unpriced line's "why" used to be chosen by whatever NOTICED the
absence rather than by whatever MADE the decision. `_unpriced_reason`
asked the item, the item was priced, and the line printed *"No cost was
recorded on this finding"* -- which blames the inspector for a decision
the reference table made.

Part 81 fixed that for the two pairs it knew about. This file is the
audit of whether the mechanism could produce a third, and the answer was
yes, in two more places:

* `unpriced_report()` -- the "Not priced" sheet, whose entire job is
  listing what has no researched figure, omitted every declined pair.
  Worse than silence: their ITEMS appear on the priced sheet, so a
  reader of both would conclude the scope was covered.
* `status()` -- answered "priced" for `entry_door` + `tighten_hardware`,
  because the item is priced. An instrument answering about the wrong
  subject.

THE STRUCTURAL FIX is that the reason is now the DEFINITION.
`UNPRICED_DETAIL` is derived from `UNPRICED_DETAIL_REASONS`, so a pair
cannot be declined without a sentence saying why, and an import-time
check closes the door the derivation opened for zero-rate flooring
materials.
"""

import unittest
from unittest import mock

from tools import site_dd_bank as bank
from tools import site_dd_capex_export as capex
from tools import site_dd_reference_costs as refcosts


class TheDeclineIsItsReasonTests(unittest.TestCase):

    def test_the_set_is_derived_from_the_reasons(self):
        self.assertEqual(refcosts.UNPRICED_DETAIL,
                         frozenset(refcosts.UNPRICED_DETAIL_REASONS))

    def test_every_declined_pair_has_a_real_sentence(self):
        for pair, why in refcosts.UNPRICED_DETAIL_REASONS.items():
            with self.subTest(pair=pair):
                self.assertGreater(len(why), 60)
                self.assertTrue(why.strip().endswith("."))

    def test_a_zero_rate_material_without_a_reason_is_refused(self):
        """POSITIVE CONTROL on the import-time guard. Without it, adding
        a material at 0.0 and forgetting the sentence would fall through
        to the general flooring rate -- the Part 62 defect, returning by
        omission rather than by design."""
        with mock.patch.object(refcosts, "FLOORING_BY_TYPE",
                               dict(refcosts.FLOORING_BY_TYPE, terrazzo=0.0)):
            with self.assertRaises(AssertionError) as ctx:
                refcosts._check_declines_have_reasons()
        self.assertIn("terrazzo", str(ctx.exception))
        self.assertIn("UNPRICED_DETAIL_REASONS", str(ctx.exception))

    def test_and_it_passes_as_the_table_actually_stands(self):
        refcosts._check_declines_have_reasons()


class StatusAnswersAboutThePairTests(unittest.TestCase):

    def test_a_declined_scope_is_unpriced_even_though_its_item_is_priced(self):
        self.assertEqual(refcosts.status("entry_door"), "priced")
        self.assertEqual(refcosts.status("entry_door", "tighten_hardware"),
                         "unpriced")

    def test_a_priced_scope_is_priced(self):
        self.assertEqual(refcosts.status("entry_door", "replace_hardware"),
                         "priced")

    def test_an_unrecognised_scope_answers_for_the_item(self):
        """It falls back to the item's price, so it must answer with the
        item's status -- the two have to agree or one of them is lying."""
        self.assertEqual(refcosts.status("entry_door", "bamboo_something"),
                         "priced")

    def test_concrete_flooring_is_unpriced_where_flooring_is_not(self):
        self.assertEqual(refcosts.status("flooring"), "priced")
        self.assertEqual(refcosts.status("flooring", "concrete"), "unpriced")


class ReasonAnswersAboutThePairTests(unittest.TestCase):

    def test_the_pairs_reason_wins(self):
        self.assertIn("adjustment rather than a job",
                      refcosts.reason("entry_door", "tighten_hardware"))

    def test_the_items_reason_still_answers_without_a_detail(self):
        self.assertIn("No published figure", refcosts.reason("closet"))

    def test_an_undeclined_pair_falls_back_to_the_item(self):
        self.assertIn("No published figure",
                      refcosts.reason("closet", "replace_rod"))


class TheNotPricedSheetListsDeclinedScopesTests(unittest.TestCase):
    """The sheet is the ask. A scope we declined belongs on it, in the
    words the inspector saw."""

    def rows(self):
        labels = {"entry_door": "Entry door & lock", "flooring": "Flooring"}
        return refcosts.unpriced_report(labels, bank.detail_labels())

    def test_the_declined_pairs_appear(self):
        labels = [r["label"] for r in self.rows()]
        self.assertIn("Entry door & lock — Tighten hardware", labels)

    def test_with_their_own_reason(self):
        row = next(r for r in self.rows()
                   if r["label"].startswith("Entry door & lock —"))
        self.assertIn("adjustment rather than a job", row["reason"])

    def test_the_key_names_both_halves(self):
        row = next(r for r in self.rows()
                   if r["label"].startswith("Entry door & lock —"))
        self.assertEqual(row["key"], "entry_door / tighten_hardware")

    def test_the_item_level_entries_are_still_all_there(self):
        keys = {r["key"] for r in self.rows()}
        for item in refcosts.UNPRICED:
            with self.subTest(item=item):
                self.assertIn(item, keys)

    def test_the_count_is_items_plus_pairs(self):
        self.assertEqual(len(self.rows()),
                         len(refcosts.UNPRICED) + len(refcosts.UNPRICED_DETAIL_REASONS))


class TheReferenceSheetDisclosesEveryFigureTests(unittest.TestCase):
    """A budget line priced at $637.50 was traceable to nothing: the
    sheet listed REFERENCE_COSTS only, and the repaint figure lives in
    COST_BY_DETAIL. Section 6 of the design calls this a disclosure
    obligation, and shipping the figures without it left the obligation
    unmet for one merge."""

    def sheet(self):
        import tempfile
        from pathlib import Path
        import openpyxl
        from tools import site_dd_checklist as cl
        from tools import site_dd_costs as costs
        row = {"item_key": "walls_ceiling", "scope": "room", "area_id": 1,
               "room_id": 2, "category_key": "interior_units",
               "condition": "repair", "detail": "paint", "instance_no": 1,
               "instance_label": None, "quantity": None, "measure": None,
               "est_unit_cost": None, "est_cost_source": costs.SOURCE_NONE,
               "bank_item_key": None}
        lines = capex.build_lines([costs.apply_reference(row, None)],
                                  dict(cl.ITEM_LABELS),
                                  detail_labels=bank.detail_labels())
        out = Path(tempfile.mkdtemp()) / "b.xlsx"
        capex.build_xlsx(out, {"property_label": "X", "assessed_on": "2026-08-31",
                               "inspector": "MJ", "id": 1},
                         lines, capex.summarize(lines), dict(cl.ITEM_LABELS))
        wb = openpyxl.load_workbook(out)
        return [[c.value for c in r] for r in wb["Reference costs"].iter_rows()]

    def test_the_figure_the_line_was_priced_from_is_on_the_sheet(self):
        values = {c for row in self.sheet() for c in row}
        self.assertIn(637.50, values)

    def test_every_scope_and_condition_entry_is_disclosed(self):
        keys = {row[1] for row in self.sheet()}
        for (item_key, detail) in refcosts.COST_BY_DETAIL:
            with self.subTest(pair=(item_key, detail)):
                self.assertIn(f"{item_key} / {detail}", keys)
        for (item_key, condition) in refcosts.CONDITION_COSTS:
            with self.subTest(pair=(item_key, condition)):
                self.assertIn(f"{item_key} / condition {condition}", keys)

    def test_each_discloses_its_sources_and_derivation(self):
        rows = [r for r in self.sheet() if r[1] and " / " in str(r[1])]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(key=row[1]):
                self.assertTrue(row[4], "no sources column")
                self.assertTrue(row[5], "no derivation note")

    def test_the_original_items_are_still_listed(self):
        keys = {row[1] for row in self.sheet()}
        for key in refcosts.REFERENCE_COSTS:
            with self.subTest(key=key):
                self.assertIn(key, keys)


class TheLineStillSaysWhyTests(unittest.TestCase):
    """The Part 81 fix, re-asserted here so this file is the whole story
    of the mechanism rather than half of it."""

    def test_the_export_asks_with_the_detail(self):
        import ast, inspect, textwrap
        tree = ast.parse(textwrap.dedent(inspect.getsource(capex.build_lines)))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "_unpriced_reason"]
        self.assertTrue(calls)
        for call in calls:
            self.assertEqual(len(call.args), 2, "the detail was not passed")


if __name__ == "__main__":
    unittest.main()

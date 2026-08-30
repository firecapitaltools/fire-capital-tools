"""What the budget calls a line, once it can carry three facts.

`Toilet — Powder room (Replace seat)`: what the item is, WHERE it is, and
WHICH JOB it needs.

WHY NOT A SUFFIX

`docs/site-dd-detail-values.md` §6 proposed appending the scope after an
em dash. That was written when `instance_label` REPLACED the item name.
Part 53 changed it to JOIN them with an em dash, so a suffix now produces
`Toilet — Powder room — replace seat`: two identical separators and no
way to tell the place from the job. Parentheses give the third fact its
own marker and leave every shipped label byte-identical.

WHY THE SCOPE IS SOMETIMES ABSENT

`state` prints the condition when there is a valid one and falls back to
the detail when there is not. A choice finding -- a missing alarm --
therefore already shows its detail in that column, and repeating it in
the label would print "Missing" twice on one row. A scope finding has a
valid condition, so `state` shows "Replace" and the detail appears
nowhere else. The rule is written as a condition on `state`'s own
behaviour rather than as a list of scope items, so a seventh scope item
needs no edit and cannot be forgotten.

ONE IMPLEMENTATION, BOTH EXPORTS

The XLSX writes `l["label"]` and the PDF reads the same key, so composing
it once in `_line_label()` is what keeps them from diverging -- which
they have done before. `coverage_sentence()` is the precedent.
"""

import tempfile
import unittest
from pathlib import Path

from tools import site_dd_bank as bank
from tools import site_dd_capex_export as capex
from tools import site_dd_checklist as cl
from tools import site_dd_costs as costs
from tools import site_dd_unit_checklist as uc
from tools.site_dd_capex_export import _line_label

LABELS = {"toilet": "Toilet", "roof_covering": "Roof covering",
          "walls_ceiling": "Walls & ceiling"}


def real_labels():
    """The label map the real caller assembles, not cl.ITEM_LABELS alone.

    site_dd.py builds it from all four sources. Passing only the property
    checklist's map -- which was the first version of this test -- makes
    every room item fall back to its raw key, so the assertions read
    'toilet' instead of 'Toilet' and pass or fail for the wrong reason.
    """
    out = dict(cl.ITEM_LABELS)
    for room_type, _ in uc.ROOM_TYPES:
        out.update({i["key"]: i["label"] for i in uc.items_for_room(room_type)})
    out.update({i["key"]: i["label"] for i in uc.items_for_unit()})
    out.update({b["key"]: b["label"] for b in bank.BANK_ITEMS})
    return out


class ThreeFactsTwoSeparatorsTests(unittest.TestCase):
    def test_item_only(self):
        self.assertEqual(_line_label("toilet", None, LABELS), "Toilet")

    def test_item_and_scope(self):
        self.assertEqual(_line_label("toilet", None, LABELS, "Replace seat"),
                         "Toilet (Replace seat)")

    def test_item_and_place(self):
        self.assertEqual(_line_label("toilet", "Powder room", LABELS),
                         "Toilet — Powder room")

    def test_all_three(self):
        self.assertEqual(
            _line_label("toilet", "Powder room", LABELS, "Replace seat"),
            "Toilet — Powder room (Replace seat)")

    def test_the_place_and_the_job_are_told_apart(self):
        """The whole reason a suffix was rejected."""
        label = _line_label("toilet", "Powder room", LABELS, "Replace seat")
        self.assertEqual(label.count(" — "), 1)
        self.assertIn("(Replace seat)", label)
        self.assertNotIn("— Replace seat", label)

    def test_a_custom_item_keeps_its_own_name(self):
        self.assertEqual(_line_label("custom_abc", "Gazebo", LABELS, "Repair"),
                         "Gazebo (Repair)")

    def test_it_does_not_repeat_itself(self):
        self.assertEqual(_line_label("toilet", "Toilet", LABELS), "Toilet")

    def test_an_empty_scope_adds_nothing(self):
        for empty in (None, "", "   "):
            with self.subTest(scope=empty):
                self.assertEqual(_line_label("toilet", None, LABELS, empty),
                                 "Toilet")


class ShippedLabelsAreByteIdenticalTests(unittest.TestCase):
    """Part 53 and Part 54 verified these against production data. The
    third fact must not have moved them."""

    def test_the_building_instance_label_is_unchanged(self):
        self.assertEqual(_line_label("roof_covering", "Building 3", LABELS),
                         "Roof covering — Building 3")

    def test_two_buildings_still_read_differently(self):
        self.assertNotEqual(_line_label("roof_covering", "Building 3", LABELS),
                            _line_label("roof_covering", "Building 5", LABELS))

    def test_no_instance_still_leaves_the_name_alone(self):
        self.assertEqual(_line_label("roof_covering", None, LABELS),
                         "Roof covering")


class TheScopeDoesNotRepeatTheStateColumnTests(unittest.TestCase):
    """Derived from `state`'s own rule, not from a list of items."""

    def build(self, **kw):
        row = {"item_key": "toilet", "scope": "room", "condition": "replace",
               "detail": None, "instance_no": 1, "instance_label": None,
               "measure": None, "quantity": None,
               "category_key": "interior_units",
               "est_unit_cost": None, "est_cost_source": costs.SOURCE_NONE}
        row.update(kw)
        lines = capex.build_lines([costs.apply_reference(row, None)],
                                  real_labels(),
                                  detail_labels=bank.detail_labels())
        self.assertEqual(len(lines), 1)
        return lines[0]

    def test_a_scope_finding_shows_the_job_in_the_label(self):
        line = self.build(detail="replace_seat")
        self.assertIn("Replace seat", line["label"])

    def test_and_the_state_column_still_shows_the_condition(self):
        line = self.build(detail="replace_seat")
        self.assertEqual(line["state"], "Replace")

    def test_a_presence_finding_does_NOT_repeat_its_detail(self):
        """A missing alarm's detail is already in `state`. Saying it in
        the label too would print it twice on one row."""
        line = self.build(item_key="smoke_alarm_unit", scope="unit",
                          condition=None, detail="missing",
                          category_key="life_safety")
        self.assertEqual(line["state"], "Missing")
        self.assertNotIn("(Missing)", line["label"])

    def test_positive_control_that_row_DOES_reach_the_budget(self):
        """Without this, the assertion above would pass on a finding that
        produced no line at all."""
        line = self.build(item_key="smoke_alarm_unit", scope="unit",
                          condition=None, detail="missing",
                          category_key="life_safety")
        self.assertTrue(line["label"])

    def test_a_detail_with_no_condition_and_no_label_adds_nothing(self):
        line = self.build(detail="not_a_real_option")
        self.assertNotIn("(", line["label"])


class BothExportsCarryItTests(unittest.TestCase):
    """The PDF and the XLSX have diverged before."""

    def lines(self):
        rows = [{"item_key": "toilet", "scope": "room", "condition": "replace",
                 "detail": d, "instance_no": i, "instance_label": None,
                 "measure": None, "quantity": None,
                 "category_key": "interior_units", "est_unit_cost": 90.0,
                 "est_cost_source": costs.SOURCE_MANUAL, "measure": "each"}
                for i, d in ((1, "replace_seat"), (2, "replace_toilet"))]
        return capex.build_lines(rows, real_labels(),
                                 detail_labels=bank.detail_labels())

    def test_two_scopes_are_two_lines(self):
        lines = self.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual({l["label"] for l in lines},
                         {"Toilet (Replace seat)", "Toilet (Replace toilet)"})

    def test_both_files_name_both_jobs(self):
        from openpyxl import load_workbook
        from pypdf import PdfReader
        lines = self.lines()
        summary = capex.summarize(lines)
        assessment = {"property_label": "Nabob", "assessed_on": "2026-08-29"}
        d = Path(tempfile.mkdtemp())
        capex.build_xlsx(d / "b.xlsx", assessment, lines, summary,
                         real_labels())
        capex.build_pdf(d / "b.pdf", assessment, lines, summary)
        xlsx = " ".join(str(c.value) for row in load_workbook(d / "b.xlsx").active
                        for c in row if c.value is not None)
        pdf = " ".join(p.extract_text() for p in PdfReader(str(d / "b.pdf")).pages)
        for probe in ("Replace seat", "Replace toilet"):
            with self.subTest(probe=probe):
                self.assertIn(probe, xlsx)
                self.assertIn(probe, pdf)

    def test_the_label_is_composed_in_exactly_one_place(self):
        """One implementation, both exports -- the coverage_sentence
        precedent. If a second site formatted a label the two files could
        drift again."""
        src = (Path(capex.__file__)).read_text(encoding="utf-8")
        self.assertEqual(src.count('f"{base} ({scope})"'), 1)
        self.assertEqual(src.count("_line_label("), 2)   # def + one call


if __name__ == "__main__":
    unittest.main()

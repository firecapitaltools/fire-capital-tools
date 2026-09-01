"""The expense-aggregation rules, checked where every machine can run them.

WHAT MOVED, AND WHAT DID NOT

`tests/test_underwriting_math.py` asserts these same rules against four
real T12 files. Those files are Michelle's and cannot be committed, so
they live in one Downloads folder, and on the container all nineteen of
those tests skipped silently -- including the naive-sum trap, which is
the single most valuable check in that file. **A check that runs on one
laptop is a check that stops existing when that laptop does.**

So the SHAPE of those files is committed instead, with every figure
regenerated from arithmetic. See `tools/t12_fixture.py` for what is kept
and what is thrown away.

**The real-file tests are not deleted and must not be.** This fixture
proves the code handles four shapes we have already seen. Only a real
file can show a shape nobody has seen, and that is what those tests are
for -- they are now a second layer rather than the only one.

THE ONE CLAIM WORTH PROVING RATHER THAN STATING

That the fixture carries none of her money. `ItCarriesNoRealFiguresTests`
recomputes every cell from the published formula and compares. A single
real number surviving anywhere makes it fail. A generator that leaks one
figure is worse than not doing this at all, and a docstring promising it
did not is exactly the kind of evidence this project has already been
caught accepting.
"""

import unittest

from tools.scorecard_pro.kpis import KPICalculator
from tools.t12_fixture import (DISAGREEMENT, MONTHS, build, load_fixture,
                               synthetic_amount)

SHAPES = load_fixture()
TREES = ("Eagle Rock", "Canyon", "OXPT")
FLAT = "Jackson"


def built(name):
    return build(SHAPES[name])


def breakdown(name):
    return KPICalculator(built(name)).category_breakdown()


def naive_sum(data):
    """What summing every 6xxx/7xxx account gives you: the trap."""
    return sum(sum(v or 0.0 for v in a["data"].values())
               for c, a in data["accounts"].items() if str(c)[:1] in "67")


class TheFixtureIsThereAtAllTests(unittest.TestCase):
    """Assert the population before asserting about its contents. Every
    test below passes vacuously against an empty fixture."""

    def test_all_four_shapes_are_present(self):
        self.assertEqual(sorted(SHAPES), sorted(TREES + (FLAT,)))

    def test_they_are_not_trivially_small(self):
        for name in TREES:
            with self.subTest(property=name):
                self.assertGreater(len(SHAPES[name]["accounts"]), 100)


class TheFourStructuralInvariantsTests(unittest.TestCase):
    """The rules that hold for any tree-format P&L, not facts about a
    particular building."""

    def test_the_naive_sum_trap_reproduces_and_is_avoided(self):
        """THE ONE THAT MATTERS. Parents and children are both present,
        so summing every account double-counts; the breakdown must total
        the leaves only."""
        for name in TREES:
            with self.subTest(property=name):
                data = built(name)
                br = KPICalculator(data).category_breakdown()
                leaf = br["operating_total"] + br["excluded_total"]
                naive = naive_sum(data)
                self.assertLess(leaf, naive)
                self.assertGreater(naive / leaf, 1.5)
                self.assertGreater(br["operating_total"], 0)

    def test_no_account_is_counted_twice(self):
        for name in TREES + (FLAT,):
            with self.subTest(property=name):
                br = breakdown(name)
                codes = [l["code"] for l in br["lines"]]
                self.assertEqual(len(codes), len(set(codes)))
                from_cats = [l["code"] for c in br["categories"]
                             for l in c["lines"]]
                self.assertEqual(sorted(codes), sorted(from_cats))

    def test_no_leaf_is_also_a_parent(self):
        """A code with children must never be summed as a line item."""
        for name in TREES:
            with self.subTest(property=name):
                data = built(name)
                leaf_codes = {l["code"] for l in
                              KPICalculator(data).category_breakdown()["lines"]}
                ordered = list(data["accounts"].items())
                depths = [a.get("depth") for _, a in ordered]
                for i, (code, acc) in enumerate(ordered):
                    nxt = next((depths[j] for j in range(i + 1, len(ordered))
                                if depths[j] is not None), None)
                    if (acc.get("depth") is not None and nxt is not None
                            and nxt > acc["depth"]):
                        self.assertNotIn(code, leaf_codes, code)

    def test_category_total_equals_the_sum_of_its_lines(self):
        for name in TREES + (FLAT,):
            with self.subTest(property=name):
                for c in breakdown(name)["categories"]:
                    self.assertAlmostEqual(
                        c["leaf_total"],
                        sum(l["annual_total"] for l in c["lines"]), places=6)


class TheTwoFileSpecificCasesTests(unittest.TestCase):
    """Facts about particular files, kept as shape rather than as
    numbers: that a disagreement exists, not how large it was."""

    def test_a_parent_child_disagreement_is_reported_not_resolved(self):
        """Eagle Rock's real parents and children disagree. The magnitude
        is invented here; that one EXISTS is the property under test."""
        br = breakdown("Eagle Rock")
        self.assertTrue(br["discrepancies"])
        for d in br["discrepancies"]:
            self.assertAlmostEqual(d["difference"],
                                   d["parent_total"] - d["leaf_total"],
                                   places=6)

    def test_the_disagreement_is_the_synthetic_one(self):
        """Positive control on the sentence above: if the generator
        stopped injecting a disagreement, the test would still pass on
        an empty discrepancy list unless this pins the shape."""
        diffs = [round(abs(d["difference"]), 2)
                 for d in breakdown("Eagle Rock")["discrepancies"]]
        self.assertTrue(diffs)
        for d in diffs:
            self.assertAlmostEqual(d % (DISAGREEMENT * len(MONTHS)), 0.0,
                                   places=2)

    def test_the_flat_file_has_no_rollup_rows(self):
        """Jackson's cash-flow export carries no depth, so naive == leaf
        is correct rather than a failure to avoid the trap."""
        data = built(FLAT)
        br = KPICalculator(data).category_breakdown()
        leaf = br["operating_total"] + br["excluded_total"]
        self.assertAlmostEqual(naive_sum(data), leaf, places=2)
        self.assertTrue(all(l["depth"] is None for l in br["lines"]))

    def test_the_flat_and_tree_cases_really_differ(self):
        """Control on the pair: if every fixture were flat, the trap test
        above would be asserting nothing."""
        self.assertTrue(SHAPES[FLAT]["flat"])
        for name in TREES:
            self.assertFalse(SHAPES[name]["flat"], name)


class NonOperatingExclusionTests(unittest.TestCase):
    """Debt service and capex are excluded from opex but stay visible.
    The classification is by NAME, so the fixture chooses names that
    classify the same way the real ones did."""

    def test_excluded_lines_exist_and_contribute_nothing_to_opex(self):
        for name in TREES:
            with self.subTest(property=name):
                br = breakdown(name)
                excluded = [l for l in br["lines"]
                            if l["line_kind"] != "operating"]
                self.assertTrue(excluded, "no non-operating lines survived")
                self.assertAlmostEqual(
                    br["operating_total"],
                    sum(l["annual_total"] for l in br["lines"]
                        if l["line_kind"] == "operating"), places=6)

    def test_excluded_lines_are_visible_not_dropped(self):
        br = breakdown("Eagle Rock")
        kinds = {l["line_kind"] for l in br["lines"]}
        self.assertIn("operating", kinds)
        self.assertTrue({"capex", "non_operating"} & kinds)
        self.assertGreater(br["excluded_total"], 0)


class ItCarriesNoRealFiguresTests(unittest.TestCase):
    """THE CHECK THAT MAKES THE PRIVACY CLAIM WORTH ANYTHING.

    Not "the generator was written not to copy figures" -- that is intent.
    This recomputes every leaf cell from the published formula and
    compares, so one real number anywhere fails the run.
    """

    def test_every_leaf_amount_is_the_formula_and_nothing_else(self):
        for name in SHAPES:
            with self.subTest(property=name):
                specs = SHAPES[name]["accounts"]
                data = build(name and SHAPES[name])
                for i, (code, acc) in enumerate(data["accounts"].items()):
                    if specs[i]["parent"]:
                        continue          # parents are sums, checked below
                    for k, month in enumerate(MONTHS):
                        self.assertEqual(acc["data"][month],
                                         synthetic_amount(i, k))

    def test_every_parent_is_exactly_its_children_plus_the_stand_in(self):
        for name in TREES:
            with self.subTest(property=name):
                specs = SHAPES[name]["accounts"]
                data = build(SHAPES[name])
                codes = list(data["accounts"])
                depths = [a["depth"] for a in specs]
                for i, spec in enumerate(specs):
                    if not spec["parent"]:
                        continue
                    kids = []
                    for j in range(i + 1, len(specs)):
                        if depths[j] is None:
                            continue
                        if depths[j] <= depths[i]:
                            break
                        if depths[j] == depths[i] + 1:
                            kids.append(codes[j])
                    if not kids:
                        continue
                    for month in MONTHS:
                        expected = sum(data["accounts"][c]["data"][month]
                                       for c in kids)
                        if spec["disagrees"]:
                            expected += DISAGREEMENT
                        self.assertAlmostEqual(
                            data["accounts"][codes[i]]["data"][month],
                            expected, places=6)

    def test_the_stored_shape_holds_no_amounts_at_all(self):
        """The committed JSON should carry structure and booleans only.
        A float in it would be a figure by another name."""
        allowed = {"lead", "depth", "parent", "kind", "disagrees"}
        for name, shape in SHAPES.items():
            with self.subTest(property=name):
                for a in shape["accounts"]:
                    self.assertEqual(set(a), allowed)
                    self.assertIsInstance(a["disagrees"], bool)
                    self.assertIsInstance(a["parent"], bool)
                    self.assertTrue(a["depth"] is None
                                    or isinstance(a["depth"], int))
                    self.assertNotIsInstance(a["depth"], float)

    def test_no_names_or_codes_from_the_real_charts_survive(self):
        """Codes are re-issued sequentially and names come from a table
        of three, so the fixture cannot carry a chart of accounts."""
        data = built("Eagle Rock")
        for code, acc in data["accounts"].items():
            self.assertRegex(code, r"^\d{4}$")
            self.assertRegex(acc["name"],
                             r"^(Grouping|Line Item|Capital Replacement Item"
                             r"|Mortgage Interest Payment) \d+$")

    def test_the_period_and_property_are_not_hers(self):
        data = built("Canyon")
        self.assertEqual(data["property"], "Fixture Property")
        self.assertEqual(data["period"], "Twelve months")


if __name__ == "__main__":
    unittest.main()

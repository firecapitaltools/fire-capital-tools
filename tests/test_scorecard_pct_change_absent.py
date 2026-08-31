"""A trend nobody can compute is not a trend of zero.

`get_category_metrics()` returned `0.0` in two different circumstances --
a category whose first half averaged zero, and a series with fewer than
two months -- and **0.0 is a real answer to this question**. A category
that spent the same in both halves genuinely did not change. So two
unknowns and one fact all arrived at the reader as the same number, and
the reader had no way to tell them apart.

THE SECOND HALF IS WHY THIS IS ONE CHANGE AND NOT TWO

Fixing only the division guard would leave `len < 2` returning 0.0, and
would make it *harder* to find: the remaining case would be the only
place in the function still fabricating a number, with the surrounding
code now looking correct. Both branches move together.

WHAT THE CONSUMERS DO ABOUT IT

`None > 0.10` raises in Python 3, so the flag and recommendation loops
are part of the change rather than a follow-on -- without them, a
category with a zero first half takes down the whole insights card. The
category table's trend cell is the fourth: `Number(null)` is `0` in
JavaScript, so the uncomputable case would have rendered as "0.0%" --
the exact fabrication, reintroduced one layer further out.

THE PRECEDENT IS IN THE SAME PACKAGE

`processing._pct_change()` returns None for a zero base, its caller
guards on `is not None`, and the template already reads a null NOI
change. This is the outlier being brought onto the rule beside it, the
same shape as the `noi_margin` fix in `test_scorecard_noi_margin_absent`.
"""

import unittest

import pandas as pd

from tools.scorecard_pro import kpis as k


def accounts_for(series, code="6600"):
    """One category's monthly values, in the shape `accounts` carries."""
    return {code: {"data": {f"2026-{i + 1:02d}": v for i, v in enumerate(series)}}}


def frame(months):
    return pd.DataFrame({
        "Month": [f"2026-{i + 1:02d}" for i in range(months)],
        "Income": [100.0] * months,
        "NOI": [50.0] * months,
        "Expenses": [50.0] * months,
    })


def insights(series, code="6600"):
    return k.generate_advanced_insights(frame(len(series)), accounts_for(series, code))


def category(out, name="Utilities"):
    return next(c for c in out["analyzed_cats"] if c["name"] == name)


class ThePreconditionTests(unittest.TestCase):
    """Every assertion below is about a category being absent or silent,
    and would pass vacuously if the category stopped being analysed."""

    def test_a_real_trend_is_still_computed(self):
        out = insights([100.0, 100.0, 200.0, 200.0])
        self.assertAlmostEqual(category(out)["pct_change"], 1.0)

    def test_a_real_trend_still_produces_a_trend_line(self):
        out = insights([100.0, 100.0, 200.0, 200.0])
        self.assertTrue(any("Utilities" in text for text, _ in out["trends"]))

    def test_a_real_spike_still_produces_a_red_flag(self):
        out = insights([100.0, 100.0, 200.0, 200.0])
        self.assertTrue(any("Utilities spiked" in f for f in out["red_flags"]))


class AZeroFirstHalfCannotBeDividedByTests(unittest.TestCase):
    """The division guard. Nothing to measure against is not 'no change'."""

    def zero_base(self):
        return insights([0.0, 0.0, 900.0, 900.0])

    def test_the_trend_is_none_not_zero(self):
        self.assertIsNone(category(self.zero_base())["pct_change"])

    def test_it_produces_no_trend_line(self):
        out = self.zero_base()
        self.assertEqual([t for t, _ in out["trends"] if "Utilities" in t], [])

    def test_it_produces_no_red_flag(self):
        out = self.zero_base()
        self.assertEqual([f for f in out["red_flags"] if "Utilities" in f], [])

    def test_it_produces_no_recommendation(self):
        out = self.zero_base()
        self.assertEqual([r for r in out["recommendations"] if "Utilities:" in r], [])

    def test_the_card_still_arrives(self):
        """A category that cannot be measured must not silence the rest."""
        out = self.zero_base()
        for key in ("trends", "green_flags", "red_flags", "recommendations",
                    "analyzed_cats"):
            self.assertIn(key, out)
        self.assertTrue(out["recommendations"])

    def test_the_category_is_still_listed_with_its_total(self):
        """Silent about the trend, not absent from the table -- the money
        was spent and the total is a fact."""
        cat = category(self.zero_base())
        self.assertEqual(cat["total"], 1800.0)


class OneMonthHasNoHalvesTests(unittest.TestCase):
    """The other branch, which returned the same 0.0 and is the half that
    would have been left behind."""

    def test_a_single_month_is_none_not_zero(self):
        self.assertIsNone(category(insights([500.0]))["pct_change"])

    def test_it_produces_no_trend_line(self):
        out = insights([500.0])
        self.assertEqual([t for t, _ in out["trends"] if "Utilities" in t], [])

    def test_two_months_is_enough_and_still_computes(self):
        """The boundary, so the guard is not quietly wider than stated."""
        out = insights([100.0, 150.0])
        self.assertAlmostEqual(category(out)["pct_change"], 0.5)


class ARealZeroIsStillAnAnswerTests(unittest.TestCase):
    """The case that makes this a real ambiguity rather than a tidy-up: a
    category that genuinely did not change must still report 0.0."""

    def test_a_flat_category_reports_zero(self):
        out = insights([100.0, 100.0, 100.0, 100.0])
        self.assertEqual(category(out)["pct_change"], 0.0)

    def test_and_zero_is_distinguishable_from_uncomputable_now(self):
        flat = category(insights([100.0, 100.0, 100.0, 100.0]))["pct_change"]
        cannot = category(insights([0.0, 0.0, 900.0, 900.0]))["pct_change"]
        self.assertEqual(flat, 0.0)
        self.assertIsNone(cannot)
        self.assertIsNot(flat, cannot)

    def test_a_real_decrease_to_zero_still_computes(self):
        """Spending that stopped is a measurable -100%, not an unknown."""
        out = insights([100.0, 100.0, 0.0, 0.0])
        self.assertAlmostEqual(category(out)["pct_change"], -1.0)


class TheConsumersDoNotRaiseTests(unittest.TestCase):
    """`None > 0.10` is a TypeError. These are the three loops that would
    have hit it, exercised through the categories they name."""

    def test_utilities_with_a_zero_base_does_not_raise(self):
        insights([0.0, 0.0, 900.0, 900.0], code="6600")

    def test_payroll_with_a_zero_base_does_not_raise(self):
        insights([0.0, 0.0, 900.0, 900.0], code="6400")

    def test_rental_income_with_a_zero_base_does_not_raise(self):
        out = insights([0.0, 0.0, 900.0, 900.0], code="4110")
        self.assertEqual([f for f in out["green_flags"] if "Rental Income" in f], [])

    def test_contract_services_with_a_zero_base_does_not_raise(self):
        out = insights([0.0, 0.0, 900.0, 900.0], code="6500")
        self.assertEqual([r for r in out["recommendations"] if "Maintenance:" in r], [])

    def test_other_income_with_a_zero_base_does_not_raise(self):
        out = insights([0.0, 0.0, 900.0, 900.0], code="4300")
        self.assertEqual([r for r in out["recommendations"] if "Ancillary:" in r], [])

    def test_positive_control_the_same_categories_do_fire_when_they_can(self):
        self.assertTrue(any("Payroll up" in f for f in
                            insights([100.0, 100.0, 200.0, 200.0], code="6400")["red_flags"]))
        self.assertTrue(any("Rental Income up" in f for f in
                            insights([100.0, 100.0, 200.0, 200.0], code="4110")["green_flags"]))
        self.assertTrue(any("Maintenance:" in r for r in
                            insights([100.0, 100.0, 200.0, 200.0], code="6500")["recommendations"]))
        self.assertTrue(any("Ancillary:" in r for r in
                            insights([100.0, 100.0, 50.0, 50.0], code="4300")["recommendations"]))


class TheTableCellReadsNullTests(unittest.TestCase):
    """The fourth consumer, and the one that would have quietly restored
    the defect: `Number(null)` is 0 in JavaScript, so a null trend prints
    as 0.0% unless the cell checks."""

    def markup(self):
        from pathlib import Path
        return (Path(k.__file__).parents[2] / "templates" / "tools"
                / "scorecard_pro.html").read_text(encoding="utf-8")

    def test_the_trend_cell_checks_for_null(self):
        src = self.markup()
        self.assertIn("cat.pct_change == null", src)

    def test_it_renders_a_dash_rather_than_a_number(self):
        src = self.markup()
        cell = src[src.index("cat.pct_change == null"):]
        self.assertIn("—", cell[:120])        # an em dash, which is
        self.assertNotIn("0.0", cell[:120])        # this page's "not stated"

    def test_the_noi_cell_already_did_this(self):
        """Named so the convention is visible as a convention."""
        self.assertIn("noi.pct_change == null", self.markup())


class ItMatchesItsNeighbourTests(unittest.TestCase):
    """processing._pct_change answers the same question between two
    points and has always returned None. The point of the change is that
    both now agree."""

    def test_the_neighbour_returns_none_for_a_zero_base(self):
        from tools.scorecard_pro import processing
        self.assertIsNone(processing._pct_change(500.0, 0.0))

    def test_and_a_real_value_when_it_can(self):
        from tools.scorecard_pro import processing
        self.assertAlmostEqual(processing._pct_change(150.0, 100.0), 0.5)

    def test_the_source_no_longer_fabricates_a_zero(self):
        """Read from the code, because the behaviour above would also be
        produced by a category that simply stopped being analysed."""
        import inspect
        src = inspect.getsource(k.generate_advanced_insights)
        self.assertNotIn("pct_change = 0.0", src)
        self.assertNotIn("if first_half_avg != 0 else 0.0", src)
        self.assertIn("pct_change = None", src)


if __name__ == "__main__":
    unittest.main()

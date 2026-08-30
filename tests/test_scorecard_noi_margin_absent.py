"""A margin nobody can compute is not a margin of zero.

`generate_advanced_insights()` returned `0` when `income_sum` was falsy and then graded it.
On a file with no parsed income -- Jackson's, whose Gross Potential Rent
line does not match -- the margin came out `0`, fell through `< 0.40`,
and posted **"Low NOI Margin: 0.0%" as a red flag**. A property nobody
could measure was reported as having failed a threshold, in the colour
that means act on this.

THE FILE ALREADY KNEW THE ANSWER, IN THREE PLACES

* `occ_avg`, five lines above, returns None and guards both comparisons.
* `expense_ratio_avg`, four lines below, divides by **the same
  `income_sum`** and returns None when it is falsy.
* `kpis.py:357`, the per-month version of this exact quantity, has always
  returned None.

So this is not a new convention. It is the one outlier of three
neighbours being brought into line with what surrounds it.

WHY NO REPLACEMENT MESSAGE

The absence is already explained on the same screen. The warnings card
carries *"Nothing in this file matched Gross Potential Rent"* and the
occupancy column reads "No GPR" rather than a number. Adding a fourth
message would repeat what the page says; adding a flag would grade what
cannot be measured. Saying nothing here IS the deliberate answer, and
`ItSaysNothingRatherThanGradingTests` pins it as a choice rather than an
omission.
"""

import unittest

import pandas as pd

from tools.scorecard_pro import kpis as k


def frame(income, noi, expenses=None, occupancy=None, months=3):
    data = {
        "Month": [f"2026-0{i + 1}" for i in range(months)],
        "Income": [income] * months,
        "NOI": [noi] * months,
        "Expenses": [(expenses if expenses is not None else 0.0)] * months,
    }
    if occupancy is not None:
        data["Occupancy"] = [occupancy] * months
    return pd.DataFrame(data)


def flags(df, accounts=None, **kw):
    """`generate_advanced_insights` needs an accounts map; the category
    trends are irrelevant here so an empty one is passed, which makes
    get_category_metrics return None for every category and leaves only
    the flag block under test."""
    return k.generate_advanced_insights(df, accounts or {}, **kw)


class ThePreconditionTests(unittest.TestCase):
    """If generate_advanced_insights stopped producing NOI-margin flags at
    assertion below would pass vacuously."""

    def test_a_real_margin_still_produces_a_flag(self):
        out = flags(frame(income=100.0, noi=70.0))
        self.assertTrue(any("NOI Margin" in f for f in out["green_flags"]))

    def test_a_genuinely_low_margin_still_produces_a_red_flag(self):
        out = flags(frame(income=100.0, noi=10.0))
        self.assertTrue(any("Low NOI Margin" in f for f in out["red_flags"]))


class ItSaysNothingRatherThanGradingTests(unittest.TestCase):
    """The defect, and the deliberate silence that replaces it."""

    def no_income(self):
        return flags(frame(income=0.0, noi=0.0))

    def test_no_income_produces_no_noi_margin_red_flag(self):
        out = self.no_income()
        offenders = [f for f in out["red_flags"] if "NOI Margin" in f]
        self.assertEqual(offenders, [],
                         "a property with no income was graded on its margin")

    def test_and_no_green_one_either(self):
        out = self.no_income()
        self.assertEqual([f for f in out["green_flags"] if "NOI Margin" in f], [])

    def test_the_fabricated_figure_appears_nowhere(self):
        """`0.0%` was the number being asserted. It must not be printed as
        a margin at all, in either list."""
        out = self.no_income()
        every = out["red_flags"] + out["green_flags"]
        self.assertEqual([f for f in every if "NOI Margin: 0.0%" in f], [])

    def test_a_missing_income_column_behaves_the_same(self):
        """`income_sum` is falsy for a zero sum AND for an absent column.
        Both are 'cannot compute' and neither may be graded."""
        df = frame(income=0.0, noi=50.0).drop(columns=["Income"])
        out = flags(df)
        self.assertEqual([f for f in out["red_flags"] if "NOI Margin" in f], [])

    def test_the_rest_of_the_report_still_arrives(self):
        """Silence about the margin must not silence the whole card."""
        out = self.no_income()
        self.assertIn("recommendations", out)
        self.assertTrue(out["recommendations"])
        self.assertIn("green_flags", out)
        self.assertIn("red_flags", out)


class ItMatchesItsNeighboursTests(unittest.TestCase):
    """The two metrics either side already did this correctly. The point
    of the change is that all three now agree."""

    def test_expense_ratio_is_also_silent_on_the_same_denominator(self):
        out = flags(frame(income=0.0, noi=0.0, expenses=50.0))
        self.assertEqual([f for f in out["red_flags"] if "Expense Ratio" in f], [])

    def test_occupancy_is_also_silent_when_it_cannot_be_averaged(self):
        out = flags(frame(income=100.0, noi=70.0))
        self.assertEqual([f for f in out["red_flags"] if "Occupancy" in f], [])

    def test_positive_control_occupancy_does_flag_when_it_can(self):
        out = flags(frame(income=100.0, noi=70.0, occupancy=0.80))
        self.assertTrue(any("Low Occupancy" in f for f in out["red_flags"]))

    def test_the_source_line_returns_none_not_zero(self):
        """Read from the code, because the behaviour above would also be
        produced by a guard that simply never flagged."""
        import inspect
        src = inspect.getsource(k.generate_advanced_insights)
        self.assertIn("if income_sum else None", src)
        self.assertNotIn("if income_sum else 0\n", src)


class ZeroIsStillAnAnswerWhenItIsRealTests(unittest.TestCase):
    """A real margin of zero -- income arrived, NOI is nil -- is a fact
    and must still be graded. Only the uncomputable case goes silent."""

    def test_real_income_with_zero_noi_is_still_a_red_flag(self):
        out = flags(frame(income=100.0, noi=0.0))
        self.assertTrue(any("Low NOI Margin" in f for f in out["red_flags"]),
                        "a real zero margin stopped being reported")

    def test_and_it_prints_the_real_zero(self):
        out = flags(frame(income=100.0, noi=0.0))
        self.assertTrue(any("0.0%" in f for f in out["red_flags"]))

    def test_a_negative_margin_is_still_reported(self):
        out = flags(frame(income=100.0, noi=-20.0))
        self.assertTrue(any("Low NOI Margin" in f for f in out["red_flags"]))


class TheMonthlyPathIsUnchangedTests(unittest.TestCase):
    """kpis.py:357 already returned None and processing.py:323 already
    carries it into the NOIMargin series. This change must not disturb
    that path, which is the evidence that None is tolerated downstream."""

    def test_the_per_month_calculation_still_returns_none(self):
        import inspect
        src = inspect.getsource(k)
        self.assertIn("noi_margin = noi / total_income if total_income != 0 else None",
                      src)


if __name__ == "__main__":
    unittest.main()

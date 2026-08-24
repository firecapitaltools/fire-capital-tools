"""The missing-GPR card states a cause the code established, and a true scope.

WHAT IT USED TO SAY, AND WHY BOTH HALVES WERE WRONG

    "This file does not state Gross Potential Rent ... Those months are
     left out of the average occupancy figure; every other number is
     unaffected."

**A claim about the file it cannot make.** What the code establishes is
that no line matched account 4110 or any GPR label the parser carries,
and the parser holds several chart-of-accounts dialects. "Nothing
matched" and "the file does not state it" are different claims, and only
one of them is derived.

Settled against the real exports on 2026-08-24. Jackson's is a Beam
Properties cash-basis "Income Statement - 12 Month" with no account codes
anywhere -- searched every one of its 609 non-empty cells for gross,
potential, scheduled, market, vacancy, 4110 and 4000 -- and a cash-basis
statement CANNOT have a GPR, because it records rent received and GPR is
an accrual concept. Eagle Rock's is an Ince "Accounting Tree Report",
accrual, carrying 4110 explicitly. **The card cannot tell those two
apart**, so it reports the match rather than diagnosing the file.

**A scope claim that was not checked.** "Every other number is
unaffected" is true only when rental income was captured. It is for both
real files -- income, expenses and NOI come from 4000 and no
reconstruction is attempted -- but a file missing 4000 as well has its
income understated, which is a much larger failure than a blank
occupancy. `nri_found` makes that conditional instead of hopeful.

BLANK IS NOT ZERO, AND THAT IS THE POINT OF THE NOTE

A missing occupancy renders as an empty cell in a column of percentages,
and Michelle may have read one as 0%. There is a separate note for
genuine 0% months, so the two must not be confusable.

THE TRAP THIS FILE ALSO GUARDS

Mapping collected rent to 4110 would "fix" Jackson by making physical
occupancy compute as 100% every month -- confidently, silently, and
flattering the asset. Collected rent is not gross potential rent. That is
the same shape as the $5.75-per-sqft capex total: the right number in the
wrong role.
"""

import unittest
from pathlib import Path

from tools.scorecard_pro.kpis import KPICalculator
from tools.scorecard_pro.utils import summarize_dataframe

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "tools" / "scorecard_pro.html"


def pnl(accounts, months=("Jan 2026",)):
    return {"accounts": accounts, "months": list(months),
            "property": "Test", "detected_format": None}


def account(name, months, value):
    return {"name": name, "data": {m: value for m in months}, "depth": None}


class NriFoundReportsWhetherIncomeSurvivesTests(unittest.TestCase):
    """The fact that makes the scope claim checkable."""

    MONTHS = ("Jan 2026",)

    def test_it_is_true_when_rental_income_was_captured(self):
        kpis = KPICalculator(pnl({
            "4000": account("Rent Income", self.MONTHS, 13224.79),
        }, self.MONTHS)).calculate()
        self.assertTrue(kpis["nri_found"])

    def test_it_is_false_when_no_rental_income_line_was_found(self):
        kpis = KPICalculator(pnl({
            "4300": account("Other Income", self.MONTHS, 100.0),
        }, self.MONTHS)).calculate()
        self.assertFalse(kpis["nri_found"])

    def test_a_missing_gpr_alone_leaves_income_intact(self):
        """Jackson's real shape: 4000 present, 4110 absent.

        This is the case the old wording described correctly by accident.
        """
        kpis = KPICalculator(pnl({
            "4000": account("Rent Income", self.MONTHS, 13224.79),
        }, self.MONTHS)).calculate()
        month = self.MONTHS[0]
        self.assertEqual(kpis["occupancy_status"][month], "missing_gpr")
        self.assertIsNone(kpis["physical_occupancy"][month])
        self.assertIsNone(kpis["economic_occupancy"][month])
        self.assertEqual(kpis["income"][month], 13224.79)
        self.assertTrue(kpis["nri_found"])

    def test_occupancy_is_none_not_zero(self):
        """None cannot be averaged in; 0.0 would drag the mean down."""
        kpis = KPICalculator(pnl({
            "4000": account("Rent Income", self.MONTHS, 13224.79),
        }, self.MONTHS)).calculate()
        month = self.MONTHS[0]
        self.assertIsNot(kpis["physical_occupancy"][month], 0.0)
        self.assertIsNone(kpis["physical_occupancy"][month])

    def test_the_summary_carries_it(self):
        import pandas as pd
        from tools.scorecard_pro.processing import build_kpi_dataframe
        kpis = KPICalculator(pnl({
            "4300": account("Other Income", self.MONTHS, 100.0),
        }, self.MONTHS)).calculate()
        df = build_kpi_dataframe(kpis)
        self.assertFalse(summarize_dataframe(df, kpis)["nri_found"])

    def test_an_empty_frame_does_not_claim_income_is_missing(self):
        """The no-rows default must not raise a false alarm."""
        import pandas as pd
        self.assertTrue(summarize_dataframe(pd.DataFrame(), {})["nri_found"])


class TheCardStatesWhatTheCodeEstablishedTests(unittest.TestCase):
    """Asserted on the template source: this note is rendered in JS."""

    def setUp(self):
        self.text = TEMPLATE.read_text(encoding="utf-8")
        marker = "if (missing.length) {"
        start = self.text.index(marker)
        block = self.text[start:start + 3400]
        # The block explains the old wording by QUOTING it, so a raw
        # substring search finds the very strings this asserts are gone --
        # commentary about a claim is not the claim. Same distinction the
        # HANDOFF rule-scope check had to make; here it is exact, because a
        # JS comment is a syntactic category rather than a judgment.
        self.note = "\n".join(
            line for line in block.splitlines()
            if not line.strip().startswith("//"))

    def test_it_no_longer_claims_the_file_does_not_state_gpr(self):
        self.assertNotIn("This file does not state Gross Potential Rent",
                         self.note)

    def test_it_reports_the_match_which_is_what_it_knows(self):
        self.assertIn("Nothing in this file matched Gross Potential Rent",
                      self.note)

    def test_it_no_longer_promises_every_other_number_is_unaffected(self):
        self.assertNotIn("every other number is unaffected", self.note)

    def test_it_makes_blank_impossible_to_read_as_zero(self):
        self.assertIn("this is not 0%", self.note)

    def test_it_names_both_occupancies_as_the_scope(self):
        self.assertIn("physical and", self.note)
        self.assertIn("economic occupancy", self.note)

    def test_the_reassuring_sentence_is_conditional_on_nri(self):
        """It may only say income is fine when income was actually found."""
        self.assertIn("nri_found", self.note)
        self.assertIn("are unaffected", self.note)
        self.assertIn("understated", self.note)

    def test_the_genuine_zero_note_still_exists_and_is_distinct(self):
        """Blank and 0% must remain two different statements."""
        self.assertIn("Occupancy really is 0%", self.text)


if __name__ == "__main__":
    unittest.main()

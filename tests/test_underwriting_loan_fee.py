"""The lender's origination fee is not a third-party acquisition cost.

WHAT CHANGED AND WHY

`origination_fee` was the ninth entry in
DEFAULT_ACQUISITION_COST_CATEGORIES, sitting beside Legal, Appraisal and
Doc Prep. That made acquisition the OPPOSITE convention from refinance,
where `refi_costs_pct` means third-party closing only and the bank's point
has its own line as `refi_bank_fee_pct`.

The inconsistency was real, was flagged in `deal_analyzer_math.refinance()`
and was pinned by a test as deliberate -- because Michelle had been asked
about the refinance side and not about acquisition. She was then asked:
"Yes, please split the lender's origination fee out of the acquisition
costs for consistency."

So the categories are eight third-party items and the lender's point is
`loan_fee_pct`, the acquisition-side twin of `refi_bank_fee_pct`.

A POINT IS A PERCENTAGE OF THE LOAN

Not of the price. That is what makes it the same object as the refinance
bank fee, and it is why `acquisition_loan_basis()` exists: the basis is
the loan stack's own total when there is one, and price x LTV when the
engine is sizing a single loan itself.

IT ALWAYS ADDS

The itemized-versus-flat override applies only between two descriptions of
the SAME money. Neither the eight categories nor the flat percentage
stands in for the lender's fee any more, so overriding it away when costs
are itemized would silently drop it -- the same reasoning that already
governs the GP acquisition fee.

NOTHING WAS ORPHANED. Production carried zero acquisition-cost lines when
this landed, so dropping the category from nine to eight stranded no
stored row, and `loan_fee_pct` is NULL on every pre-existing scenario,
which reads as no fee rather than as a missing one.
"""

import unittest
from pathlib import Path

from tools import underwriting_math as um

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "templates" / "tools" / "underwriting_detail.html"

PRICE = 7_500_000.0
LOAN = 5_000_000.0


class TheCategoriesAreThirdPartyOnlyTests(unittest.TestCase):
    def test_origination_is_gone(self):
        keys = [k for k, _ in um.DEFAULT_ACQUISITION_COST_CATEGORIES]
        self.assertNotIn("origination_fee", keys)

    def test_eight_remain_and_they_are_the_third_party_ones(self):
        keys = [k for k, _ in um.DEFAULT_ACQUISITION_COST_CATEGORIES]
        self.assertEqual(keys, ["legal", "property_inspection", "lead_paint",
                                "environmental", "appraisal",
                                "structural_inspection", "lender_legal",
                                "doc_prep"])

    def test_lender_legal_is_not_the_same_thing_and_stays(self):
        """Legal work the borrower pays for is still a third-party cost.

        Only the fee paid to the lender FOR MAKING THE LOAN moves out.
        """
        keys = [k for k, _ in um.DEFAULT_ACQUISITION_COST_CATEGORIES]
        self.assertIn("lender_legal", keys)


class TheLoanFeeIsChargedOnTheLoanTests(unittest.TestCase):
    def acq(self, **kw):
        base = dict(expense_lines=[], purchase_price=PRICE,
                    closing_costs_pct=2.0, acquisition_fee_pct=None,
                    loan_fee_pct=1.0, loan_amount=LOAN)
        base.update(kw)
        return um.acquisition_costs(**base)

    def test_one_point_is_one_percent_of_the_loan(self):
        self.assertAlmostEqual(self.acq()["loan_fee_total"], 50_000.0)

    def test_it_is_not_a_percentage_of_the_price(self):
        """The bug this shape prevents: 1% of 7.5M is 75,000, not 50,000."""
        self.assertNotAlmostEqual(self.acq()["loan_fee_total"], PRICE * 0.01)

    def test_the_base_is_reported_so_the_page_can_show_it(self):
        self.assertEqual(self.acq()["loan_fee_base"], LOAN)

    def test_no_loan_means_no_point(self):
        for kw in ({"loan_amount": 0}, {"loan_amount": None},
                   {"loan_fee_pct": None}, {"loan_fee_pct": 0}):
            with self.subTest(**kw):
                a = self.acq(**kw)
                self.assertEqual(a["loan_fee_total"], 0.0)
                self.assertFalse(a["has_loan_fee"])

    def test_it_adds_to_equity(self):
        with_fee = self.acq()["effective_total"]
        without = self.acq(loan_fee_pct=0)["effective_total"]
        self.assertAlmostEqual(with_fee - without, 50_000.0)


class ItAddsRatherThanBeingOverriddenTests(unittest.TestCase):
    """Itemizing overrides the flat percentage. It must not override this."""

    def line(self, amount):
        return {"line_kind": um.ACQUISITION_COST_KIND, "is_included": True,
                "annual_amount": amount}

    def test_itemizing_does_not_swallow_the_lender_fee(self):
        a = um.acquisition_costs([self.line(120_000.0)], PRICE, 2.0,
                                 loan_fee_pct=1.0, loan_amount=LOAN)
        self.assertTrue(a["is_itemized"])
        self.assertEqual(a["itemized_total"], 120_000.0)
        self.assertAlmostEqual(a["loan_fee_total"], 50_000.0)
        self.assertAlmostEqual(a["effective_total"], 170_000.0)

    def test_it_is_excluded_from_the_shortfall_comparison(self):
        """The shortfall compares itemized against flat. The lender fee is
        in neither, so folding it in would make a complete itemization
        look like a shortfall."""
        a = um.acquisition_costs([self.line(150_000.0)], PRICE, 2.0,
                                 loan_fee_pct=1.0, loan_amount=LOAN)
        flat = PRICE * 0.02
        self.assertAlmostEqual(a["shortfall_pct"],
                               (flat - 150_000.0) / flat * 100.0)

    def test_the_effective_pct_the_engine_receives_includes_it(self):
        """Displayed dollars and the engine's arithmetic must not disagree."""
        a = um.acquisition_costs([], PRICE, 2.0, loan_fee_pct=1.0,
                                 loan_amount=LOAN)
        self.assertAlmostEqual(a["effective_pct"],
                               a["effective_total"] / PRICE * 100.0)


class TheLoanBasisTests(unittest.TestCase):
    def test_a_loan_stack_is_its_own_total(self):
        basis = um.acquisition_loan_basis(
            {"purchase_price": PRICE, "ltv_pct": 65.0},
            [{"amount": 3_000_000.0}, {"amount": 1_250_000.0}])
        self.assertEqual(basis, 4_250_000.0)

    def test_without_a_stack_it_is_price_times_ltv(self):
        basis = um.acquisition_loan_basis(
            {"purchase_price": PRICE, "ltv_pct": 65.0}, [])
        self.assertAlmostEqual(basis, PRICE * 0.65)

    def test_the_stack_wins_when_it_disagrees_with_ltv(self):
        """With loans present the stack IS the financing and LTV is an
        output, so the point is charged on what was actually borrowed."""
        basis = um.acquisition_loan_basis(
            {"purchase_price": PRICE, "ltv_pct": 65.0},
            [{"amount": 1_000_000.0}])
        self.assertEqual(basis, 1_000_000.0)

    def test_nothing_sized_yet_is_zero_not_an_error(self):
        self.assertEqual(um.acquisition_loan_basis({}, None), 0.0)


class TheTwoSidesAgreeTests(unittest.TestCase):
    """The whole point of the change."""

    def test_neither_side_buries_the_lenders_fee_in_costs(self):
        engine = (ROOT / "tools" / "deal_analyzer_math.py").read_text(encoding="utf-8")
        self.assertIn("refi_bank_fee_pct", engine)
        self.assertIn("loan_fee_pct", um.acquisition_costs.__code__.co_varnames)

    def test_the_old_inconsistency_note_is_gone_from_the_engine(self):
        engine = (ROOT / "tools" / "deal_analyzer_math.py").read_text(encoding="utf-8")
        self.assertIn("ACQUISITION SIDE NOW AGREES", engine.upper())
        self.assertNotIn("one of nine line items", engine)

    def test_the_form_offers_the_input(self):
        tpl = TPL.read_text(encoding="utf-8")
        self.assertIn("'loan_fee_pct'", tpl)
        self.assertIn("Bank Loan Fee (% of loan)", tpl)

    def test_the_page_shows_it_as_its_own_line(self):
        tpl = TPL.read_text(encoding="utf-8")
        self.assertIn("Bank loan fee", tpl)
        self.assertIn("acq.loan_fee_total", tpl)
        self.assertIn("of the {{ money(acq.loan_fee_base) }} loan", tpl)


class TheFieldIsPersistedTests(unittest.TestCase):
    def test_it_is_a_saved_numeric_scenario_field(self):
        from tools import underwriting_db as db
        self.assertIn("loan_fee_pct", db.SCENARIO_NUMERIC)

    def test_it_is_in_the_schema_and_the_migration_list(self):
        from tools import underwriting_db as db
        src = (ROOT / "tools" / "underwriting_db.py").read_text(encoding="utf-8")
        self.assertIn("loan_fee_pct REAL", src)
        self.assertIn('("loan_fee_pct", "REAL")', src)

    def test_the_field_name_collides_with_nothing(self):
        from tools import underwriting_db as db
        names = list(db.SCENARIO_NUMERIC)
        self.assertEqual(names.count("loan_fee_pct"), 1)
        cats = [k for k, _ in um.DEFAULT_ACQUISITION_COST_CATEGORIES]
        self.assertEqual(set(cats) & set(names), set())


if __name__ == "__main__":
    unittest.main()

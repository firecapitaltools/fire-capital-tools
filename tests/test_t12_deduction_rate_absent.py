"""A deduction rate needs a gross figure to be a rate of.

`extract_totals()` returned `0.0` for `vacancy_pct` when the T12 had no
Gross Potential Rent line to divide by. That zero travelled into the Deal
Analyzer's Vacancy & Credit Loss field as `"0.000000"`, tagged
`PROVENANCE_T12` and snapshotted as `imported_vacancy_pct` -- so the tool
claimed the file **stated** a deduction rate of zero. It stated nothing of
the kind. It has no gross potential rent line at all, which is why the
deductions are zero in the first place.

THE AMOUNT AND THE RATE ARE DIFFERENT FACTS

`deductions` is a real, measured zero and stays one: nothing was deducted.
Only the RATE is unknowable. `_f()` in `quick_analyzer_math` already
states this rule for this very field -- *"a missing vacancy rate and a
vacancy rate of zero are different claims and must not collapse into each
other"* -- and this line was where they collapsed.

THE TWO MOVE TOGETHER

`deal_analyzer.py` formats the value with `f"{...:.6f}"`, which raises on
None, so the formatter is part of this change rather than a follow-on.

WHY A BLANK IS NOT A DEAD END

`to_float("")` is None, `build_noi()` answers with a named refusal --
*"Vacancy is required (enter 0 for a fully occupied property)"* -- and the
T12 warning flashed alongside now says why the field is empty. One
keystroke, and the zero becomes the analyst's claim rather than the
tool's. With no gross rent the vacancy percentage is arithmetically
immaterial anyway, so nothing is lost but the false provenance.
"""

import unittest

from tools import quick_analyzer_t12 as t12
from tools.deal_analyzer import _form_from_t12
from tools.form_utils import to_float


def totals(gpr, deductions_pct=None, **kw):
    """The shape extract_totals() returns, as the form consumer sees it."""
    out = {"months": 12, "gross_potential_income": gpr,
           "net_rental_income": 0.0, "vacancy_loss_only": 0.0,
           "deductions": 0.0, "vacancy_pct": deductions_pct,
           "other_income": 1000.0, "effective_gross_income": 1000.0,
           "operating_expenses": 400.0, "noi": 600.0, "warnings": []}
    out.update(kw)
    return out


class TheRateIsNoneWithoutAGrossFigureTests(unittest.TestCase):
    """Read from the source, because the arithmetic path needs a real
    workbook and this is the one line under test."""

    def test_the_guard_returns_none(self):
        import inspect
        src = inspect.getsource(t12)
        self.assertIn("deduction_pct = (deductions / gpr * 100.0) if gpr else None",
                      src)

    def test_it_no_longer_returns_zero(self):
        import inspect
        src = inspect.getsource(t12)
        self.assertNotIn("if gpr else 0.0", src)

    def test_the_deduction_AMOUNT_is_still_a_measured_zero(self):
        """Only the rate is unknowable. `max(0.0, gpr - nri)` stays."""
        import inspect
        src = inspect.getsource(t12)
        self.assertIn("deductions = max(0.0, gpr - net_rental_income)", src)

    def test_the_warning_says_why_the_field_is_blank(self):
        import inspect
        src = inspect.getsource(t12)
        self.assertIn("Vacancy & Credit Loss is left blank", src)

    def test_the_warning_keeps_what_it_already_said(self):
        """The existing mitigation is extended, not replaced."""
        import inspect
        src = inspect.getsource(t12)
        self.assertIn("no Gross Potential Rent line", src)
        self.assertIn("The NOI is still the file's own figure", src)


class TheFormFieldGoesBlankNotZeroTests(unittest.TestCase):
    def form(self, vacancy_pct):
        return _form_from_t12({}, totals(gpr=0.0, deductions_pct=vacancy_pct))

    def test_an_unknown_rate_produces_an_empty_field(self):
        self.assertEqual(self.form(None)["vacancy_pct"], "")

    def test_it_does_not_produce_a_measured_looking_zero(self):
        self.assertNotEqual(self.form(None)["vacancy_pct"], "0.000000")

    def test_the_provenance_snapshot_records_not_stated(self):
        """`imported_vacancy_pct` is what a later provenance check reads.
        A 0.000000 there is the tool asserting the file said zero."""
        out = self.form(None)
        self.assertEqual(out["imported_vacancy_pct"], "")
        self.assertIsNone(to_float(out["imported_vacancy_pct"]))

    def test_positive_control_a_real_rate_still_formats(self):
        """Without this, every assertion above would pass on a formatter
        that always emitted an empty string."""
        out = _form_from_t12({}, totals(gpr=100000.0, deductions_pct=7.25))
        self.assertEqual(out["vacancy_pct"], "7.250000")
        self.assertEqual(out["imported_vacancy_pct"], "7.250000")

    def test_a_real_zero_rate_still_formats_as_zero(self):
        """A T12 WITH a gross figure and no deductions genuinely states a
        0% rate, and that must survive as a stated zero."""
        out = _form_from_t12({}, totals(gpr=100000.0, deductions_pct=0.0))
        self.assertEqual(out["vacancy_pct"], "0.000000")
        self.assertEqual(to_float(out["imported_vacancy_pct"]), 0.0)

    def test_the_two_zeros_are_distinguishable(self):
        """The whole point: a stated zero and an unknown rate must not
        arrive at the form looking the same."""
        stated = _form_from_t12({}, totals(gpr=100000.0, deductions_pct=0.0))
        unknown = _form_from_t12({}, totals(gpr=0.0, deductions_pct=None))
        self.assertNotEqual(stated["vacancy_pct"], unknown["vacancy_pct"])

    def test_the_other_imported_fields_are_unaffected(self):
        out = self.form(None)
        self.assertEqual(out["other_income"], "1000.00")
        self.assertEqual(out["noi_direct"], "600.00")
        self.assertEqual(out["noi_provenance"], "t12")


class TheBlankIsARefusalNotACrashTests(unittest.TestCase):
    """A blank field must produce a named message, not a traceback."""

    def test_build_noi_refuses_a_missing_vacancy_by_name(self):
        from tools import quick_analyzer_math as qam
        with self.assertRaises(qam.ValidationError) as caught:
            qam.build_noi(100000.0, to_float(""), 0.0, "amount", 0.0)
        self.assertIn("Vacancy is required", str(caught.exception))

    def test_and_the_message_says_what_to_do(self):
        from tools import quick_analyzer_math as qam
        with self.assertRaises(qam.ValidationError) as caught:
            qam.build_noi(100000.0, to_float(""), 0.0, "amount", 0.0)
        self.assertIn("enter 0", str(caught.exception))

    def test_positive_control_a_stated_zero_is_accepted(self):
        """A vacancy of zero is a valid answer; only absence is refused."""
        from tools import quick_analyzer_math as qam
        out = qam.build_noi(100000.0, 0.0, 0.0, "amount", 0.0)
        self.assertEqual(out["vacancy_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()

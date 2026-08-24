"""A month's own digits are not its year.

WHAT WENT WRONG

`normalize_month` found the month, then ran a fresh search for the year
across the whole string. `(20\\d{2}|\\d{2})` matched the month's own digits
whenever the month was two-digit or zero-padded:

    '5/24'    -> May 2024   correct, by luck: '5' is one digit
    '10/24'   -> Oct 2010   the '10' was taken as the year
    '11/24'   -> Nov 2011
    '12/24'   -> Dec 2012
    '06/25'   -> Jun 2006
    '10/2024' -> Oct 2010   even with the year spelled out in full

October, November, December and every zero-padded month, misfiled by up to
a decade.

WHY IT MATTERS WHERE IT SITS

This is the P&L path. Month keys are the primary key of
`scorecard_history` -- `PRIMARY KEY (property_key, month)` -- and
`month_start` drives chronological ordering for the trend. A misfiled
month is therefore not a display bug: it writes a different row, sorts to
a different place, and cannot collide with the correct one to reveal
itself.

IT NEVER FIRED, WHICH IS WHY IT SURVIVED

Every P&L format in hand writes a month NAME with a four-digit year --
'Aug 2025', 'Jun 2025\\nActual', 'Jan 2025' -- across Jackson (Beam),
Eagle Rock and OXPT (Ince) and Canyon. The numeric branch was unreachable
in practice. Production history was read read-only and is clean: 36 rows
over three properties, every month between Aug 2025 and Jul 2026. So this
is a code fix with no data correction behind it.

The bug was found from the other direction entirely: the Scorecard T12
KPIs sheet uses 'm/yy' headers, and reusing this function there would have
misfiled Eagle Rock's first three months.
"""

import unittest

from tools.scorecard_pro.parsing import PnLParser


def norm(raw, default_year=None):
    return PnLParser.__new__(PnLParser).normalize_month(raw, default_year=default_year)


class TheMonthDigitsAreNotTheYearTests(unittest.TestCase):
    """Each of these returned a year taken from the month."""

    def test_two_digit_months(self):
        self.assertEqual(norm("10/24"), "Oct 2024")
        self.assertEqual(norm("11/24"), "Nov 2024")
        self.assertEqual(norm("12/24"), "Dec 2024")

    def test_zero_padded_months(self):
        self.assertEqual(norm("06/25"), "Jun 2025")
        self.assertEqual(norm("01/26"), "Jan 2026")

    def test_a_four_digit_year_is_not_stolen_either(self):
        self.assertEqual(norm("10/2024"), "Oct 2024")

    def test_nothing_lands_in_the_2010s(self):
        for raw in ("10/24", "11/24", "12/24", "06/25", "10/2024"):
            with self.subTest(raw=raw):
                self.assertNotIn("201", norm(raw))

    def test_single_digit_months_still_work(self):
        """These were right before, by luck, and must stay right."""
        self.assertEqual(norm("5/24"), "May 2024")
        self.assertEqual(norm("1/25"), "Jan 2025")
        self.assertEqual(norm("9/25"), "Sep 2025")


class TheRealFormatsAreUnchangedTests(unittest.TestCase):
    """The corpus is what the P&L path actually sees, not invented shapes.

    Collected by reading the header row of every T12/P&L export in hand:
    Jackson (Beam), Eagle Rock and OXPT (Ince), Canyon, in both .xlsx and
    the converted .csv form.
    """

    REAL = {
        "Aug 2025": "Aug 2025",
        "Jun 2025\nActual": "Jun 2025",
        "Jul 2025\nActual": "Jul 2025",
        "Jan 2025": "Jan 2025",
        "Dec 2025": "Dec 2025",
        "Oct 2025": "Oct 2025",
        "Nov 2025": "Nov 2025",
    }

    def test_every_real_header_parses_as_before(self):
        for raw, expected in self.REAL.items():
            with self.subTest(raw=raw):
                self.assertEqual(norm(raw), expected)

    def test_other_plausible_shapes(self):
        for raw, expected in (("2025-08", "Aug 2025"), ("Aug-25", "Aug 2025"),
                              ("2024-10", "Oct 2024"), ("Sept 2025", "Sep 2025"),
                              ("Dec. 2024", "Dec 2024"),
                              ("August 2025", "Aug 2025")):
            with self.subTest(raw=raw):
                self.assertEqual(norm(raw), expected)

    def test_a_month_with_no_year_is_still_bare(self):
        self.assertEqual(norm("Aug"), "Aug")

    def test_the_default_year_still_applies(self):
        self.assertEqual(norm("Aug", default_year=2025), "Aug 2025")

    def test_nonsense_is_still_rejected(self):
        for raw in ("13/24", "0/24", "junk", "", "   ", None):
            with self.subTest(raw=raw):
                self.assertIsNone(norm(raw))

    def test_a_four_digit_token_is_never_read_as_a_month(self):
        """'2025' alone is a year, not month 20 or month 2."""
        self.assertIsNone(norm("2025"))


class TheStatedPeriodBeatsTodayTests(unittest.TestCase):
    """A file that declares its own range should not be dated by the clock."""

    def parser_with_period(self, period):
        p = PnLParser.__new__(PnLParser)
        p.period = period
        return p

    def test_the_period_is_used_when_columns_carry_no_year(self):
        p = self.parser_with_period("Aug 2025 to Jul 2026")
        self.assertEqual(p._infer_default_year(["Jan", "Feb", "Mar"]), 2025)

    def test_the_ince_period_string_also_parses(self):
        p = self.parser_with_period(
            "June 2025 - May 2026 - Accrual - Accounting Book: Default")
        self.assertEqual(p._infer_default_year(["Jan", "Feb"]), 2025)

    def test_a_year_in_the_columns_still_wins(self):
        """The columns are more specific than the header line."""
        p = self.parser_with_period("Aug 2025 to Jul 2026")
        self.assertEqual(p._infer_default_year(["Jan 2023", "Feb 2023"]), 2023)

    def test_it_falls_back_to_today_when_nothing_is_stated(self):
        import datetime
        p = self.parser_with_period("Unknown Period")
        self.assertEqual(p._infer_default_year(["Jan", "Feb"]),
                         datetime.date.today().year)


if __name__ == "__main__":
    unittest.main()

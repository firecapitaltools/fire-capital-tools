"""Bedrooms and bathrooms, read from the rent roll's own type string.

Michelle: *"Ideally, I'd like the tool to recognize the number of bedrooms
and bathrooms from the rent roll so the tool can adjust the fields
accordingly."*

ALL EIGHTEEN, NOT A SAMPLE

`TYPE_STRINGS` below is every distinct `Type` value in the Oxford Pointe
rent roll -- all 18, with the unit count each covers, read from the file
rather than chosen. Testing a representative handful is how the RentCast
disclosure shipped wrong: four cached addresses agreed, and the fifth did
not. Two of these eighteen are exactly the ones a sample would drop:

* `'2 1.5 CLASSIC W/D'` -- typed with a SPACE where every other row uses a
  slash. A pattern requiring `/` reads 17 of 18 and looks fine.
* `'3/2 RENOVATED  down'` -- ends in a word that collides with
  `AREA_STATUSES`. The pattern must stop before reaching it, or something
  downstream reads "down" as an occupancy status.

WHAT IS REFUSED RATHER THAN GUESSED

A string with no leading integer pair -- a studio -- returns None and is
reported. **No such row exists in either rent roll we hold**, so that path
has never run against real data, and it stays a refusal for exactly that
reason rather than acquiring a default nobody has tested.
"""

import unittest

from tools.underwriting_rentroll import (
    UNIT_TYPE_RE,
    UnitLayout,
    layouts_for_units,
    parse_unit_type,
)

# Every distinct type string at Oxford Pointe, with its unit count and the
# layout it should yield. Read from the file; the counts sum to 152.
TYPE_STRINGS = [
    ("2/1.5 RENOVATED",                20, 2, 1.5),
    ("2/1.5 RENOVATED W/D",            20, 2, 1.5),
    ("2 1.5 CLASSIC W/D",              18, 2, 1.5),
    ("2/1.5 CLASSIC",                  16, 2, 1.5),
    ("2/2 CLASSIC NEW BUILDING  W/D",  14, 2, 2.0),
    ("3/2 RENOVATED",                  12, 3, 2.0),
    ("3/2 CLASSIC W/D",                12, 3, 2.0),
    ("1/1 RENOVATED",                  12, 1, 1.0),
    ("1/1 CLASSIC",                    12, 1, 1.0),
    ("3/2 RENOVATED  W/D",              4, 3, 2.0),
    ("2/1.5 PREMIUM",                   3, 2, 1.5),
    ("2/2 RENOVATED NEW BUILDING W/D",  2, 2, 2.0),
    ("3/2 CLASSIC",                     2, 3, 2.0),
    ("2/1 RENOVATED",                   1, 2, 1.0),
    ("3/2 RENOVATED  down",             1, 3, 2.0),
    ("3/2 PREMIUM",                     1, 3, 2.0),
    ("1/1 PREMIUM",                     1, 1, 1.0),
    ("3/1.5 RENOVATED",                 1, 3, 1.5),
]


class ThePopulationIsTheWholeFileTests(unittest.TestCase):
    """Assert the size before asserting anything about the contents."""

    def test_there_are_eighteen_distinct_types(self):
        self.assertEqual(len(TYPE_STRINGS), 18)

    def test_they_account_for_all_152_units(self):
        self.assertEqual(sum(n for _, n, _, _ in TYPE_STRINGS), 152)

    def test_the_two_awkward_ones_are_present(self):
        strings = {t for t, _, _, _ in TYPE_STRINGS}
        self.assertIn("2 1.5 CLASSIC W/D", strings)
        self.assertIn("3/2 RENOVATED  down", strings)


class EveryRealTypeStringParsesTests(unittest.TestCase):
    def test_all_eighteen(self):
        for text, _, beds, baths in TYPE_STRINGS:
            with self.subTest(type=text):
                layout = parse_unit_type(text)
                self.assertIsNotNone(layout, f"{text!r} did not parse")
                self.assertEqual(layout.beds, beds)
                self.assertEqual(layout.baths, baths)

    def test_a_space_separator_reads_the_same_as_a_slash(self):
        self.assertEqual(parse_unit_type("2 1.5 CLASSIC W/D"),
                         parse_unit_type("2/1.5 CLASSIC"))

    def test_the_trailing_text_is_not_consumed(self):
        """`down` collides with AREA_STATUSES and must not travel."""
        layout = parse_unit_type("3/2 RENOVATED  down")
        self.assertEqual((layout.beds, layout.baths), (3, 2.0))
        self.assertNotIn("down", str(layout))

    def test_the_pattern_stops_at_the_layout(self):
        match = UNIT_TYPE_RE.match("3/2 RENOVATED  down")
        self.assertEqual(match.group(0).strip(), "3/2")


class HalfBathsAreSplitTests(unittest.TestCase):
    """1.5 is one full bathroom plus one half. Site DD has no half-bath
    room type and this does not add one -- the seeding run makes two
    bathroom rooms and labels the second."""

    def test_one_and_a_half_is_one_full_and_one_half(self):
        layout = parse_unit_type("2/1.5 RENOVATED")
        self.assertEqual(layout.full_baths, 1)
        self.assertEqual(layout.half_baths, 1)

    def test_two_is_two_full_and_no_half(self):
        layout = parse_unit_type("2/2 CLASSIC NEW BUILDING  W/D")
        self.assertEqual(layout.full_baths, 2)
        self.assertEqual(layout.half_baths, 0)

    def test_the_stated_figure_is_kept_alongside_the_split(self):
        """The rent roll's own words are what an inspector recognises."""
        self.assertEqual(parse_unit_type("3/1.5 RENOVATED").baths, 1.5)

    def test_the_split_reconstructs_the_stated_figure(self):
        for text, _, _, baths in TYPE_STRINGS:
            with self.subTest(type=text):
                layout = parse_unit_type(text)
                self.assertEqual(layout.full_baths + 0.5 * layout.half_baths,
                                 baths)


class RefusedRatherThanGuessedTests(unittest.TestCase):
    def test_a_studio_is_refused(self):
        for text in ("Studio", "STUDIO RENOVATED", "Efficiency"):
            with self.subTest(type=text):
                self.assertIsNone(parse_unit_type(text))

    def test_empty_and_missing_are_refused(self):
        for text in ("", "   ", None):
            with self.subTest(type=text):
                self.assertIsNone(parse_unit_type(text))

    def test_a_bath_fraction_other_than_a_half_is_refused(self):
        """.5 means a half bath. What .25 would mean is established by
        nothing, and no real row has one."""
        for text in ("2/1.25 X", "2/1.75 X"):
            with self.subTest(type=text):
                self.assertIsNone(parse_unit_type(text))

    def test_a_leading_word_is_refused_rather_than_scanned_for(self):
        """Anchored. Finding `2/1` anywhere in a sentence would read a
        layout out of prose."""
        self.assertIsNone(parse_unit_type("RENOVATED 2/1.5"))

    def test_positive_control_the_anchor_is_the_only_reason(self):
        self.assertIsNotNone(parse_unit_type("2/1.5 RENOVATED"))


class TheRefusalsAreReportedNotDroppedTests(unittest.TestCase):
    def units(self, *types):
        return [{"unit": str(100 + i), "unit_type": t, "sqft": 800.0,
                 "status": "C"} for i, t in enumerate(types)]

    def test_readable_units_are_returned_with_their_layout(self):
        out = layouts_for_units(self.units("2/1.5 RENOVATED", "3/2 CLASSIC"))
        self.assertEqual(out["parsed_count"], 2)
        self.assertEqual(out["unreadable_count"], 0)
        self.assertEqual(out["units"][0]["beds"], 2)
        self.assertEqual(out["units"][1]["full_baths"], 2)

    def test_an_unreadable_unit_is_listed_separately(self):
        out = layouts_for_units(self.units("2/1.5 RENOVATED", "Studio"))
        self.assertEqual(out["parsed_count"], 1)
        self.assertEqual(out["unreadable_count"], 1)
        self.assertEqual(out["unreadable"][0]["unit_type"], "Studio")

    def test_it_is_not_silently_dropped(self):
        """A silent 150-of-152 is the failure shape this avoids."""
        out = layouts_for_units(self.units("Studio"))
        self.assertEqual(out["units"], [])
        self.assertTrue(out["unreadable"])

    def test_the_two_lists_account_for_every_unit(self):
        out = layouts_for_units(self.units(*[t for t, _, _, _ in TYPE_STRINGS],
                                           "Studio"))
        self.assertEqual(out["parsed_count"] + out["unreadable_count"], 19)

    def test_an_empty_roll_is_not_an_error(self):
        out = layouts_for_units([])
        self.assertEqual((out["parsed_count"], out["unreadable_count"]), (0, 0))


class TheReturnedShapeTests(unittest.TestCase):
    def test_it_is_a_named_tuple_not_a_bare_pair(self):
        layout = parse_unit_type("2/1.5 RENOVATED")
        self.assertIsInstance(layout, UnitLayout)
        self.assertEqual(layout.beds, layout[0])

    def test_the_carried_fields_survive_into_the_report(self):
        out = layouts_for_units([{"unit": "110", "unit_type": "2/2 CLASSIC",
                                  "sqft": 825.0, "status": "C"}])
        row = out["units"][0]
        self.assertEqual(row["unit"], "110")
        self.assertEqual(row["sqft"], 825.0)
        self.assertEqual(row["status"], "C")


if __name__ == "__main__":
    unittest.main()


class TheXlsGateIsScopedTests(unittest.TestCase):
    """ResMan exports .xls. The T12 importer shares the other constant and
    reads through openpyxl, which cannot open OLE2 -- so widening the
    shared set would let a .xls reach it and fail somewhere less legible
    than the gate."""

    def test_the_rent_roll_route_accepts_xls(self):
        from tools.underwriting import RENTROLL_UPLOAD_EXT
        self.assertIn(".xls", RENTROLL_UPLOAD_EXT)

    def test_the_SHARED_set_does_not(self):
        from tools.underwriting import ALLOWED_UPLOAD_EXT
        self.assertNotIn(".xls", ALLOWED_UPLOAD_EXT)

    def test_the_rent_roll_set_is_the_shared_one_plus_xls(self):
        """A superset, so a format added to the shared set later reaches
        the rent roll too rather than silently not."""
        from tools.underwriting import ALLOWED_UPLOAD_EXT, RENTROLL_UPLOAD_EXT
        self.assertEqual(RENTROLL_UPLOAD_EXT, ALLOWED_UPLOAD_EXT | {".xls"})

    def test_xlsx_is_still_accepted_everywhere_it_was(self):
        from tools.underwriting import ALLOWED_UPLOAD_EXT, RENTROLL_UPLOAD_EXT
        for ext in (".xlsx", ".xlsm"):
            with self.subTest(ext=ext):
                self.assertIn(ext, ALLOWED_UPLOAD_EXT)
                self.assertIn(ext, RENTROLL_UPLOAD_EXT)

    def test_a_pdf_is_refused_by_both(self):
        from tools.underwriting import ALLOWED_UPLOAD_EXT, RENTROLL_UPLOAD_EXT
        self.assertNotIn(".pdf", ALLOWED_UPLOAD_EXT)
        self.assertNotIn(".pdf", RENTROLL_UPLOAD_EXT)


class TheLoaderDispatchesOnExtensionTests(unittest.TestCase):
    """One place that knows about file formats."""

    def test_xls_goes_to_xlrd_and_xlsx_does_not(self):
        import datetime
        from unittest import mock
        from tools import underwriting_rentroll as rr

        class FakeSheet:
            ncols, nrows = 2, 1
            def cell_value(self, r, c):
                return [datetime.date(2025, 7, 1), "x"][c] if c else 45839.0
            def cell_type(self, r, c):
                return rr_xlrd.XL_CELL_DATE if c == 0 else 1

        class FakeBook:
            datemode = 0
            def sheet_by_index(self, i): return FakeSheet()
            def sheet_names(self): return ["Sheet"]

        import xlrd as rr_xlrd
        with mock.patch.object(rr_xlrd, "open_workbook", lambda p: FakeBook()):
            rows, names = rr._load_rows("whatever.xls")
        self.assertEqual(names, ["Sheet"])
        self.assertIsInstance(rows[0][0], datetime.datetime,
                              "a date cell was not converted from its serial")

    def test_a_date_serial_becomes_a_datetime_not_a_float(self):
        """The bug this caught: every lease date on all 152 units read as
        absent because _date_value cannot parse 45839.0."""
        import xlrd
        self.assertEqual(xlrd.xldate_as_datetime(45839.0, 0).date().isoformat(),
                         "2025-07-01")

    def test_date_conversion_is_in_the_loader_not_the_field_reader(self):
        """_date_value has no way to know which workbook a bare float came
        from, and 45839 is a plausible rent as well as a plausible date."""
        import inspect
        from tools import underwriting_rentroll as rr
        self.assertIn("xldate_as_datetime", inspect.getsource(rr._load_rows))
        self.assertNotIn("xldate", inspect.getsource(rr._as_date))

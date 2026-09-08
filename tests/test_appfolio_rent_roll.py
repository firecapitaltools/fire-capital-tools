"""The Appfolio dialect: dispatched, inverted, and refusing what it cannot read.

WHY A SECOND PARSER

Michelle is walking Nabob Hill, whose rent roll is an Appfolio export.
Underwriting's parser required `Unit`, `Market Rent` and the
`Description`/`Amount` charge lines; an Appfolio roll has none of the
three, so it was refused outright, and Site DD's seeding inherited that
because it calls the same parser.

THE THING THIS FILE MOSTLY EXISTS TO PIN

**The status vocabulary inverts.** ResMan states occupancy and leaves
vacancy blank, so vacancy is INFERRED — and earns a note saying so.
Appfolio states vacancy outright and never leaves the column blank. So an
Appfolio vacancy is READ, and the note "Vacant inferred: the rent roll
gave no status" must never appear on one: it would be a false statement
about provenance, written onto client data, on a property being walked
right now.

That is easy to get wrong in a refactor, because both dialects end up
with the same two values. The difference is only in how they were reached.

THE FIXTURES ARE SYNTHETIC, DELIBERATELY

The rows below reproduce the STRUCTURE of a real Appfolio export — the
eight-row preamble, the property banner under the header, the two footer
rows — with invented units and no resident names. The real file is a
client's and is not in the repo; the one test that reads it is
environment-gated and skips everywhere else, the same arrangement the T12
tests use.
"""

import os
import pathlib
import unittest

from tools import underwriting_rentroll as rr
from tools.site_dd_seeding import (APPFOLIO_STATUS_MAP, plan_units,
                                   read_status)

# The real file, if this machine has it. See ENVIRONMENT_GATED below.
REAL_ROLL = pathlib.Path(
    os.environ.get("APPFOLIO_ROLL",
                   "C:/Users/jaspe/Downloads/Jackson 0816 RR test.xlsx"))

ENVIRONMENT_GATED = (
    "the real Appfolio rent roll is a client's file and is not in the repo; "
    "set APPFOLIO_ROLL to a copy to run the end-to-end check. The structure "
    "it has is reproduced synthetically by every other test here."
)

HEADER = ["Unit", "BD/BA", "Tenant", "Status", "Sqft", "Rent", "Deposit",
          "Move-in", "Move-out", "Past Due"]


def appfolio_rows(units=None, preamble=True, banner=True, footers=True):
    """A workbook shaped like the real export, with invented contents."""
    rows = []
    if preamble:
        rows += [["Rent Roll"] + [None] * 9,
                 ["Exported On: 08/16/2026"] + [None] * 9,
                 [None] * 10,
                 ["Properties: 100 Example Street"] + [None] * 9,
                 ["Units: Active"] + [None] * 9,
                 ["As of: 08/16/2026"] + [None] * 9,
                 ["Include Non-Revenue Units: No"] + [None] * 9,
                 ["Include Advertised Rent: No"] + [None] * 9,
                 [None] * 10]
    rows.append(list(HEADER))
    if banner:
        rows.append(["100 Example Street - 100 Example"] + [None] * 9)
    for u in (units if units is not None else [
            ("1", "1/1.00", "Current"),
            ("2", "1/1.00", "Vacant-Unrented"),
            ("3", "1/1.00", "Notice-Unrented")]):
        label, kind, status = u
        rows.append([label, kind, "A Resident", status, None, 1000, 100,
                     None, None, 0])
    if footers:
        rows.append(["3 Units", None, None, "66.7% Occupied"] + [None] * 6)
        rows.append(["Total 3 Units", None, None, "66.7% Occupied"] + [None] * 6)
    return rows


RESMAN_HEADER = ["Unit", "Type", "Sq. Feet", "Residents", "Status",
                 "Market Rent", "Ledger", "Description", "Amount"]


class DispatchTests(unittest.TestCase):
    """Two signatures, disjoint on three columns each. That is what makes
    this a dispatch rather than a guess."""

    def test_an_appfolio_header_is_recognised(self):
        self.assertIsNotNone(rr._appfolio_header_index(appfolio_rows()))

    def test_a_resman_header_is_not_read_as_appfolio(self):
        rows = [list(RESMAN_HEADER)]
        self.assertIsNone(rr._appfolio_header_index(rows))

    def test_the_absence_half_is_load_bearing(self):
        """A ResMan export carrying a Status column must NOT match both.
        Without requiring the absence of Market Rent and the charge lines,
        the caller could not tell which parser to run."""
        rows = [RESMAN_HEADER + ["BD/BA"]]
        self.assertIsNone(rr._appfolio_header_index(rows))
        self.assertIsNotNone(rr._header_index(rows))

    def test_a_file_matching_neither_is_refused_and_says_what_it_saw(self):
        rows = [["Unit", "Something", "Else"], ["1", "x", "y"]]
        with self.assertRaises(rr.UnrecognizedRentRoll) as ctx:
            rr.parse_appfolio_rent_roll(rows)
        self.assertIn("Appfolio", str(ctx.exception))


class WhatItReadsTests(unittest.TestCase):

    def setUp(self):
        self.parsed = rr.parse_appfolio_rent_roll(appfolio_rows())

    def test_one_row_per_unit(self):
        self.assertEqual(self.parsed["unit_count"], 3)
        self.assertEqual([u["unit"] for u in self.parsed["units"]],
                         ["1", "2", "3"])

    def test_the_banner_and_both_footers_are_not_units(self):
        """All three carry text in the Unit column and would each open a
        phantom unit. Each is excluded by having no BD/BA — the same
        corroboration rule the ResMan path uses."""
        labels = [u["unit"] for u in self.parsed["units"]]
        for intruder in ("100 Example Street - 100 Example", "3 Units",
                         "Total 3 Units"):
            self.assertNotIn(intruder, labels)

    def test_sqft_is_absent_not_zero(self):
        """Empty on every row of the only real file we hold. Coercing to
        zero would put a real-looking number in front of somebody."""
        for u in self.parsed["units"]:
            self.assertIsNone(u["sqft"])

    def test_the_dialect_travels_with_every_row(self):
        """The seeding must not re-derive the dialect from whether a cell
        was blank; it has to be told."""
        for u in self.parsed["units"]:
            self.assertEqual(u["dialect"], "appfolio")

    def test_it_names_its_own_format(self):
        self.assertEqual(self.parsed["source_format"], "Appfolio Rent Roll")

    def test_no_market_rent_is_reported_rather_than_invented(self):
        for u in self.parsed["units"]:
            self.assertIsNone(u["market_rent"])
        self.assertTrue(any("market rent" in w.lower()
                            for w in self.parsed["warnings"]))


class TheInversionTests(unittest.TestCase):
    """The half that would write a false note if it regressed."""

    def test_appfolio_vacancy_is_read_never_inferred(self):
        reading = read_status("Vacant-Unrented", "appfolio")
        self.assertEqual(reading.mapped, "vacant")
        self.assertFalse(reading.inferred,
                         "an Appfolio vacancy is stated by the file")

    def test_resman_blank_is_still_inferred(self):
        """The ResMan rule is untouched: blank means vacant, and says so."""
        reading = read_status("", None)
        self.assertEqual(reading.mapped, "vacant")
        self.assertTrue(reading.inferred)

    def test_notice_unrented_counts_as_occupied(self):
        """THE FILE'S OWN ARITHMETIC, NOT THE OBVIOUS READING. Jackson's
        footer says 93.8% occupied of 16 units. 93.8% of 16 is 15, and the
        file holds 14 Current + 1 Notice-Unrented + 1 Vacant-Unrented — so
        Appfolio counts a resident on notice as in place."""
        self.assertEqual(read_status("Notice-Unrented", "appfolio").mapped,
                         "occupied")
        occupied = 14 + 1
        self.assertAlmostEqual(round(100 * occupied / 16, 1), 93.8, places=1)

    def test_the_map_covers_exactly_the_vocabulary_seen(self):
        self.assertEqual(set(APPFOLIO_STATUS_MAP),
                         {"CURRENT", "NOTICE-UNRENTED", "VACANT-UNRENTED"})

    def test_a_blank_appfolio_status_is_refused_not_defaulted(self):
        """No blank exists in the file we hold, so there is no evidence
        for what one means. Inventing a rule is the guess the ResMan blank
        earned through four independent signals and this has not."""
        reading = read_status("", "appfolio")
        self.assertIsNone(reading.mapped)
        self.assertFalse(reading.inferred)

    def test_no_inference_note_on_any_appfolio_row(self):
        parsed = rr.parse_appfolio_rent_roll(appfolio_rows())
        plan = plan_units(parsed["units"])
        self.assertEqual(len(plan["units"]), 3)
        for u in plan["units"]:
            for note in u.notes:
                self.assertNotIn("Vacant inferred", note)
            self.assertFalse(u.status.inferred)

    def test_current_earns_no_note_the_way_resman_C_does_not(self):
        """A note on every occupied unit is noise."""
        parsed = rr.parse_appfolio_rent_roll(
            appfolio_rows(units=[("1", "1/1.00", "Current")]))
        plan = plan_units(parsed["units"])
        self.assertEqual(plan["units"][0].notes, ())


class TheStudioIsRefusedTests(unittest.TestCase):
    """DO NOT "FIX" THIS AS AN OVERSIGHT.

    `0/1.00` parses cleanly to zero bedrooms, and a studio genuinely has
    none — so seeding it might be right. The problem is that a unit with
    living, kitchen and bathroom and nothing else is ALSO exactly what a
    parse failure looks like, and after the seed nothing distinguishes
    them.

    Nothing we hold contains a studio, so the correct behaviour is
    untested either way. Refusing surfaces it once, on a preview, where a
    person can look at it and add the unit by hand.
    """

    def test_a_zero_bedroom_type_is_refused(self):
        self.assertIsNone(rr.parse_unit_type("0/1.00"))

    def test_one_bedroom_still_parses(self):
        """Positive control: the refusal is about zero, not about the
        Appfolio format."""
        layout = rr.parse_unit_type("1/1.00")
        self.assertIsNotNone(layout)
        self.assertEqual((layout.beds, layout.baths), (1, 1.0))

    def test_the_refusal_reaches_the_preview_by_name(self):
        parsed = rr.parse_appfolio_rent_roll(
            appfolio_rows(units=[("1", "1/1.00", "Current"),
                                 ("2", "0/1.00", "Current")]))
        plan = plan_units(parsed["units"])
        self.assertEqual([u.label for u in plan["units"]], ["1"])
        self.assertEqual([r.label for r in plan["refusals"]], ["2"])
        self.assertIn("bedrooms", plan["refusals"][0].reason)

    def test_resman_studios_were_already_refused(self):
        """A ResMan studio has no leading pair at all, so this decision
        changes nothing for that dialect."""
        self.assertIsNone(rr.parse_unit_type("Studio"))
        self.assertIsNone(rr.parse_unit_type("STU Upgraded"))


class ResManIsUnchangedTests(unittest.TestCase):

    def test_a_resman_workbook_still_takes_the_resman_path(self):
        rows = [list(RESMAN_HEADER),
                ["101", "1/1", 690, "A Resident", "C", 1065, "Resident",
                 "Rent", 900]]
        self.assertIsNotNone(rr._header_index(rows))
        self.assertIsNone(rr._appfolio_header_index(rows))

    def test_resman_rows_carry_no_dialect_key(self):
        """Absent means ResMan, which is why read_status defaults there.
        Every existing caller keeps working untouched."""
        self.assertEqual(read_status("C").mapped, "occupied")
        self.assertEqual(read_status("C", None).mapped, "occupied")


@unittest.skipUnless(REAL_ROLL.exists(), ENVIRONMENT_GATED)
class AgainstTheRealFileTests(unittest.TestCase):
    """Environment-gated. Everything above is synthetic; this is the file."""

    @classmethod
    def setUpClass(cls):
        cls.parsed = rr.parse_rent_roll_workbook(REAL_ROLL)
        cls.plan = plan_units(cls.parsed["units"])

    def test_it_dispatches_to_appfolio(self):
        self.assertEqual(self.parsed["source_format"], "Appfolio Rent Roll")

    def test_sixteen_units_with_thirteen_missing(self):
        labels = [u["unit"] for u in self.parsed["units"]]
        self.assertEqual(labels, [str(n) for n in list(range(1, 13))
                                  + list(range(14, 18))])
        self.assertNotIn("13", labels)

    def test_fifteen_of_sixteen_read_as_occupied(self):
        occupied = sum(1 for u in self.plan["units"]
                       if u.status.mapped == "occupied")
        self.assertEqual((occupied, len(self.plan["units"])), (15, 16))
        self.assertAlmostEqual(round(100 * occupied / 16, 1), 93.8, places=1)

    def test_nothing_is_refused_and_nothing_is_inferred(self):
        self.assertEqual(self.plan["refusals"], [])
        self.assertFalse(any(u.status.inferred for u in self.plan["units"]))

    def test_sqft_absent_on_every_row(self):
        self.assertTrue(all(u["sqft"] is None for u in self.parsed["units"]))


if __name__ == "__main__":
    unittest.main()

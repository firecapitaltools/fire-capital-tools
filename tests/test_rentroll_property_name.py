"""The preview shows which building the FILE says it is for.

WHY THIS EXISTS, AND IT IS NOT A BUG REPORT

Somebody imported 152 units into an assessment and the preview said
"152 units will be created". **It was the right file.** Nobody was misled
and nothing went wrong.

The point is that the sentence reads identically either way. **A
confirmation screen that shows only the CONSEQUENCE cannot help anyone
check the PREMISE** — the consequence is what the tool knows, the premise
is which building this is, and only the person knows that. So the screen
has to carry the file's own answer next to the assessment's, and let them
compare.

THE COMPARISON IS DELIBERATELY LOPSIDED

A false "these disagree" costs two seconds of reading two names. A false
"these agree" is the whole failure: a reassurance printed at precisely the
moment somebody is about to seed a building from the wrong file. So
agreement is asserted only on evidence — identical names, whole-token
containment, or a pairing the platform already knows — and everything
else is a stated disagreement or no verdict at all.

**And it never blocks.** Names legitimately differ, an assessment may be
labelled with an abbreviation or a deal code, and refusing an import over
a name would be a rule Michelle has not asked for.
"""

import unittest

from tools import underwriting_rentroll as rr
from tools.site_dd_seeding import (MATCH_NO, MATCH_UNKNOWN, MATCH_YES,
                                   compare_property_name)
from tests.test_appfolio_rent_roll import HEADER, appfolio_rows

RESMAN_HEADER = ["Unit", "Type", "Sq. Feet", "Residents", "Status",
                 "Market Rent", "Ledger", "Description", "Amount"]


def resman_rows(preamble=("", "Example Gardens Apartments",
                          "Some Property Management, LLC", "Rent Roll",
                          "8/16/2026", "Printed 8/16/2026 8:52:49 PM", "")):
    rows = [[line] + [None] * 8 for line in preamble]
    rows.append(list(RESMAN_HEADER))
    rows.append(["101", "1/1", 690, "A Resident", "C", 1065, "Resident",
                 "Rent", 900])
    return rows


class ExtractionTests(unittest.TestCase):

    def test_resman_takes_the_name_above_the_header(self):
        rows = resman_rows()
        self.assertEqual(rr._property_name_resman(rows, rr._header_index(rows)),
                         "Example Gardens Apartments")

    def test_resman_skips_its_own_furniture(self):
        """Without the boilerplate list, a file whose name cell is empty
        would report "Rent Roll" as the property — which is worse than
        reporting nothing, because it looks like an answer."""
        rows = resman_rows(preamble=("", "Rent Roll", "8/16/2026",
                                     "Printed 8/16/2026 8:52:49 PM"))
        self.assertIsNone(rr._property_name_resman(rows, rr._header_index(rows)))

    def test_appfolio_takes_the_properties_line_without_the_address(self):
        rows = appfolio_rows()
        idx = rr._appfolio_header_index(rows)
        rows[3] = ["Properties: 100 Example Street - 100 Example Street "
                   "San Francisco, CA 94133"] + [None] * 9
        self.assertEqual(rr._property_name_appfolio(rows, idx),
                         "100 Example Street")

    def test_a_file_with_no_name_yields_None_not_blank(self):
        """ABSENT IS NOT EMPTY. The preview says "it does not name a
        property" rather than rendering a blank where a name should be."""
        rows = appfolio_rows(preamble=False)
        idx = rr._appfolio_header_index(rows)
        self.assertIsNone(rr._property_name_appfolio(rows, idx))

    def test_both_parsers_put_it_on_the_result(self):
        parsed = rr.parse_appfolio_rent_roll(appfolio_rows())
        self.assertIn("property_name", parsed)


class ComparisonTests(unittest.TestCase):

    def verdict(self, a, b):
        return compare_property_name(a, b).verdict

    # ── agreement, only on evidence ──────────────────────────────────────

    def test_identical_names_agree(self):
        self.assertEqual(self.verdict("Oxford Pointe", "Oxford Pointe"),
                         MATCH_YES)

    def test_one_name_containing_the_other_agrees(self):
        self.assertEqual(self.verdict("Oxford Pointe Apartments",
                                      "Oxford Pointe"), MATCH_YES)

    def test_the_abbreviation_the_platform_already_knows(self):
        """"Oxford Pointe Apartments" against "OXPT" is a match a person
        makes instantly and a string comparison does not. The pairing is
        reused from the Weekly Property Summary rather than restated."""
        check = compare_property_name("Oxford Pointe Apartments", "OXPT")
        self.assertEqual(check.verdict, MATCH_YES)
        self.assertIn("OXPT", check.reason)

    def test_case_and_punctuation_do_not_matter(self):
        self.assertEqual(self.verdict("OXFORD POINTE, APARTMENTS",
                                      "oxford pointe apartments"), MATCH_YES)

    # ── disagreement ─────────────────────────────────────────────────────

    def test_two_real_and_unrelated_names_differ(self):
        self.assertEqual(self.verdict("1120 Jackson Street", "OXPT"), MATCH_NO)

    def test_the_case_this_was_built_for(self):
        """Jackson's Appfolio roll into an assessment labelled OXPT."""
        check = compare_property_name("1120 Jackson Street", "OXPT")
        self.assertEqual(check.verdict, MATCH_NO)
        self.assertEqual(check.file_name, "1120 Jackson Street")
        self.assertEqual(check.assessment_name, "OXPT")

    def test_token_order_is_not_ignored(self):
        self.assertEqual(self.verdict("Eagle Rock", "Rock Eagle"), MATCH_NO)

    def test_a_fragment_inside_a_word_is_not_a_match(self):
        """Whole tokens only: "Point" must not match inside "Pointer"."""
        self.assertEqual(self.verdict("Pointer Ridge", "Point"), MATCH_NO)

    # ── no verdict rather than a wrong one ───────────────────────────────

    def test_a_file_that_names_nothing_gets_no_verdict(self):
        check = compare_property_name(None, "OXPT")
        self.assertEqual(check.verdict, MATCH_UNKNOWN)
        self.assertIn("does not name a property", check.reason)

    def test_an_unnamed_assessment_gets_no_verdict(self):
        self.assertEqual(self.verdict("Oxford Pointe Apartments", None),
                         MATCH_UNKNOWN)

    def test_a_very_short_name_is_not_evidence_of_agreement(self):
        """A two-letter name appearing inside a longer one is a
        coincidence waiting to happen, and a coincidence that says
        "agree" is the failure this is shaped around."""
        self.assertNotEqual(self.verdict("A B Street Apartments", "A B"),
                            MATCH_YES)

    def test_agreement_is_never_the_default(self):
        """Positive control on the whole design: nothing unknown or
        unrelated may come back as a match."""
        for a, b in ((None, None), ("", ""), ("1120 Jackson Street", "ERA"),
                     ("Nabob Hill", "Oxford Pointe")):
            with self.subTest(pair=(a, b)):
                self.assertNotEqual(compare_property_name(a, b).verdict,
                                    MATCH_YES)


class ItIsInformationNotAGateTests(unittest.TestCase):
    """The apply route must not consult this. A mismatch is shown and the
    import proceeds if the person wants it to."""

    def test_the_check_has_no_opinion_the_apply_route_can_read(self):
        import inspect
        from tools import site_dd
        source = inspect.getsource(site_dd.seed_apply)
        self.assertNotIn("compare_property_name", source)
        self.assertNotIn("property_check", source)


if __name__ == "__main__":
    unittest.main()

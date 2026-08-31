"""The digest, and the property that makes it worth having.

An unread flag is cleared by a glance. **An unclaimed row stays unclaimed
until somebody writes down what was decided**, which is the act that was
actually missing when three of Michelle's asks shipped without ever
reaching HANDOFF.

So the tests here are mostly about the citation: what counts as one, what
must not, and that the block is regenerated rather than edited.
"""

import tempfile
import unittest
from pathlib import Path

from tools import feedback_digest as fd

ROOT = Path(__file__).resolve().parent.parent

ROWS = [
    {"id": 1, "tool": "Deal Analyzer", "message": "lookin good",
     "created_at": "2026-08-04T22:08:09"},
    {"id": 2, "tool": "Site DD",
     "message": "1. Swap out the condition summary\n2. upload the rent roll",
     "created_at": "2026-08-16T23:28:00"},
    {"id": 3, "tool": "Investor Report",
     "message": "1. remove top description\n2. notetaker reports\n"
                "3. add a property\n4. word template",
     "created_at": "2026-08-16T23:39:09"},
]


class TheBlockSaysWhatIsUnclaimedTests(unittest.TestCase):

    def test_a_row_nobody_cites_is_unclaimed(self):
        block = fd.render(ROWS, {})
        self.assertIn("**UNCLAIMED**", block)
        self.assertIn("3 rows. 3 unclaimed.", block)

    def test_a_cited_row_names_who_claimed_it(self):
        block = fd.render(ROWS, {3: ["HANDOFF.md", "tools/investor_notes.py"]})
        self.assertIn("`HANDOFF.md`", block)
        self.assertIn("`tools/investor_notes.py`", block)
        self.assertIn("3 rows. 2 unclaimed.", block)

    def test_a_row_with_no_ask_is_claimed_the_same_way(self):
        """POSITIVE CONTROL ON THE FORMAT. Row 1 is "lookin good" and has
        nothing in it, and the digest must not need a heuristic to say so
        -- a judgement that there is nothing to do is still a judgement
        somebody made, and it is recorded the same way as any other."""
        block = fd.render(ROWS, {1: ["HANDOFF.md"]})
        self.assertIn("3 rows. 2 unclaimed.", block)
        row = [l for l in block.splitlines() if l.startswith("| **1**")][0]
        self.assertNotIn("UNCLAIMED", row)

    def test_items_are_counted_not_interpreted(self):
        block = fd.render(ROWS, {})
        self.assertIn("| 4 |", block)          # row 3's four numbered items
        self.assertIn("| — |", block)          # row 1 is not a list

    def test_it_is_deterministic(self):
        self.assertEqual(fd.render(ROWS, {2: ["a.md"]}),
                         fd.render(ROWS, {2: ["a.md"]}))


class WhatCountsAsACitationTests(unittest.TestCase):

    def cite_in(self, text):
        root = Path(tempfile.mkdtemp())
        (root / "note.md").write_text(text, encoding="utf-8")
        return fd.citations(root)

    def test_the_plain_form(self):
        self.assertEqual(self.cite_in("built for feedback #3"), {3: ["note.md"]})

    def test_the_wordier_forms(self):
        for text in ("feedback row 3", "feedback-3", "Feedback #3", "feedback 3"):
            with self.subTest(text=text):
                self.assertIn(3, self.cite_in(text))

    def test_a_bare_hash_number_is_not_a_citation(self):
        """`#3` alone is an issue number, a heading anchor and half a
        colour. The word has to be there."""
        self.assertEqual(self.cite_in("see #3 and #ffffff"), {})

    def test_prose_about_feedback_in_general_is_not_a_citation(self):
        self.assertEqual(self.cite_in("the feedback table has three rows"), {})

    def test_several_files_can_claim_one_row(self):
        root = Path(tempfile.mkdtemp())
        (root / "a.md").write_text("feedback #2 done", encoding="utf-8")
        (root / "b.py").write_text("# feedback #2 again", encoding="utf-8")
        self.assertEqual(sorted(fd.citations(root)[2]), ["a.md", "b.py"])


class TheDigestDoesNotClaimItsOwnRowsTests(unittest.TestCase):
    """Otherwise every row is claimed the moment it is printed, and the
    check becomes a mirror.

    THIS FILE IS THE OTHER HALF OF THAT, and it was caught by running the
    thing: the fixtures below contain "feedback #2 done" and "feedback
    row 3", and on the first run those claimed two REAL production rows
    on behalf of nobody. A checker satisfied by its own examples is the
    dead-reader defect in a new costume, so `citations()` skips this file
    by name -- the same narrow exclusion as the module itself, for the
    same reason, and both are named in one line rather than a pattern.
    """

    def test_the_generated_block_is_excluded_from_the_scan(self):
        root = Path(tempfile.mkdtemp())
        block = fd.render(ROWS, {})
        (root / "HANDOFF.md").write_text(
            "before\n" + block + "\nafter\n", encoding="utf-8")
        self.assertEqual(fd.citations(root), {})

    def test_this_test_file_does_not_claim_anything(self):
        """The fixtures here are examples, not claims."""
        cited = fd.citations(ROOT)
        for rid, where in cited.items():
            with self.subTest(row=rid):
                self.assertNotIn("tests/test_feedback_digest.py", where)

    def test_a_test_about_the_WORK_does_count(self):
        """`test_investor_notes` says "Her word for it, from feedback row
        3" -- a person recording why that test exists, which is exactly
        what a claim is."""
        self.assertIn("tests/test_investor_notes.py",
                      fd.citations(ROOT).get(3, []))

    def test_but_a_citation_outside_the_block_still_counts(self):
        root = Path(tempfile.mkdtemp())
        block = fd.render(ROWS, {})
        (root / "HANDOFF.md").write_text(
            "feedback #2 was triaged\n" + block, encoding="utf-8")
        self.assertEqual(fd.citations(root), {2: ["HANDOFF.md"]})


class ItIsRegeneratedNotEditedTests(unittest.TestCase):

    def target(self, body):
        path = Path(tempfile.mkdtemp()) / "H.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_it_replaces_everything_between_the_markers(self):
        path = self.target(f"head\n{fd.BEGIN}\nstale\n{fd.END}\ntail\n")
        fd.write_into(path, fd.render(ROWS, {}))
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("stale", text)
        self.assertIn("head", text)
        self.assertIn("tail", text)

    def test_regenerating_an_unchanged_block_changes_nothing(self):
        block = fd.render(ROWS, {})
        path = self.target(f"head\n{block}\ntail\n")
        self.assertFalse(fd.write_into(path, block))

    def test_a_file_without_markers_is_refused_rather_than_appended_to(self):
        """Appending to the end of a 4,000-line document is how a
        generated section ends up in two places, each half right."""
        path = self.target("no markers here\n")
        with self.assertRaises(ValueError) as ctx:
            fd.write_into(path, fd.render(ROWS, {}))
        self.assertIn("markers", str(ctx.exception))


class HandoffCarriesTheBlockTests(unittest.TestCase):
    """The convention only works if the block is somewhere it is read."""

    def test_handoff_has_the_markers(self):
        text = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn(fd.BEGIN, text)
        self.assertIn(fd.END, text)

    def test_the_real_rows_are_all_claimed_today(self):
        """Every row in production has been triaged and cited. If this
        fails, either a new row arrived or a citation was deleted — both
        of which are the thing this file exists to surface."""
        cited = fd.citations(ROOT)
        for rid in (1, 2, 3):
            with self.subTest(row=rid):
                self.assertTrue(cited.get(rid),
                                f"feedback row {rid} is cited nowhere in the repo")


if __name__ == "__main__":
    unittest.main()

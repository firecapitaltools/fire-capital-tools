"""`docs/known-issues.md` keeps its shape, or it decays into a scratch note.

The file exists because "nobody checked" and "checked and fine" look
identical months later. That only holds if every entry actually carries
the thing that distinguishes them — **How to close it**. An entry without
one is a worry, and a file of worries is what this replaces.

These assertions are about STRUCTURE, not content. They cannot tell
whether a closing procedure is any good; they can tell whether somebody
wrote one down.
"""

import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "known-issues.md"
HANDOFF = Path(__file__).resolve().parents[1] / "HANDOFF.md"

REQUIRED = ("**What is believed.**", "**What is actually known.**",
            "**Why it is not settled.**", "**Cost if wrong.**",
            "**How to close it.**")


def entries(text):
    """The numbered entries, skipping the format preamble.

    Entry headings are `## <n>. <title>`. The preamble's own `## The
    format` heading is not numbered, which is what keeps the template
    below out of the results -- it documents the headings rather than
    using them, and counting it would make every assertion here pass on
    the template alone.
    """
    parts = re.split(r"^## (?=\d+\.)", text, flags=re.M)[1:]
    return [("## " + p).strip() for p in parts]


class TheFileIsThereTests(unittest.TestCase):
    def test_it_exists(self):
        self.assertTrue(DOC.exists(), f"{DOC} is missing")

    def test_handoff_points_at_it(self):
        """A file nobody is sent to is a file nobody reads."""
        self.assertIn("docs/known-issues.md",
                      HANDOFF.read_text(encoding="utf-8"))

    def test_there_is_at_least_one_entry(self):
        self.assertGreaterEqual(len(entries(DOC.read_text(encoding="utf-8"))), 1)


class EveryEntryIsCompleteTests(unittest.TestCase):
    def setUp(self):
        self.entries = entries(DOC.read_text(encoding="utf-8"))

    def test_each_carries_all_six_headings(self):
        for entry in self.entries:
            title = entry.splitlines()[0]
            for heading in REQUIRED:
                with self.subTest(entry=title, heading=heading):
                    self.assertIn(heading, entry)

    def test_each_is_dated_and_has_a_severity_and_a_status(self):
        for entry in self.entries:
            title = entry.splitlines()[0]
            with self.subTest(entry=title):
                self.assertRegex(entry, r"\*\*Opened\*\* \d{4}-\d{2}-\d{2}")
                self.assertRegex(entry, r"\*\*Severity\*\* (low|medium|high)")
                self.assertRegex(entry,
                                 r"\*\*Status\*\* (open|closed \d{4}-\d{2}-\d{2})")

    def test_how_to_close_it_has_actual_steps(self):
        """A numbered list, not a sentence saying someone should look."""
        for entry in self.entries:
            title = entry.splitlines()[0]
            tail = entry.split("**How to close it.**", 1)[1]
            with self.subTest(entry=title):
                self.assertRegex(tail, r"^\s*1\.", msg="no numbered steps")

    def test_the_preamble_template_is_not_counted_as_an_entry(self):
        """The positive control for `entries()`.

        The format block spells out all six headings. If the splitter
        picked it up, every assertion above would pass on the template
        even if no real entry satisfied them.
        """
        for entry in self.entries:
            self.assertNotIn("<short title>", entry)


class TheUserStoreEntryTests(unittest.TestCase):
    """Entry 1 is the reason the file was created. It gets pinned so a
    later tidy-up cannot quietly drop it while it is still open."""

    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")

    def test_it_is_present(self):
        self.assertIn("Volume persistence for the user store is unverified",
                      self.text)

    def test_it_names_the_variable_and_the_path(self):
        self.assertIn("USER_STORE_PATH", self.text)
        self.assertIn("/data/users.json", self.text)

    def test_the_closing_procedure_removes_the_throwaway_account(self):
        """Leaving a live account with a known password on production is
        worse than the thing being investigated."""
        entry = [e for e in entries(self.text) if "Volume persistence" in e][0]
        tail = entry.split("**How to close it.**", 1)[1].lower()
        self.assertIn("remove", tail)


if __name__ == "__main__":
    unittest.main()

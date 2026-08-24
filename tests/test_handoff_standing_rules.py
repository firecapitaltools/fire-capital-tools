"""The next rewrite of HANDOFF.md drops a standing rule loudly, not silently.

WHY THIS EXISTS AND WHY IT IS NOT test_handoff_rule_scope

`test_handoff_rule_scope` compares statements WITHIN one document: it
flags a rule stated twice whose shorter statement lost its condition. It
cannot see this failure at all, and widening it would not help — **a rule
that exists in no statement has no scope to disagree with**. Absence is
not detectable from inside a document.

Detecting absence needs a predecessor to diff against, and that is exactly
what was missing: the original handoff carried eleven numbered standing
rules, `HANDOFF.md` replaced it in Part 11 rather than editing it, the
original was never committed, and four rules were dropped with nothing to
notice for thirty-six runs.

`docs/original-handoff-standing-rules.md` is now that predecessor, and
this is the diff. Each rule below is represented by a marker phrase that
must remain findable in `HANDOFF.md`.

WHAT A FAILURE HERE MEANS

Not "put the sentence back". It means a standing rule left the document,
and the fix is a decision: restore it, or record why it is obsolete. Rule
4 is the model of the second kind — deliberately superseded, with the old
form named so it is not reinstated by accident. Rules 8 and 11 are
deliberately NOT fully present, for reasons written into the doc, and are
excluded here rather than asserted.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "HANDOFF.md"
ORIGINAL = ROOT / "docs" / "original-handoff-standing-rules.md"

# marker -> what its absence would mean
REQUIRED = {
    "BOTH failure states":
        "rule 1: every persistent DB path demonstrates both failure states",
    "FULL-COLLECTION-REWRITE ROUTES ARE DANGEROUS":
        "rule 2: partial POSTs silently blank collections -- a data-loss rule "
        "from real recovered incidents",
    "Merge discipline":
        "rule 3: fetch, merge, deploy, verify, report, never chain",
    "Verification is by behaviour":
        "rule 4, in its superseding form: the two-signal behavioural "
        "fingerprint that replaced the byte-hash",
    "No fabricated authority":
        "rule 5: nothing is established unless it was read from the thing itself",
    "No scraping":
        "rule 6, narrowed to its actual domain",
    "metered third-party call":
        "rule 7, generalised from OpenAI to every metered call",
    "One merge at a time":
        "rule 8's surviving half",
    "instruction is wrong or stale":
        "rule 9: report a bad instruction rather than building around it",
    "Reachability is not correctness":
        "rule 10: passing tests never say anyone can reach the feature",
}

# Deliberately not asserted, with the reason recorded rather than implied.
NOT_ASSERTED = {
    "rule 8, easiest-to-hardest ordering":
        "lapsed and not restored -- work runs in the order the prompt sets, "
        "and restoring a rule nobody follows teaches the list to be ignored",
    "rule 11, Census and BLS have no paid tiers":
        "lives in tools/service_costs.py instead, structured and carrying a "
        "last_verified date -- and the code is more honest than the rule was",
}


class EveryRestoredRuleIsStillInTheHandoffTests(unittest.TestCase):
    def setUp(self):
        self.text = HANDOFF.read_text(encoding="utf-8")

    def test_handoff_exists(self):
        self.assertTrue(HANDOFF.is_file())

    def test_each_rule_is_traceable(self):
        missing = [f"{marker!r} -- {why}"
                   for marker, why in REQUIRED.items()
                   if marker not in self.text]
        self.assertEqual(
            missing, [],
            "a standing rule left HANDOFF.md. Restore it, or record why it "
            "is obsolete the way rule 4 was:\n  " + "\n  ".join(missing))

    def test_the_check_can_actually_fail(self):
        """Positive control on the mechanism, not on the marker strings.

        The first version asserted each marker was at least twelve
        characters, which establishes nothing -- a long string that
        happens to match is exactly as vacuous as a short one, and it
        failed on "No scraping" for being eleven. What matters is that
        the search reports a missing rule as missing.
        """
        absent = "a standing rule that was never written down"
        self.assertNotIn(absent, self.text)
        missing = [m for m in list(REQUIRED) + [absent] if m not in self.text]
        self.assertEqual(missing, [absent],
                         "the check must flag an absent rule and only that one")


class ThePredecessorIsKeptTests(unittest.TestCase):
    """The corollary the original never had: keep the old document.

    It was never committed, so there was nothing to diff against and no
    way to notice the loss. A superseded document costs a few kilobytes
    and is the only instrument that can audit its successor.
    """

    def test_the_original_rules_are_preserved(self):
        self.assertTrue(ORIGINAL.is_file())

    def test_all_eleven_are_recorded(self):
        text = ORIGINAL.read_text(encoding="utf-8")
        for n in range(1, 12):
            with self.subTest(rule=n):
                self.assertIn(f"{n}. **", text)

    def test_it_says_it_is_not_current(self):
        """A historical record read as live guidance is its own hazard."""
        text = ORIGINAL.read_text(encoding="utf-8")
        self.assertIn("Do not treat this as current", text)

    def test_every_deliberate_omission_carries_a_reason(self):
        text = ORIGINAL.read_text(encoding="utf-8")
        for label, reason in NOT_ASSERTED.items():
            with self.subTest(label=label):
                self.assertTrue(reason.strip())
        # Both omissions are argued in the document, not just here.
        self.assertIn("easiest-to-hardest ordering lapsed", text)
        self.assertIn("service_costs.py", text)


if __name__ == "__main__":
    unittest.main()

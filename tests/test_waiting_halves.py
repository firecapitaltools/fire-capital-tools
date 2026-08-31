"""A waiting-half comment is a claim, and claims go stale.

THE CONVENTION, AND WHY IT NEEDED AN INSTRUMENT RATHER THAN A SIXTH SWEEP

When a feature ships in halves, the half that ships alone carries a
comment saying nothing calls it, what the other half is, and whether it
is safe to wire. Three modules carry one today: `site_dd_costs
.to_capex_lines`, `underwriting_capex.SOURCE_SITE_DD`, and
`underwriting_rentroll.layouts_for_units`.

**The convention's weakness is not that people forget to write the
comment. It is that nobody deletes it when the half is wired** -- and a
comment saying "nothing calls this" on a function with three callers is
worse than no comment, because a reader who believes it will look in the
wrong places. `site_dd_seed_write` proved both directions inside two
merges: it carried the notice for exactly one merge and then had to have
it rewritten by hand.

So this file does not look for dead code. **It checks that the sentences
we already wrote are still true.** Input set: comments that make the
claim. Failure: a claim that has stopped being true.

WHY NOT WIDEN THE SWEEPS INSTEAD -- MEASURED, 2026-08-31

Part 35 measured the candidate sweep at 81 hits, 54 of them
framework-dispatched routes, leaving 27 to triage, of which one was a
real finding. Re-measured now over `tools/*.py` with the prefix filter
dropped: **601 public module-level functions, 120 with no reference
outside their own module.** Forty-two of the 120 are helpers of one large
module (`fire_metrics_ai_summary`); two are the class this convention is
for. That is a **98% noise rate, worse than the 71% Part 35 measured**,
and the yield is two findings that were both discovered by a person
reading code for another reason.

The conclusion from Part 35 stands and is now better supported: a sixth
instrument is not the lesson. A cheap check on the claims we already make
is.
"""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The marker every waiting-half comment carries, in either casing. The
# SUBJECT is not parsed out of the sentence -- these comments say "nothing
# calls this" as often as they name the function, and guessing which word
# is the symbol is how a checker ends up asserting things about the word
# "this". The subject is the enclosing definition, resolved on the AST.
CLAIM = re.compile(r"NOTHING (?:IN PRODUCTION )?CALLS", re.IGNORECASE)


def claims() -> list[tuple[Path, str, int]]:
    """(file, symbol, line) for every 'nothing calls this' claim in tools/.

    A marker outside any function is skipped: `site_dd_seed_write`'s
    module docstring carries the history of one, and history is not a
    claim about today.
    """
    found = []
    for path in sorted(ROOT.glob("tools/*.py")):
        source = path.read_text(encoding="utf-8")
        spans = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                spans.append((node.lineno, node.end_lineno, node.name))
        for i, line in enumerate(source.splitlines(), 1):
            if not CLAIM.search(line):
                continue
            enclosing = [n for start, end, n in spans if start <= i <= end]
            if enclosing:
                found.append((path, enclosing[-1], i))
    return found


def references(symbol: str, defining: Path) -> list[str]:
    """Every file outside `defining` and outside tests that CALLS it.

    ON THE AST, NOT ON THE TEXT, and that distinction is the reason this
    check is trustworthy. `to_capex_lines` is named in prose in three
    other modules — explaining what it is and why not to wire it — and a
    substring search reports those as callers, so the check would fail
    loudest on precisely the waiting half whose comment is most carefully
    written. A checker fooled by a good comment is the original
    dead-reader defect arriving from the other direction.
    """
    out = []
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts or ".git" in path.parts:
            continue
        if path.resolve() == defining.resolve():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if ((isinstance(node, ast.Name) and node.id == symbol)
                    or (isinstance(node, ast.Attribute) and node.attr == symbol)
                    or (isinstance(node, ast.alias) and node.name == symbol)):
                out.append(str(path.relative_to(ROOT)))
                break
    # Templates are not Python, so a Jinja reference is text — with the
    # comments stripped first, for the same reason the AST is used above.
    for path in ROOT.rglob("templates/**/*.html"):
        markup = re.sub(r"\{#.*?#\}", " ",
                        path.read_text(encoding="utf-8", errors="ignore"),
                        flags=re.S)
        if re.search(rf"\b{re.escape(symbol)}\b", markup):
            out.append(str(path.relative_to(ROOT)))
    return out


class TheClaimsAreStillTrueTests(unittest.TestCase):

    def test_there_are_claims_to_check(self):
        """POPULATION FIRST. Every assertion below is a loop over the
        claims, and a regex that matched nothing would pass all of them
        -- the vacuous-check failure this project has already had once,
        on a partition over 39 of 89 definitions."""
        self.assertGreaterEqual(len(claims()), 3)

    def test_the_known_three_are_among_them(self):
        symbols = {s for _, s, _ in claims()}
        for expected in ("to_capex_lines", "layouts_for_units"):
            with self.subTest(symbol=expected):
                self.assertIn(expected, symbols)

    def test_nothing_that_claims_to_be_uncalled_has_a_caller(self):
        """THE WHOLE POINT. Wiring a waiting half is welcome; leaving the
        comment saying otherwise is not."""
        for path, symbol, line in claims():
            with self.subTest(symbol=symbol, where=f"{path.name}:{line}"):
                callers = references(symbol, path)
                self.assertEqual(
                    callers, [],
                    f"{path.name}:{line} says nothing calls {symbol}, but "
                    f"{', '.join(callers)} does. Wiring it is fine -- the "
                    f"comment has to stop saying it is unwired.")


class ThePositiveControlTests(unittest.TestCase):
    """An instrument that has never returned a difference has not been
    tested, and this one asserts an emptiness."""

    def test_a_claim_about_a_called_function_fails(self):
        """`build_lines` is called from site_dd.py. A claim about it must
        be caught, or the check above proves nothing."""
        defining = ROOT / "tools" / "site_dd_capex_export.py"
        self.assertNotEqual(references("build_lines", defining), [],
                            "build_lines has no callers, so this control "
                            "no longer controls anything")

    def test_the_marker_matches_both_phrasings_used_today(self):
        for line in ("    NOTHING CALLS THIS. It is the hand-off,",
                     "    NOTHING IN PRODUCTION CALLS IT TODAY -- the preview"):
            with self.subTest(line=line.strip()[:30]):
                self.assertTrue(CLAIM.search(line))

    def test_and_does_not_fire_on_ordinary_prose(self):
        for line in ("# this function calls nothing in particular",
                     "# nothing here reaches out to the network"):
            with self.subTest(line=line):
                self.assertIsNone(CLAIM.search(line))

    def test_a_marker_outside_a_function_is_not_a_claim(self):
        """`site_dd_seed_write`'s module docstring records that it USED to
        be a waiting half. History is not a claim about today, and reading
        it as one would fail this suite for a module that is wired."""
        modules = {p.name for p, _, _ in claims()}
        self.assertNotIn("site_dd_seed_write.py", modules)


class TheSweepsStillCannotSeeTheseTests(unittest.TestCase):
    """Recorded as a test rather than a comment, because it is the reason
    this file exists and it would otherwise be an assumption."""

    def test_the_dead_reader_sweep_does_not_cover_them(self):
        from tests import test_dead_readers as sweep
        for path, symbol, _ in claims():
            with self.subTest(symbol=symbol):
                in_glob = path.name.endswith("_db.py")
                prefixed = symbol.startswith(sweep.READER_PREFIXES)
                self.assertFalse(
                    in_glob and prefixed,
                    f"{symbol} IS covered by the dead-reader sweep now, so "
                    f"the waiting-half comment is belt and braces rather "
                    f"than the only guard -- worth saying so in the file.")


if __name__ == "__main__":
    unittest.main()

"""The suite checks itself: every test file must actually run.

WHAT THIS EXISTS TO CATCH, IN THE WORDS OF THE THING THAT HAPPENED

`tests/test_fire_metrics_improvements.py` imported `httpx`. Locally
`openai` was not installed, `httpx` came only with it, and so the module
failed to import — **161 tests did not run on this machine for weeks**.

Nothing went red. `unittest discover` reports an unimportable module as
ONE error, so a hundred and sixty missing tests and one broken test look
identical in the summary line. The gap was reconciled against the
container every time, correctly, by unique test id, and came back as the
same 161 ids in the same single module — and was read as an explanation
of a number rather than as a module that was not executing.

So the assertion here is not about a count. A count nets out: two modules
failing to import while one gains 160 tests is a difference of zero.
These ask whether every file can run at all.

WHAT THIS CANNOT DO, SAID PLAINLY

**It cannot compare the two environments.** Parity needs both, and a test
has only the one it is running in. `tools.suite_parity --compare` does
that and needs a person to run `--ids` on the container. What is pinned
here is the LOCAL condition that produced the failure, which is the half
that is checkable from inside.

The alternative — committing an expected test count and asserting against
it — is worse than nothing. It passes on the day both sides are wrong
together, and it needs editing on every merge until somebody edits it
without looking.
"""

import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from tools.suite_parity import (  # noqa: E402
    compare, empty_modules, environment_gated, import_failures, test_ids)

TESTS = pathlib.Path(__file__).resolve().parent


class EveryTestModuleRunsTests(unittest.TestCase):
    """The two things that were true of the invisible module."""

    def test_no_test_module_fails_to_import(self):
        """THE CONDITION THAT HID 161 TESTS.

        Named, not counted: the failure message carries the module and
        the exception, because "one module is missing" is the finding
        and "the totals differ by 161" is arithmetic.
        """
        failures = import_failures(TESTS)
        self.assertEqual(
            failures, {},
            "a test module does not import, so its tests are not running "
            "and unittest will report that as a single error:\n" +
            "\n".join(f"  {name}: {why}" for name, why in failures.items()))

    def test_no_test_module_collects_zero_tests(self):
        """The quiet version: discovered, imported, and empty."""
        empty = empty_modules(TESTS)
        self.assertEqual(empty, [],
                         f"test files collecting no tests: {empty}")

    def test_there_are_test_modules_at_all(self):
        """Assert the population before asserting about its contents.

        Both checks above pass vacuously against an empty directory —
        no modules, no failures. This is what stops a glob that has
        stopped matching from reading as a clean bill of health.
        """
        modules = sorted(p.stem for p in TESTS.glob("test_*.py"))
        self.assertGreater(len(modules), 50,
                           "the test glob has stopped matching")
        self.assertIn("test_suite_integrity", modules)


class TheCheckActuallyDetectsItTests(unittest.TestCase):
    """Positive controls. Without these, every assertion above passes on
    a function that has been quietly changed to return nothing."""

    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        sys.path.insert(0, str(self.dir.parent))
        self.pkg = self.dir.name
        (self.dir / "__init__.py").write_text("")
        self.addCleanup(sys.path.remove, str(self.dir.parent))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(lambda: [sys.modules.pop(m) for m in list(sys.modules)
                                 if m.startswith(self.pkg)])

    def _write(self, name, body):
        (self.dir / f"{name}.py").write_text(body, encoding="utf-8")

    def test_a_broken_import_is_caught_and_the_module_is_named(self):
        """Break one, and the check must say which one and why."""
        self._write("test_fine", "import unittest\n"
                                 "class T(unittest.TestCase):\n"
                                 "    def test_a(self): pass\n")
        self._write("test_broken", "import a_module_that_is_not_installed\n")
        failures = import_failures(self.dir, package=self.pkg)
        self.assertEqual(list(failures), ["test_broken"])
        self.assertIn("ModuleNotFoundError", failures["test_broken"])
        self.assertIn("a_module_that_is_not_installed",
                      failures["test_broken"])

    def test_the_healthy_case_really_reports_nothing(self):
        """The control on the control: an unbroken directory is clean,
        so the check above is not simply always failing."""
        self._write("test_fine", "import unittest\n"
                                 "class T(unittest.TestCase):\n"
                                 "    def test_a(self): pass\n")
        self.assertEqual(import_failures(self.dir, package=self.pkg), {})
        self.assertEqual(empty_modules(self.dir, package=self.pkg), [])

    def test_a_module_with_no_tests_is_caught(self):
        self._write("test_hollow", "x = 1\n")
        self.assertEqual(empty_modules(self.dir, package=self.pkg),
                         ["test_hollow"])

    def test_an_unimportable_module_is_one_error_not_many(self):
        """WHY THIS FILE EXISTS, demonstrated rather than asserted in
        prose: sixty tests behind a broken import cost exactly one line
        of failure output, which is why nobody saw a hundred and sixty."""
        body = ("import a_module_that_is_not_installed\n"
                "import unittest\n"
                "class T(unittest.TestCase):\n")
        body += "".join(f"    def test_{i}(self): pass\n" for i in range(60))
        self._write("test_many_hidden", body)
        suite = unittest.defaultTestLoader.discover(
            str(self.dir), top_level_dir=str(self.dir.parent))
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(import_failures(self.dir, package=self.pkg).keys(),
                         {"test_many_hidden"})


class EnvironmentGatedIsDeclaredNotDiscoveredTests(unittest.TestCase):
    """Nineteen tests skipped on the container for months, and the only
    trace was a number in a summary line nobody was diffing.

    A skip hides the same way an unimportable module does: the run stays
    green and the count moves quietly. So a module that needs something
    the machine may not have says so in the file, and the parity report
    prints it.
    """

    def test_the_real_t12_module_declares_its_gate(self):
        gated = environment_gated(TESTS)
        self.assertIn("test_underwriting_math", gated)
        reason = gated["test_underwriting_math"]["reason"]
        self.assertIn("T12_DIR", reason)
        self.assertIn("test_t12_shapes", reason,
                      "the gate should name what DOES run everywhere")

    def test_modules_without_a_gate_are_not_listed(self):
        """Positive control: without this, a function returning every
        module would satisfy the test above."""
        gated = environment_gated(TESTS)
        self.assertNotIn("test_suite_integrity", gated)
        self.assertLess(len(gated), 5,
                        "almost nothing should be environment-gated")

    def test_a_declaration_is_picked_up_from_any_module(self):
        d = pathlib.Path(tempfile.mkdtemp())
        sys.path.insert(0, str(d.parent))
        pkg = d.name
        (d / "__init__.py").write_text("")
        body = chr(10).join([
            "import unittest",
            "ENVIRONMENT_GATED = 'needs a thing'",
            "class T(unittest.TestCase):",
            "    def test_a(self): pass",
        ])
        (d / "test_gated.py").write_text(body)
        plain = chr(10).join([
            "import unittest",
            "class T(unittest.TestCase):",
            "    def test_a(self): pass",
        ])
        (d / "test_plain.py").write_text(plain)
        try:
            found = environment_gated(d, package=pkg)
            self.assertEqual(list(found), ["test_gated"])
            self.assertEqual(found["test_gated"]["reason"], "needs a thing")
            self.assertEqual(found["test_gated"]["tests"], 1)
        finally:
            sys.path.remove(str(d.parent))
            for m in [m for m in sys.modules if m.startswith(pkg)]:
                sys.modules.pop(m)
            shutil.rmtree(d, ignore_errors=True)


class ParityComparesSetsNotCountsTests(unittest.TestCase):
    """`compare()` is the half that needs the other environment. Its
    logic is testable here even though the comparison is not."""

    def test_equal_sets_agree(self):
        ids = {"tests.a.T.test_one", "tests.a.T.test_two"}
        self.assertTrue(compare(ids, set(ids))["agree"])

    def test_two_differences_that_net_to_zero_are_still_reported(self):
        """THE REASON THIS COMPARES SETS. One module gains a test while
        another loses one: the totals match exactly and the suites are
        not running the same thing."""
        local = {"tests.a.T.test_one", "tests.b.T.test_x"}
        remote = {"tests.a.T.test_one", "tests.c.T.test_y"}
        result = compare(local, remote)
        self.assertEqual(result["local_total"], result["remote_total"])
        self.assertFalse(result["agree"])
        self.assertEqual(result["only_local"], ["tests.b.T.test_x"])
        self.assertEqual(result["only_remote"], ["tests.c.T.test_y"])

    def test_a_whole_missing_module_is_named_as_such(self):
        """The 161 case: every missing id shares one module prefix."""
        local = {"tests.a.T.test_one"}
        remote = local | {f"tests.hidden.T.test_{i}" for i in range(161)}
        result = compare(local, remote)
        self.assertEqual(result["modules_missing_entirely"], ["hidden"])
        self.assertEqual(len(result["only_remote"]), 161)

    def test_a_scattering_is_not_called_a_missing_module(self):
        """Control on that: ids spread across modules that both sides
        have must NOT be reported as a module absence."""
        local = {"tests.a.T.test_one", "tests.b.T.test_two"}
        remote = local | {"tests.a.T.test_three", "tests.b.T.test_four"}
        self.assertEqual(compare(local, remote)["modules_missing_entirely"], [])

    def test_ids_are_ids_and_not_source_lines(self):
        """A line-grep tally once produced a phantom 14-test discrepancy
        here. Ids come from the loader."""
        ids = test_ids(TESTS, TESTS.parent)
        self.assertIn(
            "tests.test_suite_integrity.ParityComparesSetsNotCountsTests"
            ".test_ids_are_ids_and_not_source_lines", ids)
        self.assertTrue(all(i.startswith("tests.") for i in ids))


if __name__ == "__main__":
    unittest.main()

"""Do the two suites run the same tests? Compare the SET, not the count.

WHY THIS IS A MODULE AND NOT A TALLY

For weeks the local suite ran 2,419 tests and the container ran 2,580.
The difference was reconciled every time, correctly, by unique test id,
and it came back as the same 161 ids in the same single module. That was
read as an explanation of a number. It was a module that was not
executing.

    A difference with a NAME is a finding.
    A difference reported as a NUMBER is a fact about arithmetic.

So this compares sets of unique test ids and reports the names on each
side. **A count would have netted out**: two modules failing to import
while one gains 160 tests is a difference of zero, and a check that
compared totals would have called that agreement.

WHAT A TEST CAN AND CANNOT DO

Parity needs both environments, and a unit test has only the one it runs
in. So the work is split honestly:

* `tests/test_suite_integrity.py` asserts the LOCAL half — that no test
  module fails to import and none collects zero tests. **That is the
  exact condition that produced the 161**, and it is checkable here.
* This module's `compare()` does the real parity check, and needs
  somebody to run `--ids` on the container. That is a command, not an
  automatic guard, and it is described as one.

The thing not to build is a test that compares the local suite to a
number committed in a file. It would pass on the day both sides were
wrong together, and it would need editing on every merge until somebody
started editing it without looking.

HOW TO RUN THE PARITY CHECK

    railway ssh
    cd /app && python -m tools.suite_parity --ids > /tmp/remote.txt
    # then, locally:
    python -m tools.suite_parity --compare remote.txt
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import sys
import unittest
from typing import Any

TESTS_DIR = "tests"


def _module_names(root: pathlib.Path) -> list[str]:
    return sorted(p.stem for p in root.glob("test_*.py"))


def import_failures(root: pathlib.Path | str = TESTS_DIR,
                    package: str | None = None) -> dict[str, str]:
    """Modules that cannot be imported, mapped to why.

    This is the whole finding in one function. `unittest discover`
    reports an unimportable module as a SINGLE error — one line, one
    failure, regardless of whether the file held two tests or a hundred
    and sixty. A check that cannot run reports as a failure rather than
    as an absence, which is the same reason a reader nothing calls
    survives a sweep: the count of visible problems does not move.
    """
    root = pathlib.Path(root)
    package = package if package is not None else root.name
    failures: dict[str, str] = {}
    for name in _module_names(root):
        try:
            importlib.import_module(f"{package}.{name}")
        except BaseException as exc:  # noqa: BLE001 - report, never mask
            failures[name] = f"{type(exc).__name__}: {exc}"
    return failures


def empty_modules(root: pathlib.Path | str = TESTS_DIR,
                  package: str | None = None) -> list[str]:
    """Test files that collect nothing.

    A file named `test_*.py` holding zero tests is the quiet version of
    the same problem: it is discovered, it is imported, it reports
    nothing, and it costs nothing to keep. It is not always a defect —
    but it is always worth a name.
    """
    root = pathlib.Path(root)
    package = package if package is not None else root.name
    empty = []
    for name in _module_names(root):
        try:
            module = importlib.import_module(f"{package}.{name}")
        except BaseException:  # noqa: BLE001 - import_failures reports these
            continue
        if unittest.defaultTestLoader.loadTestsFromModule(
                module).countTestCases() == 0:
            empty.append(name)
    return empty


def environment_gated(root: pathlib.Path | str = TESTS_DIR,
                      package: str | None = None) -> dict[str, dict[str, Any]]:
    """Modules that say, in the file, that they need something absent.

    STATED RATHER THAN DISCOVERED. Nineteen tests skipped on the
    container for months because four real files live on one laptop, and
    the only trace was a skip count that nobody was comparing between
    runs. A skip is invisible in exactly the way an unimportable module
    is: the summary line stays green.

    A module declares it by setting `ENVIRONMENT_GATED` to a sentence
    saying what is missing and how to supply it. That is a claim its
    author writes deliberately, which is the point -- this cannot detect
    a gate nobody declared, and it is not pretending to.
    """
    root = pathlib.Path(root)
    package = package if package is not None else root.name
    out: dict[str, dict[str, Any]] = {}
    for name in _module_names(root):
        try:
            module = importlib.import_module(f"{package}.{name}")
        except BaseException:  # noqa: BLE001 - import_failures reports these
            continue
        reason = getattr(module, "ENVIRONMENT_GATED", None)
        if reason:
            out[name] = {
                "reason": str(reason),
                "tests": unittest.defaultTestLoader.loadTestsFromModule(
                    module).countTestCases(),
            }
    return out


def _flatten(suite: Any) -> list[str]:
    out: list[str] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            out.extend(_flatten(item))
        else:
            out.append(item.id())
    return out


def test_ids(root: pathlib.Path | str = TESTS_DIR,
             top: pathlib.Path | str = ".") -> set[str]:
    """Every unique test id this environment would run.

    Ids rather than lines: a line-grep tally once produced a phantom
    14-test discrepancy here, because source lines are not tests.
    """
    suite = unittest.defaultTestLoader.discover(str(root), top_level_dir=str(top))
    return set(_flatten(suite))


def compare(local: set[str], remote: set[str]) -> dict[str, Any]:
    """The parity result, named on both sides.

    `modules_missing_entirely` is called out separately because it is the
    signature of this class of failure: when every id a side is missing
    shares one module prefix, the module did not run. A scattering of
    ids is a different question and usually a benign one.
    """
    only_local = sorted(local - remote)
    only_remote = sorted(remote - local)

    def modules(ids: list[str]) -> set[str]:
        return {i.split(".")[1] for i in ids if i.count(".") >= 1}

    wholly_missing = sorted(
        m for m in modules(only_remote)
        if not any(i.startswith(f"tests.{m}.") for i in local))
    wholly_extra = sorted(
        m for m in modules(only_local)
        if not any(i.startswith(f"tests.{m}.") for i in remote))
    return {
        "agree": not only_local and not only_remote,
        "local_total": len(local),
        "remote_total": len(remote),
        "only_local": only_local,
        "only_remote": only_remote,
        "modules_missing_entirely": wholly_missing + wholly_extra,
    }


def _report(result: dict[str, Any]) -> str:
    if result["agree"]:
        return (f"the two suites run the same {result['local_total']} tests, "
                f"compared by unique id")
    lines = [f"local {result['local_total']} / remote {result['remote_total']} "
             f"-- THE SETS DIFFER"]
    if result["modules_missing_entirely"]:
        lines += ["", "WHOLE MODULES ABSENT FROM ONE SIDE -- this is the shape "
                      "that hid 161 tests:"]
        lines += [f"  {m}" for m in result["modules_missing_entirely"]]
    for label, key in (("only local", "only_local"), ("only remote", "only_remote")):
        if result[key]:
            lines += ["", f"{label} ({len(result[key])}):"]
            lines += [f"  {i}" for i in result[key][:20]]
            if len(result[key]) > 20:
                lines.append(f"  ... and {len(result[key]) - 20} more")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", action="store_true",
                        help="print every test id, one per line")
    parser.add_argument("--compare", metavar="FILE",
                        help="compare local ids against ids from FILE")
    args = parser.parse_args(argv)

    if args.ids:
        for test_id in sorted(test_ids()):
            print(test_id)
        return 0
    if args.compare:
        remote = {line.strip() for line in
                  pathlib.Path(args.compare).read_text().splitlines()
                  if line.strip()}
        result = compare(test_ids(), remote)
        print(_report(result))
        return 0 if result["agree"] else 1

    failures = import_failures()
    empty = empty_modules()
    if failures:
        print("MODULES THAT DO NOT IMPORT:")
        for name, why in failures.items():
            print(f"  {name}: {why}")
    if empty:
        print("MODULES THAT COLLECT NOTHING:", ", ".join(empty))
    if not failures and not empty:
        print(f"all {len(_module_names(pathlib.Path(TESTS_DIR)))} test modules "
              f"import and collect at least one test")

    gated = environment_gated()
    if gated:
        print()
        print("ENVIRONMENT-GATED -- these do not run everywhere, and say so:")
        for name, info in gated.items():
            print(f"  {name} ({info['tests']} tests in the module)")
            print(f"    {info['reason']}")
    return 1 if (failures or empty) else 0


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())

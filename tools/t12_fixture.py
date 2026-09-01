"""Turn a real T12 into a committable shape, carrying none of its money.

WHY

Nineteen tests asserted the expense-aggregation rules against four real
T12 files sitting in one person's Downloads folder. They are the checks
that catch the double-counting trap -- summing a P&L that carries both
parents and children inflates expenses by about 8x -- and on the
container they skipped, every run, silently. **A check that runs on one
laptop is a check that stops existing when that laptop does.**

The files cannot go in the repo. They are Michelle's, and a git history
is forever. So this takes the one thing the assertions actually need --
the SHAPE -- and leaves everything else behind.

WHAT IS PRESERVED, BECAUSE THE ASSERTIONS DEPEND ON IT

* the number of accounts and their order
* each account's `depth`, which is the entire parent/child structure:
  an account is a parent when the next one sits deeper
* the LEADING DIGIT of each code, because the breakdown selects expense
  lines with `[67]\\d{3}`
* each leaf's classification -- operating, capex or non-operating --
  which the code decides from the account NAME, so a synthetic name is
  chosen that classifies the same way and is then checked to
* whether a parent AGREES with the sum of its children, as a boolean

WHAT IS THROWN AWAY, WHICH IS EVERYTHING ELSE

* **every amount.** Not scaled, not rounded, not offset -- regenerated
  from an arithmetic formula that does not read the source value at all
* every account name and every account code
* the property name and the period

**The magnitude of a disagreement is thrown away too**, and that is
deliberate rather than lazy. Eagle Rock's parents and children really do
disagree, and the test that matters asserts that the disagreement is
REPORTED rather than quietly resolved. Keeping the real difference would
put one of her numbers in the repo to assert something no test needs.
So the fact is kept as a boolean and the magnitude is invented.

HOW THE ABSENCE OF HER FIGURES IS PROVED

Not by reading this docstring. `tests/test_t12_shapes.py` recomputes
every amount in the committed fixture from the formula below and asserts
equality. A single real number surviving anywhere in the file makes that
test fail, which is the only form of this claim worth having: a
generator that leaks one figure is worse than not doing this at all.

REGENERATING

    python -m tools.t12_fixture --from-real

Requires the real files; see `T12_DIR` in tests/test_underwriting_math.py.
Nobody needs to run it unless a new shape appears, and the real-file
tests stay in place precisely to notice that.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

FIXTURE = (pathlib.Path(__file__).resolve().parent.parent
           / "tests" / "fixtures" / "t12_shapes.json")

# Twelve neutral month labels. The real period is not recorded: it names
# the months of her financial year and says nothing the tests read.
MONTHS = [f"{m} 2020" for m in
          ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")]

# Names picked to land on each branch of KPICalculator._classify_line.
# The generator asserts that they do rather than trusting this table.
KIND_NAMES = {
    "operating": "Line Item",
    "capex": "Capital Replacement Item",
    "non_operating": "Mortgage Interest Payment",
}

# One parent in ten disagreeing by this much is a stand-in for a real
# disagreement, not a measurement of one.
DISAGREEMENT = 137.0


def synthetic_amount(index: int, month: int) -> float:
    """The whole of the money in this fixture.

    A function of position and nothing else. It never sees the source
    value, which is what makes "no real figures" checkable instead of
    asserted: recompute this for every cell and compare.
    """
    return float(1000 + 37 * index + 11 * month)


def derive(data: dict[str, Any]) -> dict[str, Any]:
    """Reduce one parsed T12 to the facts the assertions rest on."""
    from tools.scorecard_pro.kpis import KPICalculator

    ordered = list(data["accounts"].items())
    depths = [a.get("depth") for _, a in ordered]

    def is_parent(i: int) -> bool:
        d = depths[i]
        if d is None:
            return False
        nxt = next((depths[j] for j in range(i + 1, len(depths))
                    if depths[j] is not None), None)
        return nxt is not None and nxt > d

    accounts = []
    for i, (code, acc) in enumerate(ordered):
        parent = is_parent(i)
        accounts.append({
            "lead": str(code)[:1],
            "depth": acc.get("depth"),
            "parent": parent,
            # Only leaves are classified; a parent's name is a heading.
            "kind": (None if parent
                     else KPICalculator._classify_line(acc.get("name"))),
        })

    # Which parents disagree with the sum of their own children, as a
    # boolean. Recorded per position so Eagle Rock keeps having a
    # discrepancy and Jackson keeps not having one.
    disagreeing = _disagreeing_parents(ordered, depths)
    for i, a in enumerate(accounts):
        a["disagrees"] = i in disagreeing

    return {"format": data.get("meta", {}).get("format"),
            "flat": not any(d is not None for d in depths),
            "accounts": accounts}


def _disagreeing_parents(ordered, depths) -> set[int]:
    out = set()
    for i, (code, acc) in enumerate(ordered):
        d = depths[i]
        if d is None:
            continue
        kids = []
        for j in range(i + 1, len(ordered)):
            dj = depths[j]
            if dj is None:
                continue
            if dj <= d:
                break
            if dj == d + 1:
                kids.append(ordered[j][0])
        if not kids:
            continue
        parent_total = sum(v or 0.0 for v in acc["data"].values())
        kid_total = sum(sum(v or 0.0 for v in ordered_dict["data"].values())
                        for ordered_dict in
                        (dict(ordered)[k] for k in kids))
        if abs(parent_total - kid_total) > 0.005:
            out.add(i)
    return out


def build(shape: dict[str, Any]) -> dict[str, Any]:
    """Expand a shape back into something KPICalculator can read."""
    from tools.scorecard_pro.kpis import KPICalculator

    specs = shape["accounts"]
    counters: dict[str, int] = {}
    codes: list[str] = []
    for a in specs:
        lead = a["lead"]
        counters[lead] = counters.get(lead, 0) + 1
        codes.append(f"{lead}{counters[lead]:03d}")

    accounts: dict[str, Any] = {}
    for i, (code, a) in enumerate(zip(codes, specs)):
        name = (KIND_NAMES[a["kind"]] if a["kind"] else "Grouping")
        if a["kind"]:
            assert KPICalculator._classify_line(name) == a["kind"], name
        accounts[code] = {
            "name": f"{name} {i}",
            "depth": a["depth"],
            "data": {m: synthetic_amount(i, k)
                     for k, m in enumerate(MONTHS)},
        }

    # Parents are rewritten as the sum of their children so the naive sum
    # double-counts exactly as a real tree file does -- that IS the trap.
    depths = [a["depth"] for a in specs]
    for i in reversed(range(len(specs))):
        if not specs[i]["parent"]:
            continue
        d = depths[i]
        kids = []
        for j in range(i + 1, len(specs)):
            if depths[j] is None:
                continue
            if depths[j] <= d:
                break
            if depths[j] == d + 1:
                kids.append(codes[j])
        if not kids:
            continue
        for k, month in enumerate(MONTHS):
            total = sum(accounts[c]["data"][month] for c in kids)
            if specs[i]["disagrees"]:
                total += DISAGREEMENT
            accounts[code_at(codes, i)]["data"][month] = total

    return {"property": "Fixture Property",
            "period": "Twelve months",
            "accounts": accounts,
            "detail_totals": {},
            "meta": {"format": shape["format"], "warnings": []}}


def code_at(codes: list[str], i: int) -> str:
    return codes[i]


def load_fixture(path: pathlib.Path | str = FIXTURE) -> dict[str, Any]:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def regenerate(names: list[str]) -> dict[str, Any]:  # pragma: no cover - CLI
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from tests.test_underwriting_math import load
    return {name: derive(load(name)) for name in names}


def main(argv=None):  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-real", action="store_true",
                    help="re-derive the shapes from the real T12 files")
    args = ap.parse_args(argv)
    if not args.from_real:
        ap.error("nothing to do; pass --from-real")
    shapes = regenerate(["Eagle Rock", "Canyon", "OXPT", "Jackson"])
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(shapes, indent=1, sort_keys=True),
                       encoding="utf-8")
    print(f"wrote {FIXTURE} ({FIXTURE.stat().st_size} bytes)")
    for name, s in shapes.items():
        print(f"  {name}: {len(s['accounts'])} accounts, "
              f"flat={s['flat']}, "
              f"disagreeing parents="
              f"{sum(1 for a in s['accounts'] if a['disagrees'])}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())

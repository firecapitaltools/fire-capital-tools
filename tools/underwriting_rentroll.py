"""
FIRE Capital Tools - Rent roll parsing for Underwriting.

Turns a ResMan rent roll export into per-unit lines: unit, type, square
footage, status, in-place rent, market rent, and lease dates.

Why this is new code rather than reuse. mmr_report.parsers.parse_rent_roll
exists, but it answers a different question -- it returns two scalars,
{"total_rental", "avg_rent"}, for an operations report, and takes an MMR
worksheet plus an occupied count from the box score. Nothing in the MMR
package captures per-unit rents, square footage or lease dates, and
parse_available_units only covers the vacant/notice/holding subset. So the
extraction is new; the *helpers* are not -- the cell utilities and the
rent-line allowlist below are imported from the MMR package rather than
reimplemented, because they already encode real knowledge about which
ledger lines count as rent (HAP and other subsidies do, renters insurance
does not, concessions offset).

TWO DIALECTS, DISPATCHED ON THE HEADER. ResMan was first and is
unchanged below; Appfolio was added in Part 106 because Michelle is
walking a property whose roll is one. Any other layout, or a file that
matches both, raises UnrecognizedRentRoll rather than guessing -- the Scorecard Pro property-name collision came
from a parser that guessed when it did not recognize a file, and the same
mistake here would silently under- or over-state income for the whole
model.

Structure of a real export (confirmed against Eagle Rock, May 2026):

    row 8   Unit | Type | Sq. Feet | Residents | Status | Market Rent | ...
                 ... | Ledger | Description | Amount | Move In | Lease Start | Lease End
    row 9   0101 | 1/1 Upgraded | 690 | ... | C | 1065 | Resident | Rent   | 310
    row 10                                                        | HAP Rent| 665
    row 11                                                        | Total   | 975

Each unit spans several rows: one carrying the unit's attributes and its
first charge line, then further charge lines, then a Total. In-place rent
is summed from the charge lines that _is_rent_line accepts rather than
read off the Total row, so a unit whose ledger mixes rent with
non-rent charges is still counted correctly.

The Unit column is merged in the export, so its value lands one column to
the left of its own header. That is handled explicitly below rather than
by trusting the header index.
"""

from __future__ import annotations

import datetime
from typing import Any, NamedTuple

import re
from pathlib import Path

import openpyxl

from tools.mmr_report.helpers import (
    coerce_num,
    find_col,
    find_col_contains,
    looks_like_unit_value,
    norm,
    rows_of,
    safe_get,
)
from tools.mmr_report.parsers import _is_rent_line

MAX_HEADER_SCAN_ROWS = 40

# The export ends with a charge-type summary block ("Total Charges", then
# "Rent", "HAP Rent", "Pet Rent", ... with totals). Those labels satisfy
# looks_like_unit_value(), so without an explicit stop the summary reads as
# 27 extra phantom units on a real 92-unit Eagle Rock roll -- inflating the
# unit count and dragging every per-unit average toward zero.
_SUMMARY_TERMINATORS = ("total charges", "total credits", "grand total",
                        "summary", "charge summary")


class UnrecognizedRentRoll(ValueError):
    """Raised when the file is not a rent roll layout this parser
    understands. The message is written to be shown to the user."""


# Sheets that only ever appear in a Weekly Property Summary (MMR) export.
# Used to tell the user *which* wrong file they uploaded rather than just
# that it was wrong -- an MMR and a rent roll are both ResMan exports for
# the same property, so "unrecognized" alone would be an unhelpful answer.
#
# Two dialects are in circulation and both are covered. The long-form one
# (Eagle Rock, Canyon, OXPT, High Caliber) uses names like "Cash Flow
# Statement"; the short-form one (Maple Valley) uses "Cash Flow", "Work
# Order", "Tenant Tickler". Listing both matters only for the quality of
# the error message -- either way the file is rejected -- but naming the
# actual mistake is the difference between a user fixing it in seconds and
# re-uploading the same wrong file.
_MMR_SHEET_MARKERS = (
    # long form
    "box score", "cash flow statement", "delinquency", "bank deposit register",
    "bank deposits by category", "work order summary", "expiring leases",
    "new and renewed leases", "prospect source summary", "renewal percentages",
    "available units",
    # short form
    "cash flow", "work order", "tenant tickler", "vacancy", "check register",
    "deposit register", "general ledger",
)
# Three markers, not one: a genuine rent roll is a single unnamed sheet, so
# even one marker would in practice be decisive -- but requiring three means
# a future rent-roll variant that happens to carry a "Vacancy" tab is not
# mislabelled as an MMR.
_MMR_SHEET_MATCH_THRESHOLD = 3


def _looks_like_mmr(sheetnames) -> bool:
    """True when the workbook is a Weekly Property Summary export.

    Matched on several marker sheets rather than one, so a rent roll that
    happens to carry a single similarly-named tab is not misclassified.
    """
    present = {norm(s) for s in sheetnames}
    return sum(1 for m in _MMR_SHEET_MARKERS if m in present) >= _MMR_SHEET_MATCH_THRESHOLD


def _header_index(rows) -> int | None:
    """Row index of the column header band.

    Requires Unit, Market Rent, AND the Description/Amount charge-line pair.

    The charge-line requirement is the load-bearing part, and its absence is
    exactly what let an MMR through before. An MMR's "Available Units" sheet
    does carry Unit and Market Rent, so demanding only those two matched it
    happily -- and because that sheet lists vacant units and has no charge
    lines at all, every unit came back with an in-place rent of zero. The
    result was a fully-computed model built from nothing but vacant units.

    Description and Amount are the columns in-place rent is actually summed
    from, so requiring them is not a heuristic: a sheet without them cannot
    produce a rent roll, only a plausible-looking shell.
    """
    for idx, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        has_unit = find_col(row, "unit") is not None
        has_market = (find_col(row, "market rent") is not None
                      or find_col_contains(row, "market rent") is not None)
        has_charges = (find_col(row, "description") is not None
                       and find_col(row, "amount") is not None)
        if has_unit and has_market and has_charges:
            return idx
    return None


# ── Appfolio: a second dialect, dispatched rather than guessed ───────────
#
# Appfolio's rent roll is a different document that happens to share a
# name. One row per unit, no charge lines at all, and the layout written
# numerically:
#
#     rows 0-7  Rent Roll / Exported On: / Properties: / Units: Active /
#               As of: / Include Non-Revenue... / Include Advertised...
#     row 9     Unit | BD/BA | Tenant | Status | Sqft | Rent | Deposit |
#               Move-in | Move-out | Past Due
#     row 10    1120 Jackson Street - 1120 Jackson      <- property banner
#     row 11    1 | 1/1.00 | Kin Wah Fong | Current | | 2820 | 100 | ...
#     ...
#     footer    16 Units | | | 93.8% Occupied
#               Total 16 Units | | | 93.8% Occupied
#
# THE TWO SIGNATURES ARE DISJOINT ON THREE COLUMNS EACH, which is what
# makes this a dispatch and not a guess:
#
#     ResMan    Unit AND Market Rent AND Description/Amount
#     Appfolio  Unit AND BD/BA AND Status, and NEITHER Market Rent NOR
#               Description/Amount
#
# Confirmed against `Jackson 0816 RR test.xlsx` (1120 Jackson Street,
# exported 2026-08-16): 16 units, labels 1-12 and 14-17 with no unit 13,
# every layout `1/1.00`, sqft empty on every row, and statuses stated
# rather than blank.
_APPFOLIO_STATUS_COL = "status"


def _appfolio_header_index(rows) -> int | None:
    """Row index of an Appfolio header band, or None.

    Requires Unit, BD/BA and Status AND the ABSENCE of the two ResMan
    markers. The absence half is load-bearing: without it a ResMan export
    that happens to carry a Status column would match both dialects, and
    the caller could not tell which parser to run.
    """
    for idx, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        has_unit = find_col(row, "unit") is not None
        has_bdba = (find_col(row, "bd/ba", "bd / ba", "bdba") is not None
                    or find_col_contains(row, "bd/ba") is not None)
        has_status = find_col(row, "status") is not None
        has_market = (find_col(row, "market rent") is not None
                      or find_col_contains(row, "market rent") is not None)
        has_charges = (find_col(row, "description") is not None
                       and find_col(row, "amount") is not None)
        if has_unit and has_bdba and has_status and not has_market and not has_charges:
            return idx
    return None


def _appfolio_columns_seen(rows) -> list[str]:
    """What the best-looking header row actually carried, for the refusal
    message. Naming what WAS found is the difference between a message
    somebody can act on and one that just says no."""
    best: list[str] = []
    for row in rows[:MAX_HEADER_SCAN_ROWS]:
        labels = [str(c).strip() for c in row if str(c or "").strip()]
        if find_col(row, "unit") is not None and len(labels) > len(best):
            best = labels
    return best


def parse_appfolio_rent_roll(rows) -> dict[str, Any]:
    """One row per unit, and three kinds of row that are not units.

    The banner (`1120 Jackson Street - 1120 Jackson`) and both footers
    (`16 Units ... 93.8% Occupied`, `Total 16 Units ...`) all carry text in
    the Unit column and would open a phantom unit. Every one of them is
    distinguishable by having no BD/BA, which is the same corroboration
    rule the ResMan path already uses -- a unit number on its own is not a
    unit.
    """
    header_idx = _appfolio_header_index(rows)
    if header_idx is None:
        raise UnrecognizedRentRoll("Not an Appfolio rent roll layout.")
    header = rows[header_idx]
    cols = {
        "unit": find_col(header, "unit"),
        "type": (find_col(header, "bd/ba", "bd / ba", "bdba")
                 or find_col_contains(header, "bd/ba")),
        "status": find_col(header, _APPFOLIO_STATUS_COL),
        "sqft": find_col(header, "sqft", "sq ft", "square feet"),
        "rent": find_col(header, "rent"),
        "move_in": find_col(header, "move-in", "move in"),
        "move_out": find_col(header, "move-out", "move out"),
    }
    if cols["unit"] is None or cols["type"] is None or cols["status"] is None:
        raise UnrecognizedRentRoll(
            "Appfolio rent roll header found but its Unit/BD-BA/Status "
            "columns could not be read.")

    units: list[dict[str, Any]] = []
    for row in rows[header_idx + 1:]:
        label = str(safe_get(row, cols["unit"]) or "").strip()
        unit_type = str(safe_get(row, cols["type"]) or "").strip()
        if not label or not unit_type:
            # Banner and footer rows both land here. Neither carries a
            # layout, and a row without one cannot be seeded anyway.
            continue
        # WHAT NOTHING WE HOLD CAN VALIDATE, SAID WHERE THE PARSE HAPPENS.
        #
        # Every one of Jackson's 16 rows reads `1/1.00`. So this parser is
        # demonstrated on ONE layout string, and how Appfolio writes a unit
        # that is not one bedroom is UNKNOWN. If it writes `2/1.00` this
        # already works, because parse_unit_type reads a leading N/M and
        # ignores the rest. If it writes `2BD/1BA` or `2 BR / 1 BA` the
        # parse returns None, plan_units refuses the row by name, and the
        # preview shows it -- which is the right failure, but it is a
        # failure nobody here has seen.
        #
        # Do not add a pattern for a form nobody has a file of. The
        # letter-only unit rule was retired for exactly that reason: a
        # branch that cannot be exercised is a branch that cannot be
        # trusted. The first multi-bedroom Appfolio roll is the test.
        units.append({
            "unit": label,
            "unit_type": unit_type,
            # ABSENT, NOT ZERO. Sqft is empty on every row of the only
            # Appfolio file we hold; coercing to 0 would put a real number
            # in front of somebody. This repo has recorded that failure
            # three times.
            "sqft": coerce_num(safe_get(row, cols["sqft"]), default=None),
            "status": (str(safe_get(row, cols["status"]) or "").strip() or None),
            "market_rent": None,          # Appfolio has no market rent column
            "in_place_rent": coerce_num(safe_get(row, cols["rent"]), default=None),
            "lease_start": None,
            "lease_end": None,
            "move_in": _as_date(safe_get(row, cols["move_in"])),
            "move_out": _as_date(safe_get(row, cols["move_out"])),
            # THE DIALECT TRAVELS WITH THE ROW, because the status
            # vocabulary inverts between the two and the seeding must not
            # re-derive it from whether a cell was blank. See
            # site_dd_seeding.read_status.
            "dialect": "appfolio",
        })

    if not units:
        raise UnrecognizedRentRoll(
            "An Appfolio rent roll header was recognised but no unit rows "
            "were found under it.")

    warnings: list[str] = []
    missing_sqft = sum(1 for u in units if u["sqft"] is None)
    if missing_sqft:
        warnings.append(f"{missing_sqft} unit(s) have no square footage; they are "
                        f"excluded from average-sqft figures rather than counted as zero.")
    warnings.append(
        "Appfolio rent rolls carry no market rent, so gross potential rent "
        "cannot be read from this file.")
    return {
        "units": units,
        "unit_count": len(units),
        "warnings": warnings,
        "source_format": "Appfolio Rent Roll",
        "property_name": _property_name_appfolio(rows, header_idx),
    }


# ── The property the FILE says it is for ─────────────────────────────────
#
# WHY THIS IS EXTRACTED AT ALL. A preview that says "152 units will be
# created" reads identically whether the file is the right one or the
# wrong one. The consequence is what the tool knows; which building this
# is, is what the PERSON knows -- so the screen has to carry the file's own
# answer for them to compare against. See HANDOFF, "a confirmation screen
# that shows only the consequence".
#
# Both dialects state it, in different places:
#
#   ResMan    row 1, column 0        'Oxford Pointe Apartments'
#                                    (row 2 is the management company,
#                                     row 3 the title "Rent Roll")
#   Appfolio  preamble, column 0     'Properties: 1120 Jackson Street -
#                                     1120 Jackson Street San Francisco...'
#
# ABSENT IS None, NEVER "". A file that does not name a property is a
# different thing from one that names an empty string, and the preview
# says "this file does not name a property" rather than rendering a blank
# where a name should be. Falsy-absence has bitten this codebase in three
# directions already.

# Lines above a ResMan header that are furniture rather than a name.
_RESMAN_BOILERPLATE = ("rent roll", "current", "future", "notice", "vacant")
_DATE_ISH = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}")


def _property_name_resman(rows, header_idx: int) -> str | None:
    """The first line above the header that looks like a property name.

    Taken positionally rather than by label because the export carries no
    label for it -- it is simply the first thing on the page. The
    boilerplate list exists so that a file whose name cell is empty falls
    through to None instead of reporting "Rent Roll" as the property.
    """
    for row in rows[:header_idx]:
        value = str(safe_get(row, 0) or "").strip()
        if not value:
            continue
        low = norm(value)
        if low in _RESMAN_BOILERPLATE or low.startswith("printed"):
            continue
        if _DATE_ISH.match(value):
            continue
        return value
    return None


def _property_name_appfolio(rows, header_idx: int) -> str | None:
    """The `Properties:` line from the preamble.

    Appfolio writes `Properties: <name> - <full address>`. The part before
    the dash is the property as the file names it; the address after it is
    the same thing again at greater length and is not what a person is
    comparing against an assessment label.
    """
    for row in rows[:header_idx]:
        value = str(safe_get(row, 0) or "").strip()
        if not value.lower().startswith("properties:"):
            continue
        name = value.split(":", 1)[1].strip()
        if " - " in name:
            name = name.split(" - ", 1)[0].strip()
        return name or None
    return None


def _as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _unit_value(row, unit_col):
    """The unit number. Checked at the header's own column and the one to
    its left, because the export merges the Unit cell and openpyxl reports a
    merged value at the range's anchor."""
    for col in (unit_col - 1, unit_col, unit_col + 1):
        if col is None or col < 0:
            continue
        v = safe_get(row, col)
        if looks_like_unit_value(v):
            return str(v).strip()
    return None


def _load_rows(path) -> tuple[list[list[Any]], list[str]]:
    """The first sheet as rows, and the workbook's sheet names.

    ONE PLACE THAT KNOWS ABOUT FILE FORMATS.

    The parser below reasons about a list of lists and nothing else -- it
    uses the workbook only to get rows and to name the sheets when it
    rejects an MMR. Keeping the format branch here means a third format
    later has an obvious home, and means the parsing logic never grows a
    second opinion about what a cell is.

    ResMan exports .xls, not .xlsx. That is the whole reason this exists:
    the layout was already parsed correctly and completely -- 152 units at
    Oxford Pointe, every column mapped -- and the only thing standing
    between the tool and the file was that openpyxl cannot open OLE2.

    xlrd normalises differently from openpyxl and the difference is
    deliberate rather than smoothed over here: it yields `""` for an empty
    cell where openpyxl yields `None`, and floats for numbers that
    openpyxl may hand back as int. Every reader downstream goes through
    `coerce_num`, `norm` or `safe_get`, all of which already treat both
    the same, so normalising here would be inventing a conversion nobody
    needs.

    DATES ARE THE EXCEPTION AND THEY HAD TO BE CONVERTED HERE.

    openpyxl hands back a `datetime` for a date cell; xlrd hands back the
    raw serial number and keeps the cell type separately. `_as_date()`
    below parses datetimes and strings, so an unconverted serial fell
    through it and returned None -- and the first run of this loader
    reported **every lease date on all 152 units as absent** while the
    file plainly contained them. Data present in the source and silently
    reported as missing is the failure this codebase keeps finding, and it
    is worse than a crash because nothing looks wrong.

    So date cells are converted here, where the format difference lives,
    rather than teaching `_as_date()` about serial numbers -- it has no
    way to know which workbook a bare float came from, and 45839 is a
    plausible rent as well as a plausible date.
    """
    ext = Path(str(path)).suffix.lower()
    if ext == ".xls":
        # Imported here, not at module scope. xlrd is needed by one branch
        # of one function, and a missing optional dependency should fail
        # where it is used with a message about the file, not at import
        # time with a traceback about the module.
        import xlrd

        try:
            book = xlrd.open_workbook(str(path))
        except Exception as exc:
            raise UnrecognizedRentRoll(
                f"Could not open the rent roll file: {exc}") from exc
        sheet = book.sheet_by_index(0)

        def cell(r, c):
            value = sheet.cell_value(r, c)
            if sheet.cell_type(r, c) == xlrd.XL_CELL_DATE:
                try:
                    return xlrd.xldate_as_datetime(value, book.datemode)
                except (ValueError, OverflowError):
                    # A serial outside Excel's range. Left as it was found
                    # rather than guessed at; _as_date() will decline it
                    # and the field reads as unstated, which is true.
                    return value
            return value

        rows = [[cell(r, c) for c in range(sheet.ncols)]
                for r in range(sheet.nrows)]
        return rows, list(book.sheet_names())

    try:
        wb = openpyxl.load_workbook(str(path), data_only=True)
    except Exception as exc:
        raise UnrecognizedRentRoll(
            f"Could not open the rent roll file: {exc}") from exc
    return rows_of(wb[wb.sheetnames[0]]), list(wb.sheetnames)


def parse_rent_roll_workbook(path) -> dict[str, Any]:
    """Parse a ResMan rent roll into per-unit lines.

    Accepts .xlsx and .xls; see `_load_rows`. Raises UnrecognizedRentRoll
    if the layout is not recognized or yields no units -- never returns a
    partially-guessed result."""
    rows, sheetnames = _load_rows(path)

    # DISPATCH, NOT GUESS. Both dialects are workbooks whose first rows are
    # title text and neither names its own vendor anywhere worth trusting,
    # so the decision is made on the header row's columns. The signatures
    # are disjoint on three columns each; see _appfolio_header_index.
    #
    # AMBIGUITY REFUSES. Guessing wrong here seeds an entire building from
    # a misunderstanding, and the undo for that is a seed_batch rollback
    # that only works while nobody has walked the units -- which is exactly
    # the window an import is followed by.
    resman_idx = _header_index(rows)
    appfolio_idx = _appfolio_header_index(rows)
    if resman_idx is not None and appfolio_idx is not None:
        raise UnrecognizedRentRoll(
            "This file matches both the ResMan and the Appfolio rent roll "
            "layouts, so which one it is cannot be decided from its columns. "
            "Nothing was read. The header row carries: "
            + ", ".join(_appfolio_columns_seen(rows)) + ".")
    if appfolio_idx is not None:
        return parse_appfolio_rent_roll(rows)

    header_idx = resman_idx
    if header_idx is None:
        # Name the actual mistake when it is recognizable. An MMR is the file
        # most likely to be uploaded here by accident -- it is the same
        # property, the same system and a similar filename -- so it gets its
        # own message rather than a generic rejection.
        if _looks_like_mmr(sheetnames):
            raise UnrecognizedRentRoll(
                "This looks like a Weekly Property Summary / MMR export, not a "
                "rent roll. Please upload the property's actual rent roll file."
            )
        seen = _appfolio_columns_seen(rows)
        raise UnrecognizedRentRoll(
            "This does not look like a rent roll this tool reads. A ResMan "
            "export needs a 'Unit' column, a 'Market Rent' column and the "
            "'Description'/'Amount' charge lines that in-place rent is read "
            "from; an Appfolio export needs 'Unit', 'BD/BA' and 'Status'. "
            + (f"The closest header row carries: {', '.join(seen)}. "
               if seen else "No header row carrying a 'Unit' column was found. ")
            + "Upload one of those exports, or enter the rent roll manually."
        )

    header = rows[header_idx]
    cols = {
        "unit": find_col(header, "unit"),
        "type": find_col(header, "type", "unit type"),
        "sqft": find_col(header, "sq. feet", "sq feet", "sqft", "square feet"),
        "status": find_col(header, "status"),
        "market": find_col(header, "market rent") or find_col_contains(header, "market rent"),
        "description": find_col(header, "description"),
        "amount": find_col(header, "amount"),
        "lease_start": find_col(header, "lease start"),
        "lease_end": find_col(header, "lease end", "lease expires"),
        "move_in": find_col(header, "move in"),
        "move_out": find_col(header, "move out"),
    }
    if cols["unit"] is None or cols["market"] is None:
        raise UnrecognizedRentRoll("Rent roll header found but its Unit/Market Rent columns could not be read.")
    # _header_index already required these, so this is a belt-and-braces
    # guard against the two ever drifting apart -- without the charge lines
    # every in-place rent would silently come back as zero.
    if cols["description"] is None or cols["amount"] is None:
        raise UnrecognizedRentRoll(
            "Rent roll header found but it has no 'Description'/'Amount' charge "
            "lines, so in-place rent cannot be read. Upload a full rent roll "
            "export rather than a summary."
        )

    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    warnings: list[str] = []

    def close(u):
        if u is not None:
            u["in_place_rent"] = round(u.pop("_rent_accum", 0.0), 2)
            units.append(u)

    for row in rows[header_idx + 1:]:
        first = norm(safe_get(row, 0) or "")
        if first in _SUMMARY_TERMINATORS:
            break                      # per-unit detail is over

        unit_val = _unit_value(row, cols["unit"])
        # A genuine unit row carries at least one unit attribute alongside
        # its number. Requiring corroboration keeps stray labels elsewhere in
        # the sheet from opening a phantom unit block.
        if unit_val and not any((
            safe_get(row, cols["type"]),
            safe_get(row, cols["sqft"]),
            safe_get(row, cols["status"]),
            coerce_num(safe_get(row, cols["market"]), default=None) is not None,
        )):
            unit_val = None

        if unit_val:
            close(current)
            current = {
                "unit": unit_val,
                "unit_type": (str(safe_get(row, cols["type"]) or "").strip() or None),
                "sqft": coerce_num(safe_get(row, cols["sqft"]), default=None),
                "status": (str(safe_get(row, cols["status"]) or "").strip() or None),
                "market_rent": coerce_num(safe_get(row, cols["market"]), default=None),
                "lease_start": _as_date(safe_get(row, cols["lease_start"])),
                "lease_end": _as_date(safe_get(row, cols["lease_end"])),
                "move_in": _as_date(safe_get(row, cols["move_in"])),
                "move_out": _as_date(safe_get(row, cols["move_out"])),
                "_rent_accum": 0.0,
            }

        if current is None:
            continue

        desc = safe_get(row, cols["description"])
        amt = coerce_num(safe_get(row, cols["amount"]), default=None)
        if desc is None or amt is None:
            continue
        label = str(desc).strip()
        if norm(label) in ("total", "totals"):
            continue          # summary line; the charge lines above already counted
        if _is_rent_line(label, amt):
            current["_rent_accum"] += amt

    close(current)

    if not units:
        raise UnrecognizedRentRoll(
            "The rent roll header was recognized but no unit rows could be read "
            "from it. Check the file is a full rent roll export rather than a "
            "summary."
        )

    missing_market = sum(1 for u in units if u["market_rent"] is None)
    if missing_market:
        warnings.append(f"{missing_market} unit(s) have no market rent on file; "
                        f"their in-place rent is used for gross potential rent instead.")
    missing_sqft = sum(1 for u in units if u["sqft"] is None)
    if missing_sqft:
        warnings.append(f"{missing_sqft} unit(s) have no square footage; they are "
                        f"excluded from average-sqft figures rather than counted as zero.")

    return {
        "units": units,
        "unit_count": len(units),
        "warnings": warnings,
        "source_format": "ResMan Rent Roll",
        "property_name": _property_name_resman(rows, header_idx),
    }


# ── Bedrooms and bathrooms, from the unit type string ────────────────────
#
# Michelle: "IDEALLY, I'D LIKE THE TOOL TO RECOGNIZE THE NUMBER OF BEDROOMS
# AND BATHROOMS FROM THE RENT ROLL SO THE TOOL CAN ADJUST THE FIELDS
# ACCORDINGLY."
#
# ResMan puts the layout at the front of a free-text type string and then
# whatever else the property manager felt like typing:
#
#     '2/1.5 RENOVATED W/D'      '2 1.5 CLASSIC W/D'
#     '3/2 RENOVATED  down'      '2/2 CLASSIC NEW BUILDING  W/D'
#
# THE PATTERN IS ANCHORED AND STOPS. It reads the leading pair and nothing
# else, which is not tidiness -- `'3/2 RENOVATED  down'` ends in a word
# that collides with AREA_STATUSES, and a pattern that consumed the tail
# would hand "down" to something that reads statuses. The trailing text is
# a description nobody has asked us to interpret, so it is left alone.
#
# The separator is a slash OR a space: one of the 18 real strings at Oxford
# Pointe is `'2 1.5 CLASSIC W/D'`, typed without the slash.
UNIT_TYPE_RE = re.compile(r"^\s*(\d+)\s*[/ ]\s*(\d+(?:\.\d+)?)")


class UnitLayout(NamedTuple):
    """What a type string says about a unit's rooms.

    `baths` is kept as stated (1.5) alongside the split, because the
    rent roll's own words are what an inspector will recognise and the
    split is what Site DD needs to make rooms from.
    """

    beds: int
    baths: float
    full_baths: int
    half_baths: int


def parse_unit_type(text: Any) -> UnitLayout | None:
    """Bedrooms and bathrooms, or None when the string does not say.

    NONE IS REFUSED, NOT GUESSED, AND THE CALLER MUST REPORT IT.

    A studio has no leading integer pair in a ResMan file and there is no
    honest reading of one -- "0 bedrooms" is a guess, and so is "1". No
    such row exists in either rent roll we hold, so this path has never
    run against real data; it stays a refusal rather than a default
    precisely because it is untested. `layouts_for_units()` collects the
    refusals so they are shown rather than silently absent.

    **An Appfolio studio WOULD parse**, as `0/1.00`, and is refused
    explicitly below for the same reason rather than seeded.

    A fractional bath other than .5 is refused for the same reason. Every
    bath figure in the real file is 1, 1.5 or 2; .5 means one half bath,
    and what .25 or .75 would mean is not established by anything.
    """
    match = UNIT_TYPE_RE.match(str(text or ""))
    if not match:
        return None
    beds = int(match.group(1))
    if beds == 0:
        # A STUDIO IS REFUSED, AND THIS IS A DECISION MADE WITHOUT A SAMPLE.
        #
        # ResMan strings cannot reach here: a studio there has no leading
        # `N/M` pair, so it is already refused by the pattern. Appfolio
        # writes its layouts numerically -- `1/1.00` -- and a studio would
        # therefore arrive as `0/1.00` and parse cleanly to zero bedrooms.
        # This function was written and validated against ResMan; it
        # accepts the Appfolio form by accident rather than by design.
        #
        # Zero bedroom rooms might be exactly right for a studio. The
        # problem is that a unit seeded with living, kitchen and bathroom
        # and nothing else is ALSO precisely what a parse failure looks
        # like, and after the seed nothing distinguishes the two -- there
        # is no record of whether zero was read or fumbled.
        #
        # NOTHING WE HOLD CONTAINS A STUDIO, so the correct behaviour is
        # untested either way. Refusing surfaces it once, on the first
        # real one, on a preview where a person can look at it and add the
        # unit by hand. Seeding it would be silent and permanent.
        #
        # Do not "fix" this as an oversight. If a studio sample arrives,
        # decide it against the file.
        return None
    baths = float(match.group(2))
    full_baths = int(baths)
    remainder = round(baths - full_baths, 4)
    if remainder == 0.0:
        half_baths = 0
    elif remainder == 0.5:
        # 1.5 is one full bathroom plus one half. Site DD has no half-bath
        # room type and this design does not add one: the seeding run
        # makes two bathroom rooms and labels the second one, using
        # create_room's existing label parameter. No schema change.
        half_baths = 1
    else:
        return None
    return UnitLayout(beds=beds, baths=baths,
                      full_baths=full_baths, half_baths=half_baths)


def layouts_for_units(units: list[dict[str, Any]]) -> dict[str, Any]:
    """Every unit's layout, and every unit whose type string did not say.

    ── A HALF THAT SHIPPED ALONE. NOTHING CALLS layouts_for_units. ──────

    It was written as Underwriting's bed/bath derivation — the thing
    Michelle asked for when she said *"if the unit type is available, then
    the tool should automatically create 2 bedrooms"* — and Underwriting
    never grew a screen for it. **Site DD then imported `parse_unit_type`
    directly** and did its own grouping in `site_dd_seeding.plan_units`,
    so the derivation is live and this wrapper is not.

    **The other half is a unit mix by LAYOUT.** Underwriting's Unit Mix
    table groups on the raw type string: Oxford Pointe shows **18 rows**
    where the same file yields **6 layouts** — `2/1.5 RENOVATED`,
    `2/1.5 RENOVATED W/D` and `2/1.5 CLASSIC` are three rows of one
    layout. Both readings are right, and the second is the one that
    answers "how many two-beds are there".

    **Safe to wire as it stands**, with one thing to honour: it returns
    `unreadable` separately and the caller must SHOW it. Dropping that
    list is how a rent roll silently becomes 150 of 152, which is the
    failure this project keeps finding and the reason the refusals are
    returned rather than filtered.

    **NEITHER SWEEP CAN SEE THIS.** `tests/test_dead_readers.py` globs
    `tools/*_db.py` and gates on `READER_PREFIXES`; this module is
    neither. `tests/test_route_reachability.py` needs a route. The claim
    in this comment is kept honest by
    `tests/test_waiting_halves.py`, which fails when a function marked
    "nothing calls this" acquires a caller — so wiring it forces the
    comment to be updated rather than left to mislead.
    ────────────────────────────────────────────────────────────────────

    Returns the parsed rows and the refusals SEPARATELY rather than
    dropping the refusals or defaulting them. A rent roll whose types
    cannot be read should say so on the screen that imports it; a silent
    150-of-152 is the shape of failure this project keeps finding.
    """
    parsed: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for unit in units or []:
        layout = parse_unit_type(unit.get("unit_type"))
        row = {"unit": unit.get("unit"), "unit_type": unit.get("unit_type"),
               "sqft": unit.get("sqft"), "status": unit.get("status")}
        if layout is None:
            unreadable.append(row)
            continue
        parsed.append({**row, "beds": layout.beds, "baths": layout.baths,
                       "full_baths": layout.full_baths,
                       "half_baths": layout.half_baths})
    return {"units": parsed, "unreadable": unreadable,
            "parsed_count": len(parsed), "unreadable_count": len(unreadable)}

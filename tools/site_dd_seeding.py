"""Turning a parsed rent roll into a Site DD plan — WITHOUT WRITING IT.

`docs/site-dd-rentroll-seeding.md` is the design. This module builds
everything up to the preview and deliberately stops there: nothing here
opens a database, creates an area, or touches a finding. The preview is
the checkpoint, and the database it would write into holds Michelle's
live walk.

Three things the real Oxford Pointe file settled that the Part 35 spec
had guessed at, all of them recorded where the code implements them:

* the amenity suffix is on the LABEL, not only the type (`unit_key`);
* a lettered rent roll is refused rather than discriminated (`unit_key`);
* the status collapse needs no answer to what `UE` means (`STATUS_MAP`).

WHAT "REFUSED" MEANS HERE, EVERYWHERE

A row this module cannot read is returned in `refusals`, named
individually, and is never guessed at or dropped. Oxford Pointe produces
zero refusals, which is exactly the condition under which a
refusal-reporting path ships broken -- so the refusal list is built to be
exercised by files we do not have, and the tests supply them.
"""

from __future__ import annotations

import math
import re
from typing import Any, NamedTuple

from tools import site_dd_db as sdb
from tools.underwriting_rentroll import parse_unit_type

# ── The amenity suffix ───────────────────────────────────────────────────
#
# Six of Oxford Pointe's 152 unit labels carry it on the LABEL itself:
#
#     '122 W/D'  '222 W/D'  '226 W/D'  '521 W/D'  '526 W/D'  '529 W/D'
#
# The other 146 are plain numbers. `'226 W/D'` and `'226'` are the same
# apartment written two ways, and an inspector typing a unit into Site DD
# types `226`.
#
# The Part 35 spec anticipated this rule from the six W/D *type* strings
# and did not know it also applied to labels. It does, and that is the
# form that matters: the label is what an area is matched on.
#
# Anchored at the end, so a unit genuinely called "W/D 3" -- which would
# be strange, and which no file has -- is not silently truncated.
AMENITY_SUFFIX = re.compile(r"\s*\bW/?D\b\s*$", re.IGNORECASE)

# A unit label we are willing to key on: digits, optionally with a simple
# trailing letter (12A) or a dash segment (12-A). Deliberately narrow --
# see LETTERED_MESSAGE for what is NOT accepted and why.
UNIT_LABEL = re.compile(r"^\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?$")

# Rows a rent roll carries that are not units. Matched on the normalised
# label, and the list is short on purpose: anything not recognised is
# REFUSED rather than pattern-matched into oblivion.
NON_UNIT_LABELS = frozenset({
    "total", "totals", "subtotal", "grand total", "summary",
    "clubhouse", "office", "model", "leasing office", "maintenance shop",
    "vacant", "occupied", "unit",
})

LETTERED_MESSAGE = (
    "Unit labels starting with a letter are not supported yet. Some "
    "properties use the letter as a building (A1, B2) and some use it as "
    "part of the unit number, and reading it the wrong way would attach "
    "findings to the wrong apartment."
)


class Refusal(NamedTuple):
    """One row this module declined, named rather than counted."""

    label: str
    reason: str


def unit_key(label: Any) -> str | None:
    """The key a rent-roll row and a Site DD area are matched on.

    None when the label is not a unit label this module will key on. The
    caller must report it -- see `plan_units`.

    THE 60% LETTER DISCRIMINATOR IS DELIBERATELY NOT BUILT.

    The Part 35 spec detects a letter-labelled building by asking whether
    more than 60% of labels start with a letter, and treats the letter as
    a building discriminator when they do. **No file we hold can exercise
    that.** Every one of Oxford Pointe's 152 labels is numeric; not one
    starts with a letter. A threshold that cannot be run against real data
    is a branch that will be wrong in a way nobody notices, and this file
    already supplies the reminder -- `'3/2 RENOVATED  down'` is the row a
    representative sample drops.

    So a lettered roll is refused BY NAME, and the refusal says why. When
    a real lettered rent roll arrives, the threshold can be built against
    it and tested. Until then the honest position is that we do not know
    which convention a given property uses.
    """
    text = str(label or "").strip()
    if not text:
        return None
    text = AMENITY_SUFFIX.sub("", text).strip()
    if not text:
        return None
    if text.casefold() in NON_UNIT_LABELS:
        return None
    if text[0].isalpha():
        return None
    if not UNIT_LABEL.match(text):
        return None
    return text.upper()


def _refusal_reason(label: Any) -> str:
    """Why one label was declined. Specific to the label, never generic."""
    text = str(label or "").strip()
    if not text:
        return "the row has no unit number"
    stripped = AMENITY_SUFFIX.sub("", text).strip()
    if not stripped:
        return "the row's unit number is only an amenity marker"
    if stripped.casefold() in NON_UNIT_LABELS:
        return f"{stripped!r} is a summary or common-area row, not a unit"
    if stripped[0].isalpha():
        return LETTERED_MESSAGE
    return (f"{stripped!r} is not a unit number this import recognises "
            f"(expected digits, optionally with a trailing letter)")


# ── Status ───────────────────────────────────────────────────────────────
#
# Michelle: "unit status isn't important for my purpose. What is most
# important is the correct unit number, unit type, occupied or vacant."
#
# So the ResMan vocabulary collapses to two. The mapping was established
# from the file rather than from the acronyms -- see the design document
# section 1:
#
#   C     132 units   current
#   NTV     1 unit    unit 640: resident, lease, move-in AND a move-out of
#                     2026-08-13. Occupied today, leaving on a known date.
#   UE      1 unit    unit 217: resident, current lease, $960 in-place
#                     rent, no move-out. THE FILE HAS NO LEGEND and this
#                     module does not expand the acronym from plausibility.
#   blank  18 units   no lease, no lease end, no move-in, no in-place
#                     rent -- on all 18, and the set is identical to the
#                     set with no status.
#
# The seeding does NOT need to know what UE stands for, which is worth
# stating rather than leaving as an open worry: both non-blank codes carry
# a lease and a resident and are counted Occupied by the file's own two
# summary sections.
STATUS_MAP = {
    "C": sdb.AREA_OCCUPIED,
    "NTV": sdb.AREA_OCCUPIED,
    "UE": sdb.AREA_OCCUPIED,
}

# Blank maps to vacant on four independent lines of evidence, not on the
# summary row alone. It is a separate constant from STATUS_MAP because it
# is a separate KIND of claim: the codes above are stated by the file, and
# this one is inferred by us. The preview renders it as
# "(no status) -> vacant" for exactly that reason.
BLANK_STATUS = sdb.AREA_VACANT

UNMAPPED_STATUS_MESSAGE = (
    "status {code!r} is not one this import recognises, and it is not "
    "counted as occupied or vacant anywhere in the file"
)


class StatusReading(NamedTuple):
    stated: str | None      # exactly what the file said, or None
    mapped: str | None      # an AREA_STATUSES value, or None if unmapped
    inferred: bool          # True when we concluded it rather than read it


def read_status(stated: Any) -> StatusReading:
    """What the file said, what it becomes, and whether we inferred it.

    The three are returned together so a caller cannot render the
    conclusion without the evidence -- the same shape `site_dd_costs
    .describe()` uses to stop a figure being shown without its provenance.
    """
    code = str(stated or "").strip()
    if not code:
        return StatusReading(stated=None, mapped=BLANK_STATUS, inferred=True)
    mapped = STATUS_MAP.get(code.upper())
    return StatusReading(stated=code, mapped=mapped, inferred=False)


# ── Rooms ────────────────────────────────────────────────────────────────

HALF_BATH_LABEL = "Half bath"


class RoomSpec(NamedTuple):
    room_type: str
    label: str | None


def rooms_for(beds: int, baths: float) -> list[RoomSpec]:
    """The rooms to walk in one unit, in walk order.

    living, kitchen, N bedrooms, ceil(baths) bathrooms.

    CEIL, NOT ROUND. 1.5 baths is two rooms an inspector walks into -- a
    full one and a half one -- not one and a half rooms. Rounding would
    make a 1.5 into a single bathroom and lose the half entirely.

    The half bath is distinguished by LABEL, not by a new room type.
    `create_room` already takes a label, so Site DD gains no `half_bath`
    room type, no schema change, and no new value for anything that
    switches on room_type. Michelle declined a wider status vocabulary in
    Part 58 and the same restraint applies here: the checklist's five room
    types are enough if the label carries the distinction.
    """
    rooms = [RoomSpec("living", None), RoomSpec("kitchen", None)]
    rooms += [RoomSpec("bedroom", None) for _ in range(max(0, int(beds)))]
    full = int(baths)
    total_baths = math.ceil(baths)
    rooms += [RoomSpec("bathroom", None) for _ in range(full)]
    if total_baths > full:
        rooms.append(RoomSpec("bathroom", HALF_BATH_LABEL))
    return rooms


class Layout(NamedTuple):
    """One distinct set of rooms, shared by every unit that has it.

    Oxford Pointe's 18 type strings collapse to SIX layouts once finish
    and amenity text is set aside -- '2/1.5 RENOVATED', '2/1.5 RENOVATED
    W/D', '2/1.5 CLASSIC' and '2/1.5 PREMIUM' are all 2 bed / 1.5 bath.
    One of the six covers 77 of the 152 units.

    That is what makes copy_layout worth using: six room sets are built
    and copied, not 152 constructed independently.
    """

    beds: int
    baths: float
    rooms: tuple[RoomSpec, ...]

    @property
    def key(self) -> tuple[int, float]:
        return (self.beds, self.baths)

    @property
    def name(self) -> str:
        return f"{self.beds} bed / {self.baths:g} bath"


class PlannedUnit(NamedTuple):
    key: str                    # what an area is matched on
    label: str                  # exactly as the file wrote it
    unit_type: str | None
    sqft: float | None
    layout: Layout
    status: StatusReading
    notes: tuple[str, ...]      # facts the status collapse would lose


# What the collapse to occupied/vacant discards, kept as words rather than
# thrown away. Part 4's answer to "a real fact with nowhere structured to
# live" was the area's notes field, and it applies unchanged.
#
# NTV's move-out date is the most useful fact in the file for scheduling a
# walk: a unit that empties on a known date is one you inspect after that
# date, and that is the difference between one visit and two.
def _notes_for(unit: dict[str, Any], status: StatusReading) -> tuple[str, ...]:
    notes: list[str] = []
    if (status.stated or "").upper() == "NTV" and unit.get("move_out"):
        notes.append(f"Notice to vacate {unit['move_out']}")
    elif status.stated and status.stated.upper() not in ("C",):
        notes.append(f"Rent roll status: {status.stated}")
    return tuple(notes)


def plan_units(units: list[dict[str, Any]]) -> dict[str, Any]:
    """Every unit this import would seed, and every row it refuses.

    TWO ROWS CLAIMING ONE APARTMENT REFUSES BOTH.

    Not "keep the first", not "append a discriminator". Two rows
    normalising to one key is a fact about the file that a person has to
    look at, and picking a winner silently is how one unit's findings end
    up on another unit. Both rows are named in the refusal so the person
    can see which two.

    Verified against Oxford Pointe: 152 distinct labels produce 152
    distinct keys, and none of the six bare numbers behind a `W/D` suffix
    exists as its own separate unit -- so stripping merges nothing there.
    """
    planned: list[PlannedUnit] = []
    refusals: list[Refusal] = []
    layouts: dict[tuple[int, float], Layout] = {}
    by_key: dict[str, list[str]] = {}

    for unit in units or []:
        label = str(unit.get("unit") or "").strip()
        key = unit_key(label)
        if key is None:
            refusals.append(Refusal(label or "(blank)", _refusal_reason(label)))
            continue
        layout_parts = parse_unit_type(unit.get("unit_type"))
        if layout_parts is None:
            refusals.append(Refusal(
                label,
                f"type {str(unit.get('unit_type') or '')!r} does not state "
                f"a number of bedrooms and bathrooms"))
            continue
        status = read_status(unit.get("status"))
        if status.mapped is None:
            refusals.append(Refusal(
                label, UNMAPPED_STATUS_MESSAGE.format(code=status.stated)))
            continue
        layout = layouts.get((layout_parts.beds, layout_parts.baths))
        if layout is None:
            layout = Layout(beds=layout_parts.beds, baths=layout_parts.baths,
                            rooms=tuple(rooms_for(layout_parts.beds,
                                                  layout_parts.baths)))
            layouts[layout.key] = layout
        by_key.setdefault(key, []).append(label)
        planned.append(PlannedUnit(
            key=key, label=label, unit_type=unit.get("unit_type"),
            sqft=unit.get("sqft"), layout=layout, status=status,
            notes=_notes_for(unit, status)))

    # The collision pass runs last, so both sides of a clash are known and
    # both can be named. A unit removed here is removed from the plan --
    # refusing one half and seeding the other would be the silent winner
    # this rule exists to prevent.
    collided = {k for k, labels in by_key.items() if len(labels) > 1}
    if collided:
        for key in sorted(collided):
            labels = by_key[key]
            for label in labels:
                others = [l for l in labels if l != label]
                refusals.append(Refusal(
                    label,
                    f"normalises to unit {key!r}, and so does "
                    f"{', '.join(repr(o) for o in others)} -- the file "
                    f"gives one apartment two rows and this import will "
                    f"not choose between them"))
        planned = [p for p in planned if p.key not in collided]

    ordered = sorted(layouts.values(), key=lambda l: l.key)
    counts = {l.key: sum(1 for p in planned if p.layout.key == l.key)
              for l in ordered}
    return {
        "units": planned,
        "refusals": refusals,
        "layouts": ordered,
        "layout_counts": counts,
        "unit_count": len(planned),
        "refusal_count": len(refusals),
        "room_total": sum(len(p.layout.rooms) for p in planned),
    }


# ── Reconcile: what a seed would do to an assessment that already exists ──

class AreaPlan(NamedTuple):
    """One unit's outcome, if the seed were applied."""

    unit: PlannedUnit
    existing_area_id: int | None
    action: str                      # "create" | "reuse"
    rooms_existing: int
    rooms_appended: int
    rooms_surplus: int               # kept, never deleted
    findings_preserved: int


class Untouched(NamedTuple):
    """An existing area the rent roll says nothing about."""

    area_id: int
    label: str
    findings: int


def plan_reconcile(plan: dict[str, Any],
                   areas: list[dict[str, Any]],
                   rooms_by_area: dict[int, list[dict[str, Any]]],
                   findings_by_area: dict[int, int]) -> dict[str, Any]:
    """What seeding would do, WITHOUT DOING IT.

    THE ASYMMETRY IS THE WHOLE RULE.

    Per `(area_id, room_type)`: reuse what exists, append only the
    shortfall, **never delete a surplus, never touch a finding.** A rent
    roll can tell us a room is missing. It cannot tell us that a room an
    inspector recorded does not exist -- the roll is a document about the
    building, not an authority over it.

    The same asymmetry applies one level up: an existing area with no
    matching row in the roll is left alone. A unit missing from a newer
    rent roll is not evidence the apartment stopped existing, and an
    inspector may have added it deliberately.

    Nothing here opens a connection. The caller reads, this decides, and
    a later run writes.
    """
    by_key: dict[str, dict[str, Any]] = {}
    for area in areas or []:
        key = unit_key(area.get("label"))
        if key is not None:
            by_key.setdefault(key, area)

    area_plans: list[AreaPlan] = []
    matched_ids: set[int] = set()
    for unit in plan["units"]:
        existing = by_key.get(unit.key)
        if existing is None:
            area_plans.append(AreaPlan(
                unit=unit, existing_area_id=None, action="create",
                rooms_existing=0, rooms_appended=len(unit.layout.rooms),
                rooms_surplus=0, findings_preserved=0))
            continue
        area_id = existing["id"]
        matched_ids.add(area_id)
        have: dict[str, int] = {}
        for room in rooms_by_area.get(area_id, []):
            have[room["room_type"]] = have.get(room["room_type"], 0) + 1
        want: dict[str, int] = {}
        for room in unit.layout.rooms:
            want[room.room_type] = want.get(room.room_type, 0) + 1
        appended = sum(max(0, want.get(t, 0) - have.get(t, 0))
                       for t in set(want) | set(have))
        surplus = sum(max(0, have.get(t, 0) - want.get(t, 0))
                      for t in set(want) | set(have))
        area_plans.append(AreaPlan(
            unit=unit, existing_area_id=area_id, action="reuse",
            rooms_existing=sum(have.values()), rooms_appended=appended,
            rooms_surplus=surplus,
            findings_preserved=findings_by_area.get(area_id, 0)))

    untouched = [Untouched(area_id=a["id"], label=a.get("label") or "",
                           findings=findings_by_area.get(a["id"], 0))
                 for a in areas or [] if a["id"] not in matched_ids]

    return {
        "areas": area_plans,
        "untouched": untouched,
        "create_count": sum(1 for a in area_plans if a.action == "create"),
        "reuse_count": sum(1 for a in area_plans if a.action == "reuse"),
        "rooms_appended": sum(a.rooms_appended for a in area_plans),
        "rooms_surplus_kept": sum(a.rooms_surplus for a in area_plans),
        # Stated as a number so the preview can say it in words rather
        # than implying it by silence.
        "findings_preserved": sum(a.findings_preserved for a in area_plans)
                              + sum(u.findings for u in untouched),
    }

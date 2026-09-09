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

from tools import investor_notes_match as matching
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

# ── Appfolio: the same two answers, arrived at the opposite way ──────────
#
# THE INVERSION IS THE WHOLE POINT OF THIS BLOCK. ResMan states occupancy
# and leaves vacancy blank, so we INFER it -- see BLANK_STATUS above, and
# the note that inference earns. Appfolio STATES vacancy outright and has
# no blank at all: every one of the 16 rows in the only Appfolio file we
# hold carries a word.
#
# So a vacant Appfolio unit is READ, not concluded, and the Part 100 note
# "Vacant inferred: the rent roll gave no status..." must never appear on
# one. Writing it there would be a false statement about provenance on
# real client data, and Michelle is walking assessment 22 now.
#
# NOTICE-UNRENTED IS OCCUPIED, AND THAT IS THE FILE'S ARITHMETIC RATHER
# THAN THE OBVIOUS READING. Jackson's own footer says 93.8% occupied of
# 16 units; 93.8% of 16 is 15, and the file holds 14 Current + 1
# Notice-Unrented + 1 Vacant-Unrented. So Appfolio counts a resident on
# notice as in place -- which agrees with the reading a person would give
# it, and matters because it was established the same way the ResMan map
# was: from the document, not from plausibility.
APPFOLIO_STATUS_MAP = {
    "CURRENT": sdb.AREA_OCCUPIED,
    "NOTICE-UNRENTED": sdb.AREA_OCCUPIED,
    "VACANT-UNRENTED": sdb.AREA_VACANT,
}

# No blank status exists in the Appfolio file we hold, so there is no
# evidence for what one would mean. It is refused rather than defaulted:
# inventing a rule here is exactly the guess the ResMan blank rule earned
# through four independent signals and this one has not.
APPFOLIO_BLANK_MESSAGE = (
    "this Appfolio rent roll left the status blank, and unlike a ResMan "
    "export there is no established meaning for that"
)

UNMAPPED_STATUS_MESSAGE = (
    "status {code!r} is not one this import recognises, and it is not "
    "counted as occupied or vacant anywhere in the file"
)


class StatusReading(NamedTuple):
    stated: str | None      # exactly what the file said, or None
    mapped: str | None      # an AREA_STATUSES value, or None if unmapped
    inferred: bool          # True when we concluded it rather than read it


def read_status(stated: Any, dialect: str | None = None) -> StatusReading:
    """What the file said, what it becomes, and whether we inferred it.

    The three are returned together so a caller cannot render the
    conclusion without the evidence -- the same shape `site_dd_costs
    .describe()` uses to stop a figure being shown without its provenance.

    THE DIALECT DECIDES, BECAUSE THE VOCABULARIES INVERT. ResMan infers
    vacancy from a blank; Appfolio states it and never leaves it blank.
    A shared "was the cell empty" test would mark an Appfolio vacancy as
    inferred, which is false, and would attach a note saying the file gave
    no status to a row where it plainly did.

    Defaults to ResMan so every existing caller and test is unchanged --
    the dialect travels on the unit dict, set by the parser that read it.
    """
    code = str(stated or "").strip()
    if dialect == "appfolio":
        if not code:
            return StatusReading(stated=None, mapped=None, inferred=False)
        return StatusReading(stated=code,
                             mapped=APPFOLIO_STATUS_MAP.get(code.upper()),
                             inferred=False)
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
# AND AN INFERENCE IS A FACT ABOUT THE IMPORT, SO IT IS WRITTEN DOWN TOO.
#
# `vacant` and `vacant` are the same two bytes whether the file said so or
# we concluded it, and the file is not kept -- the preview holds it
# between preview and apply and deletes it either way. So the moment the
# seed commits, a stated vacancy and an inferred one are
# indistinguishable forever, and the screen that showed the reasoning
# ("(no status) -> vacant") is gone.
#
# The evidence is strong: on Oxford Pointe the eighteen units with no
# status are exactly the eighteen with no lease start, no lease end, no
# move-in and no in-place rent, and two independent summary sections
# agree. That is why this is a NOTE and not a column -- a `status_source`
# would need a vocabulary on the area card, the Lite filter, the label
# maps and both exports, to hedge a conclusion nobody has reason to
# doubt.
#
# What the note buys is the next rent roll. If some later export's blanks
# mean something else -- a different system, a partial file, a column
# that moved -- these sentences are the only place anybody would ever
# notice that a judgement had been made.
#
# IT READS AS A FACT ABOUT THE IMPORT, not about the apartment. "This
# unit is vacant" is a claim about the world that nobody here is entitled
# to make; "the rent roll gave no status" is what actually happened.
# The status codes that mean "occupied, nothing else to say", per dialect.
# A note on every occupied unit is noise, which is why ResMan's "C" was
# excluded from the start; "Current" is the same word in the other dialect.
_UNREMARKABLE_STATUS = {
    None: ("C",),
    "appfolio": ("CURRENT",),
}

# The codes that mean "occupied today, leaving on a known date". Both
# dialects have one, and both earn the same note when a move-out is on
# the row -- the date is the useful part, not the code.
_NOTICE_STATUS = {
    None: ("NTV",),
    "appfolio": ("NOTICE-UNRENTED",),
}


# ── Bed-level facts, for a file that states them ─────────────────────────
#
# WHAT THIS IS FOR. A by-the-bed rent roll carries one row per BED. The
# decision in docs/site-dd-per-bed-occupancy.md is that a 4x4 building
# becomes ONE AREA PER APARTMENT -- 84, not 336 -- because 336 areas would
# invent 252 kitchens that do not exist, and the file's own "4x4" says the
# apartment is the unit and the bed is a leasing subdivision of it.
#
# The cost of that decision is exact: an apartment's single `status` has
# to stand for four beds, and at The View 34 of 84 apartments hold beds in
# more than one state. THIS IS WHERE THOSE FOUR FACTS GO -- the same
# answer §1.3 of the seeding design gave for NTV and UE, which is that a
# real fact with nowhere structured to live goes in the notes.
#
# ── LIMIT 1: THIS DOES NOT MAKE THE WALK RIGHT ──────────────────────────
#
# It must not be read as fixing per-bed occupancy, and it does not fix one
# bed of it. `site_dd._lite_area()` selects the walk from the AREA's
# status, so an apartment with one occupant and three empty beds reads
# `occupied` and Lite does not offer it. Measured on the real file rather
# than argued: 53 of The View's 85 vacant beds -- 62% of the building's
# turnable inventory -- sit in apartments Lite would hide, and 42 more
# apartments are genuinely full. A per-unit Lite offers an inspector 8 of
# 84 apartments.
#
# A NOTE CANNOT BE FILTERED, COUNTED OR SELECTED ON. Only a status on
# `site_dd_rooms` can change which spaces an inspector is sent to, and
# that is a column plus a write path that does not exist -- rooms have no
# update function at all -- and it is downstream of the by-unit/by-bed
# flag, which has no home until there is a properties table.
#
# So this preserves the fact and leaves the walk exactly as wrong as it
# was. That is worth having and it is not the fix.
#
# ── LIMIT 2: EVERY LINE IS A CLAIM ABOUT A DOCUMENT, NOT ABOUT A ROOM ───
#
# "Rent roll lists bed A as Vacant Unrented Not Ready" and "bed A is not
# ready" are different sentences, and only the first is ours to write.
#
# The second is the property manager's judgement of READINESS -- which is
# precisely the question a site DD exists to answer independently. An
# inspector is sent to that bed to decide whether it is ready; importing
# the answer would seed the conclusion they are there to reach. This is
# the same reasoning as the Part 88 inference note, which says the rent
# roll gave no status rather than that the unit is empty, and the same
# reason Michelle's Part 58 decline of the ready/not-ready axis survives
# per-bed rather than being reopened by it: we are not short a status,
# we are recording somebody else's opinion as an opinion.
#
# ── SHAPE: ONE SENTENCE PER REMARKABLE BED ──────────────────────────────
#
# Not four-lines-always and not one packed sentence, and the deciding
# reasons are about the two surfaces this lands on rather than taste:
#
#   * `templates/tools/site_dd_area.html:251` renders the stored note into
#     a single-line `<input type="text">`, and `site_dd.save_area` writes
#     `notes` UNCONDITIONALLY on every post -- so whatever that field
#     posts back replaces the stored note entirely. The write half is
#     demonstrated in tests/test_sitedd_bed_note.py; the browser half --
#     that a text input's value sanitization strips CR/LF, so the lines
#     would come back welded together -- is READ FROM THE HTML SPEC AND
#     NOT OBSERVED HERE, because nothing in this repo drives a browser.
#     Stated as a spec claim rather than a measurement on purpose. Either
#     way the conclusion is the same and only needs the tested half: a
#     multi-line note does not survive somebody opening that unit and
#     saving it. `_insert_area` joins this tuple with "; " into one line,
#     and that join is why it survives.
#   * `templates/tools/site_dd_seed_preview.html:229` iterates the tuple
#     and renders each element as its own quoted note. So on the approval
#     screen -- the one place a person reads these before committing --
#     the facts are already separate. Packing them into one sentence
#     ("beds A,D vacant; B,C occupied") would put structured data in a
#     text column, which is the shape §3C of the per-bed design rejected
#     when the SOURCE FILE did it in `resident_name`.
#
# Each element is therefore a complete sentence that stands alone, because
# it may be read alone.
#
# A dialect absent from the map below has NO unremarkable bed state, so
# every bed gets a sentence. That is the safe direction: a note that says
# too much is read past, and one that silently omits a vacant bed is the
# failure this whole mechanism exists to prevent.
_UNREMARKABLE_BED_STATUS = {
    "entrata": ("OCCUPIED NO NOTICE",),
}


def _bed_notes(unit: dict[str, Any]) -> tuple[str, ...]:
    """One sentence per bed whose state is worth a walker's attention.

    Expects `unit["beds"]` as a sequence of mappings carrying `label` and
    `status` exactly as the FILE stated them -- no mapping, no collapse,
    no title-casing. The three-way vacant vocabulary (Rented Ready /
    Unrented Ready / Unrented Not Ready) survives here precisely because
    nothing normalises it on the way in; the apartment's own status is
    where the collapse happens, and this is the record of what was
    collapsed.

    NOTHING PRODUCES `unit["beds"]` TODAY. There is no Entrata parser --
    dispatch refuses the file by name, `parse_unit_type("4x4 (Regular)")`
    returns None, and `unit_key("111-A")` returns None -- so this function
    is reachable only from its own tests. It is written now because the
    shape was designed against the real file while that file was in hand,
    and the wording is the part that would be got wrong later.

    A bed the file lists with no status is recorded as exactly that. It is
    NOT inferred vacant: the ResMan blank rule was earned on four
    independent signals for a whole unit, and none of them has been shown
    to hold for a bed. Whether such a row should be refused outright is
    the PARSER's decision and belongs there -- see the odd-bed-count
    refusal in the per-bed design, which this function deliberately does
    not attempt.
    """
    beds = unit.get("beds") or ()
    unremarkable = _UNREMARKABLE_BED_STATUS.get(unit.get("dialect"), ())
    notes: list[str] = []
    for bed in beds:
        label = str(bed.get("label") or "").strip()
        if not label:
            continue
        stated = str(bed.get("status") or "").strip()
        if not stated:
            notes.append(f"Rent roll lists bed {label} with no status")
        elif stated.upper() not in unremarkable:
            notes.append(f"Rent roll lists bed {label} as {stated}")
    return tuple(notes)


def _notes_for(unit: dict[str, Any], status: StatusReading) -> tuple[str, ...]:
    """Facts the status collapse to occupied/vacant would otherwise lose.

    THE INFERENCE NOTE IS RESMAN-ONLY, and that is not an accident of
    control flow -- `status.inferred` is never True for an Appfolio row
    because that dialect states its vacancies. Writing "the rent roll gave
    no status" onto a row whose status column reads `Vacant-Unrented`
    would be a false statement about where the conclusion came from.

    THE BED SENTENCES ARE ADDITIVE AND CANNOT REACH A LIVE PATH. They
    append only when the unit dict carries `beds`, which no parser sets,
    so both shipped dialects return byte-identical notes to what they
    returned before this branch existed. That is asserted on the real
    ResMan and Appfolio files through the real upload route, not reasoned
    about, because those two are live and Michelle uses them.
    """
    dialect = unit.get("dialect")
    code = (status.stated or "").upper()
    notes: list[str] = []
    if code in _NOTICE_STATUS.get(dialect, ()) and unit.get("move_out"):
        notes.append(f"Notice to vacate {unit['move_out']}")
    elif status.stated and code not in _UNREMARKABLE_STATUS.get(dialect, ()):
        notes.append(f"Rent roll status: {status.stated}")
    elif status.inferred:
        notes.append("Vacant inferred: the rent roll gave no status, and "
                     "no lease, move-in or rent.")
    notes.extend(_bed_notes(unit))
    return tuple(notes)


# ── Does the file say it is for this building? ───────────────────────────
#
# INFORMATION AT THE POINT OF APPROVAL, NOT A GATE. A mismatch is never
# refused: names legitimately differ, an assessment may be labelled with
# an abbreviation or a deal code, and refusing would invent a rule
# Michelle has not asked for. The screen shows both names and says which
# way it reads them.
#
# CONSERVATIVE IN ONE DIRECTION ON PURPOSE. A false "these disagree" costs
# a person two seconds of reading two names. A false "these agree" is the
# entire failure this exists to prevent -- it would put a reassurance on
# screen exactly when somebody is about to seed a building from the wrong
# file. So AGREEMENT IS ASSERTED ONLY ON EVIDENCE, and anything else is
# either a stated disagreement or no verdict at all.

MATCH_YES = "match"          # the same building, on evidence
MATCH_NO = "differ"          # both named, and nothing connects them
MATCH_UNKNOWN = "unknown"    # not enough to say -- show both, judge nothing


class PropertyNameCheck(NamedTuple):
    file_name: str | None       # what the rent roll calls itself
    assessment_name: str | None # what this assessment is called
    verdict: str
    reason: str


def _tokens(text: Any) -> list[str]:
    return matching.normalize(str(text or "")).split()


def _contains_tokens(longer: list[str], shorter: list[str]) -> bool:
    """Whole-token containment, in order.

    Token-wise rather than substring so "Pointe" cannot match inside
    another word, and ordered so "Eagle Rock" does not match "Rock Eagle".
    """
    if not shorter or len(shorter) > len(longer):
        return False
    for i in range(len(longer) - len(shorter) + 1):
        if longer[i:i + len(shorter)] == shorter:
            return True
    return False


def _abbreviation_pairs() -> dict[str, str]:
    """The full-name/abbreviation pairings this platform already knows.

    Reused rather than restated: the Weekly Property Summary has needed
    "oxford pointe" -> "OXPT" since long before this check existed, and a
    second copy would be a second thing to update.
    """
    from tools.mmr_report.builders import _PROPERTY_ABBREVS
    return dict(_PROPERTY_ABBREVS)


def compare_property_name(file_name: Any, assessment_name: Any) -> PropertyNameCheck:
    """Whether the rent roll and the assessment name the same building.

    "Oxford Pointe Apartments" against "OXPT" is a match a person makes
    instantly and a string comparison does not, which is why the
    abbreviation table is consulted rather than trusting equality.
    """
    file_text = str(file_name or "").strip() or None
    assessment_text = str(assessment_name or "").strip() or None

    if file_text is None:
        return PropertyNameCheck(None, assessment_text, MATCH_UNKNOWN,
                                 "this file does not name a property")
    if assessment_text is None:
        return PropertyNameCheck(file_text, None, MATCH_UNKNOWN,
                                 "this assessment has no property name to compare")

    a, b = _tokens(file_text), _tokens(assessment_text)
    if not a or not b:
        return PropertyNameCheck(file_text, assessment_text, MATCH_UNKNOWN,
                                 "one of the names has nothing to compare")
    if a == b:
        return PropertyNameCheck(file_text, assessment_text, MATCH_YES,
                                 "the names are the same")

    longer, shorter = (a, b) if len(a) >= len(b) else (b, a)
    # A very short name matching inside a longer one is not evidence -- it
    # is a coincidence waiting to happen, and a coincidence that says
    # "agree" is the failure mode this function is shaped around.
    if len(" ".join(shorter)) >= 4 and _contains_tokens(longer, shorter):
        return PropertyNameCheck(file_text, assessment_text, MATCH_YES,
                                 "one name contains the other")

    for full, abbrev in _abbreviation_pairs().items():
        full_tokens, abbrev_tokens = _tokens(full), _tokens(abbrev)
        for name_a, name_b in ((a, b), (b, a)):
            if (_contains_tokens(name_a, full_tokens)
                    and _contains_tokens(name_b, abbrev_tokens)):
                return PropertyNameCheck(
                    file_text, assessment_text, MATCH_YES,
                    f"{abbrev} is this platform's abbreviation for {full.title()}")

    return PropertyNameCheck(file_text, assessment_text, MATCH_NO,
                             "nothing connects these two names")


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
        status = read_status(unit.get("status"), unit.get("dialect"))
        if status.mapped is None:
            reason = (APPFOLIO_BLANK_MESSAGE
                      if status.stated is None
                      else UNMAPPED_STATUS_MESSAGE.format(code=status.stated))
            refusals.append(Refusal(label, reason))
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

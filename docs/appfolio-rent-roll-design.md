# Appfolio rent rolls: dispatch and a second parser

**Design only. Nothing here is built.** Written 2026-09-07 while the
ResMan work is fresh, against the real file rather than against notes.

**The file this was checked against:** `Jackson 0816 RR test.xlsx`,
exported 2026-08-16, property *1120 Jackson Street*. Every claim below
was re-read from it today; nothing is carried forward from an earlier
session's description.

---

## 1. Why an Appfolio roll is refused today

`tools/underwriting_rentroll.py` finds its header by requiring **three
things at once**: a `Unit` column, a `Market Rent` column, and the
`Description`/`Amount` charge-line pair. That triple is not arbitrary —
it is what distinguishes a rent roll from the MMR workbook, which also
carries `Unit` and `Market Rent`, and `Description`/`Amount` is where
in-place rent is actually summed from.

**An Appfolio roll has none of the three.** Its header is:

    Unit | BD/BA | Tenant | Status | Sqft | Rent | Deposit | Move-in | Move-out | Past Due

`Unit` matches by name; `Market Rent` does not exist (there is a single
`Rent`); and there are no charge lines at all. So `parse_rent_roll_workbook`
raises `UnrecognizedRentRoll` before reading a row — **correctly**, on the
information it has. Site DD's seeding calls that parser, so it inherits the
refusal.

## 2. What the Appfolio file actually looks like

**Confirmed against the file, 2026-09-07.** Sixteen units.

| claim | confirmed |
|---|---|
| one row per unit, no charge lines | **yes** — 16 data rows for 16 units |
| unit type is numeric, not prose | **yes** — every row is exactly `1/1.00` |
| status is stated, never blank | **yes** — `Current` ×14, `Vacant-Unrented` ×1, `Notice-Unrented` ×1 |
| sqft empty on this file | **yes** — empty on all 16, where Oxford Pointe's is populated |
| unit labels are not contiguous | **yes** — 1–12 and 14–17; **unit 13 is the gap** |

**Structure beyond the five claims**, which the dispatch has to survive:

* an **eight-row preamble** before the header — `Rent Roll`,
  `Exported On:`, `Properties:`, `Units: Active`, `As of:`,
  `Include Non-Revenue…`, `Include Advertised R…`. The header is row 10.
* a **property banner row** under the header: `1120 Jackson Street - 1120
  Jackson`, with every other cell empty.
* **two footer rows**: `16 Units … 93.8% Occupied` and
  `Total 16 Units … 93.8% Occupied`. Both must be excluded, and both are
  distinguishable by having no `BD/BA`.
* `Rent` and `Move-in` are each empty on exactly **one** row — the vacant
  one. Not a parse problem; a fact the preview should show rather than
  fill in.

> **93.8% is 15 of 16, so Appfolio counts `Notice-Unrented` as OCCUPIED.**
> That is the file arithmetic agreeing with the obvious reading — a
> resident on notice is still in the unit — and it is the same call ResMan's
> `NTV` gets. Worth having from the file rather than from plausibility,
> because the whole ResMan status map was established that way.

## 3. Detection, and what happens when it is ambiguous

**Dispatch on the header row, not on the filename and not on the
preamble.** Both dialects are `.xlsx` workbooks whose first rows are
title text, and neither says its own vendor anywhere a parser should
trust.

    ResMan   header carries Unit AND Market Rent AND Description/Amount
    Appfolio header carries Unit AND BD/BA AND Status
                            and NO Market Rent and NO Description/Amount

**The two signatures are disjoint on three columns each**, which is what
makes this a dispatch rather than a guess.

> **REFUSE ON AMBIGUITY, AND REFUSE BY NAME.** If a sheet matches both
> signatures, or neither, the answer is `UnrecognizedRentRoll` with the
> columns it did find listed. **Guessing wrong here seeds 152 units from a
> misunderstanding**, and the undo for that is a `seed_batch` rollback
> that only works while nobody has walked the units — which is exactly the
> window an import is followed by.

**The message should name what was missing**, in the existing style: the
current one already tells the reader which three columns a ResMan roll
needs, and the Appfolio branch should do the same rather than saying
"unrecognised".

## 4. What the seeding path has to be told

**The status mapping inverts, and this is the part that will bite.**

    ResMan     stated code -> occupied ; BLANK -> vacant (INFERRED by us)
    Appfolio   stated word -> occupied or vacant ; BLANK -> nothing seen

| Appfolio status | maps to | stated or inferred |
|---|---|---|
| `Current` | occupied | **stated** |
| `Notice-Unrented` | occupied | **stated** — file counts it occupied |
| `Vacant-Unrented` | vacant | **stated** |
| blank | — | **does not occur in this file; refuse rather than infer** |

**The Part 100 inference note must not fire on Appfolio rows.**
`_notes_for()` writes *"Vacant inferred: the rent roll gave no status, and
no lease, move-in or rent"* — and `BLANK_STATUS = AREA_VACANT` exists
because eighteen ResMan rows were blank on four independent signals at
once. **Both of those are ResMan facts.** An Appfolio roll states
vacancy outright, so a vacant unit there is *read*, not *concluded*, and
labelling it inferred would be a false note on real client data.

> So `StatusReading.inferred` has to be set by the **dialect's** rule, not
> by a shared "was the cell blank" test. The cleanest shape is that each
> parser returns its own `read_status`, and the seeding takes the reading
> rather than re-deriving it. That is a change to who decides, not a new
> column — and the Part 88 decision that this is a note and not a
> `status_source` column still holds.

**What blank should do on Appfolio is a refusal, not a default.** No blank
row exists in the file we have, so any rule for it would be invented.

## 5. Bed and bath: no new code, and a real limit

**`parse_unit_type` already handles the Appfolio form unchanged.**
Verified today:

    parse_unit_type("1/1.00")               -> beds=1 baths=1.0 full=1 half=0
    parse_unit_type("2/1.5 RENOVATED W/D")  -> beds=2 baths=1.5 full=1 half=1

The regex is `^\s*(\d+)\s*[/ ]\s*(\d+(?:\.\d+)?)`, which is dialect-agnostic
by accident rather than by design — it takes a leading `N/M` and ignores
whatever follows. **So there is no Appfolio bed/bath branch to write, and
therefore no untestable branch**, which is a better answer than the one
this section was expected to give.

> **WHAT CANNOT BE VALIDATED, STATED PLAINLY.** Jackson is **entirely
> `1/1.00`** — sixteen identical strings. So while the function demonstrably
> parses that form, **nothing we hold exercises a multi-bedroom Appfolio
> unit**. If Appfolio writes 2-bed units as `2/1.00` this already works; if
> it writes them as `2 BR / 1 BA` or `2BD/1BA`, it returns `None` and
> `layouts_for_units` reports the refusal. **Which of those it does is
> unknown and should not be guessed** — the same argument that retired the
> letter-only unit rule.

**One difference worth deciding before it ships**: `0/1.00` parses to
**beds=0** rather than being refused. In ResMan a studio has no leading
pair and is refused by construction; in Appfolio's numeric form a studio
would silently seed a unit with no bedroom rooms. **That is a new
behaviour arriving through an unchanged function**, and it is the kind of
thing that looks like a parser working right up until somebody counts the
rooms.

## 6. Sqft

**Empty on all sixteen rows**, where Oxford Pointe's ResMan file populates
it. Nothing downstream requires sqft — Site DD seeding uses unit, type and
status — so this is not a blocker. It should be carried as absent rather
than as zero, which is the falsy-zero rule this repo has recorded three
times.

## 7. What is NOT designed here

* **Underwriting's unit lines.** This design is about Site DD seeding.
  Whether an Appfolio roll should also feed `underwriting_unit_lines` is a
  separate question with its own answer, and Part 83 investigated the
  ResMan side without building it.
* **Any multi-property roll.** Jackson's file has a single property
  banner. A file with two would need a rule about which units belong to
  which, and no such file exists here.
* **Which assessment a re-walk seeds into.** Still open with Michelle.

---

## The shape, in one paragraph

Add a **dialect detector** that reads the header row and returns
`resman` / `appfolio` / **refuse-with-reasons**; move the existing header
requirements behind the ResMan branch unchanged; add an Appfolio reader
that skips the preamble, takes `Unit`/`BD/BA`/`Status`, drops the banner
and the two footer rows by their empty `BD/BA`, and returns the same unit
dicts the ResMan path already returns. **Status becomes the dialect's
responsibility rather than a shared blank-test**, so the vacancy-inference
note stays a ResMan-only claim. Bed/bath needs nothing. **The single
genuinely unknown is how Appfolio writes a unit type that is not one
bedroom, and the honest position is to find that out from a file before
writing a line that depends on it.**

# Seeding Site DD units from a rent roll — design

**Design only. No build, no writes. Written 2026-08-29 against master
`dee8f27`.**

The parser half shipped in Part 68: a ResMan `.xls` is read, and each
unit's bedroom and bathroom count comes off its type string. This is the
half that writes — and it writes into a database holding Michelle's live
walk, so the shape goes in front of Jasper before any of it runs.

**Everything below is measured against the real Oxford Pointe file (152
units) unless it says otherwise.** Where a rule rests on one file, it says
so.

---

## 1. The two status questions, answered from the file

Both had to be settled before seeding could write anything.

### 1.1 The 18 blank statuses mean vacant — on five independent columns, not one summary row

The brief's evidence was the Property Occupancy total: 134 occupied / 18
vacant / 88.157%, and `132 C + 1 UE + 1 NTV = 134`. That is inference
from a summary row, and it is good but singular.

**It is not the only evidence, and the rest is stronger.** Every
tenancy-bearing column is empty on exactly those 18 units and populated on
all 134 others:

| column | present on the 18 | present on the 134 |
|---|---|---|
| `lease_start` | **0** | 134 |
| `lease_end` | **0** | 134 |
| `move_in` | **0** | 134 |
| `in_place_rent` | **0** | 133 |

**And the sets are identical**: the units with no status are exactly the
units with no lease start. A unit with no lease, no move-in and no rent is
vacant, and that is read off the tenancy columns rather than inferred from
a total.

There is also a **second summary section** — the file carries *Property
Occupancy* (r722) and *Unit Type Occupancy* (r729), the latter breaking
occupied/vacant down per unit type. Both agree.

**So: blank means vacant, established four ways.** No question for
Michelle.

### 1.2 `NTV` is confirmed. `UE` is not, and does not need to be.

**`NTV` = notice to vacate, confirmed from the row rather than the
acronym.** Unit 640: a named resident, a lease running 2025-05-01 to
2026-04-30, a move-in — and **a move-out date of 2026-08-13**, with
in-place rent at 0.0. Occupied today, leaving on a known date. It is the
only row in the file with a move-out.

**`UE` cannot be confirmed from the file and I am not going to expand it
from plausibility.** Unit 217 has a named resident, a current lease
(2026-03-09 to 2027-02-28), a move-in and $960 of in-place rent. There is
**no legend anywhere in the export** — no status-code key above the
header, in the summary sections, or in the footer. "Under eviction" is the
common ResMan reading and it fits a tenant who still has a lease and still
owes rent, but the file does not say so.

**What the file does establish is the only thing the mapping needs:**
both rows have a lease, a resident and a move-in, and both are counted
`Occupied` by the summary sections. So:

| ResMan | count | → Site DD | why |
|---|---|---|---|
| `C` | 132 | `occupied` | current |
| `NTV` | 1 | `occupied` | occupied today; leaving 2026-08-13 |
| `UE` | 1 | `occupied` | resident, lease and rent, counted occupied |
| *(blank)* | 18 | `vacant` | no lease, no move-in, no rent |

**The seeding does not need to know what `UE` stands for**, which is worth
stating plainly: resolving it would be nice and is not blocking. If a
future roll carries a code that is *not* counted occupied by the summary,
that one does block, and the preview must refuse it rather than guess.

### 1.3 What the collapse loses, and where it could go

Michelle: *"Unit status isn't important for my purpose. What is most
important is the correct unit number, unit type, occupied or vacant."*

So the collapse is what she asked for. Two facts are lost by it:

* **NTV's move-out date** — 2026-08-13 on unit 640. This is the single
  most useful fact in the file for **scheduling a walk**: a unit that
  empties on a known date is one you inspect after that date, and it is
  the difference between one visit and two.
* **UE's distinctness** — whatever it means.

**Proposal, not a build: the area's `notes` field.** Part 4's answer to
"a real fact with nowhere structured to live" was the notes field, and it
applies unchanged. Seeding would write `Notice to vacate 2026-08-13` into
the notes of unit 640's area, and `Rent roll status: UE` into 217's.
Nothing parses it back; it is there for the person planning the walk.

That keeps `AREA_STATUSES` untouched — which matters, because widening it
is the design Michelle **declined** in Part 58, and the note is how the
information survives that decision instead of being argued with.

---

## 2. `unit_key` — matching a rent-roll unit to a Site DD area

### 2.1 The amenity suffix is on the LABEL, not only the type

The Part 35 spec anticipated an amenity-suffix rule from the six `W/D`
**type** strings. The real file is more direct than that: **six of the 152
unit labels carry the suffix themselves.**

    '122 W/D'   '222 W/D'   '226 W/D'   '521 W/D'   '526 W/D'   '529 W/D'

The other 146 are plain numbers. `'226 W/D'` and `'226'` are the same
apartment written two ways, and an inspector typing the unit into Site DD
will type `226`.

**The rule:** strip a trailing amenity suffix to form the key; keep the
label exactly as the file wrote it for display.

    unit_key('226 W/D') -> '226'        area label stays '226 W/D'

**Checked against the file rather than assumed: stripping produces no
collisions.** 152 distinct labels before, 152 distinct keys after, and
**none of the six bare numbers exists as its own separate unit** — so
there is no case where stripping merges two real apartments.

### 2.2 The collision refusal

That is one file. The rule must fail loudly when it is wrong:

> **If two rent-roll rows normalise to the same key, seed nothing and name
> both rows.** Not "keep the first", not "append a discriminator". Two
> rows claiming one apartment is a fact about the file that a person has
> to look at, and picking one silently is how a unit's findings end up on
> the wrong apartment.

### 2.3 The letter-only discriminator, and its threshold is still a guess

Some properties label units `A1`, `B2` by building. The Part 35 spec
detects this with a **60% threshold** — if more than 60% of labels start
with a letter, treat the letter as a building discriminator rather than
part of the unit number.

**That threshold is a guess from one file and this file does not test
it.** Oxford Pointe's labels are numeric; not one starts with a letter.
So the second lettered rent roll HANDOFF has been waiting for has still
not arrived, and the threshold remains exactly as provisional as it was.

**Recommendation: do not build the letter rule in the seeding run.**
Refuse a lettered roll with a named message and ship the numeric case,
which is the case we can test. A threshold nobody can exercise is a branch
that will be wrong in a way nobody notices — this file's own
`3/2 RENOVATED  down` is the reminder that the awkward row is the one a
sample drops.

---

## 3. Rooms

### 3.1 Derivation

Per unit, in walk order: **living, kitchen, N bedrooms, ceil(baths)
bathrooms.** `ceil` because 1.5 baths is two rooms to walk — one full and
one half — not one and a half rooms.

The half bath is distinguished by **label**, not by a new room type:
`create_room(conn, area_id, "bathroom", "Half bath")`. Site DD gains no
`half_bath` room type and no schema change, which is the Part 68 spec's
answer and still holds.

For Oxford Pointe that is:

| layout | units | rooms each | bathrooms |
|---|---|---|---|
| 1 / 1.0 | 25 | 4 | 1 |
| 2 / 1.0 | 1 | 5 | 1 |
| **2 / 1.5** | **77** | **6** | 2 (one labelled *Half bath*) |
| 2 / 2.0 | 16 | 6 | 2 |
| 3 / 1.5 | 1 | 7 | 2 (one labelled *Half bath*) |
| 3 / 2.0 | 32 | 7 | 2 |

**~880 rooms across 152 units.** That number is worth seeing before it is
written.

### 3.2 `copy_layout` for identical units

**Six distinct layouts across 152 units, and one of them is 77 units.**
The 18 distinct *type strings* collapse to 6 layouts once finish and
amenity text is set aside — `'2/1.5 RENOVATED'`, `'2/1.5 RENOVATED W/D'`,
`'2/1.5 CLASSIC'` and `'2/1.5 PREMIUM'` are all 2 bed / 1.5 bath.

So: build the room set once per layout, then `copy_layout` it. That is 6
constructions instead of 152.

**`copy_layout` is already safe for this and it was checked, not assumed.**
It copies *"only room_type, label and sort_order"* — an explicit column
list — so occupancy, notes and findings do not travel with a layout. The
per-bed design already flagged that this safety is an enumeration somebody
could later "tidy" into `SELECT *`, and it wants a test asserting a copied
room comes back with no status. That test belongs in the seeding run.

### 3.3 The room-collision rule — reuse, append, never delete

Re-uploading a rent roll for a property that has already been walked is
the case that can destroy work. The Part 31 rule, unchanged:

> **Per `(area_id, room_type)`: reuse the rooms that exist, append only
> the shortfall, never delete a surplus, and never touch a finding.**

Worked through on the live case. **Assessment 11 has one kitchen carrying
15 findings.** If a rent roll said that unit needs one kitchen:

* reuse the existing kitchen — the 15 findings stay attached to the same
  `room_id`;
* append nothing;
* delete nothing.

If the roll implied *two* bedrooms and one exists, append one. If it
implied *one* bedroom and three exist, **leave all three** — the extra two
are somebody's observation of the actual apartment, and the rent roll is a
document about it, not an authority over it.

**The asymmetry is the point.** A rent roll can tell us a room is missing.
It cannot tell us a room an inspector recorded does not exist.

---

## 4. Idempotence

**A second upload of the same file must produce the same areas, not 152
more.** This is the requirement that makes the run expensive, and it falls
out of §2 if `unit_key` is honest:

1. Read the rent roll; compute a `unit_key` per row.
2. Load the assessment's existing areas; compute the same key from each
   area's label.
3. **Match on the key.** Existing → update in place. Absent → create.
4. **An area with no matching row is left alone**, exactly as a surplus
   room is. A unit missing from a newer rent roll is not evidence the
   apartment stopped existing, and an inspector may have added it
   deliberately.

Re-uploading therefore converges: same keys, same areas, rooms reconciled
per §3.3, findings untouched throughout.

**What "update in place" may change is narrow, and should be argued
rather than assumed**: unit type, square footage and status are facts the
rent roll owns. **Notes are not** — an inspector's note must not be
overwritten by a re-import, which is the same absent-means-unchanged rule
this codebase has now applied four times. The §1.3 status note would need
to append rather than replace, or to live on its own line.

---

## 5. The preview screen

**Nothing writes until Michelle has seen what will be written.** With 152
units this is a real screen rather than a confirmation dialog — the Part
31 design was drafted against a 16-unit file and could treat it as a
formality.

The preview shows, before any write:

* **Every unit**, with its label, `unit_key` if it differs, layout, square
  footage, and mapped status.
* **The rooms that would be created**, summarised per layout and totalled
  — *"152 units, ~880 rooms"* is the number that makes someone check.
* **The status mapping**, as the §1.2 table, so the collapse of `NTV` and
  `UE` into `occupied` is visible rather than buried.
* **What already exists**, if the assessment has been walked: areas that
  will be reused, rooms that will be appended, and **an explicit count of
  findings that will not be touched**. Assessment 11's 15 kitchen findings
  should be visible as *"15 findings preserved"*, not implied by silence.
* **Every refusal, named individually.** Not *"3 units skipped"* —
  *"unit 118: type string 'STUDIO' does not state bedrooms"*, one line
  each.

That last point is the one this file makes concrete. Oxford Pointe has
**zero** refusals — 152 of 152 parse — so the refusal list will be empty
on the only file we can test it with. **It must still be built and it must
still be exercised**, because an empty list on the one available file is
precisely the condition under which a summarised-refusal bug ships
unnoticed.

### The 18 blank statuses must appear as themselves

The preview shows what the *file* said and what it will *become*:

    unit 118    2/1.5 RENOVATED    825 sqft    (no status) → vacant

Not `vacant` alone. §1 concluded blank means vacant on strong evidence,
and the preview is exactly where that conclusion should remain visible and
contestable rather than being applied silently. If a later rent roll
leaves status blank for a different reason, this screen is the only place
anyone would catch it.

---

## 6. What this does not answer

* **`UE`.** Not blocking (§1.2), and worth one sentence from Michelle or
  the property manager when convenient.
* **Lettered unit labels.** §2.3 — recommend refusing them until a real
  lettered roll exists.
* **Studios.** No row in either file has one; the parser refuses and
  reports, and that path stays untested until a file has one.
* **Which assessment a roll seeds into.** A rent roll belongs to a
  property; assessments belong to a property and a date. Seeding into a
  *new* assessment versus *an existing* one is a different question with
  different risks, and it is not answered here.
* **Whether any of this should touch the Underwriting unit lines**, which
  the same file already populates. Two tools reading one file into two
  tables is a coherence question this design does not open.

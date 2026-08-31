# FIRE Capital Tools — handoff

**Written 2026-08-17, updated 2026-08-18. Master at `66b2d1e`.**

This replaces an earlier handoff that had gone substantially stale. That
document's errors cost real investigation time: it had the repo under the
old owner, listed the cash-out refinance as unbuilt when the branch
already existed, and two confident premises in it were simply wrong (see
*Premises that turned out to be false*, below). **Nothing in this file
should be treated as settled unless it says it was verified, and where
something is uncertain it says so.**

---

## Where things run

| | |
|---|---|
| Repo | `firecapitaltools/fire-capital-tools` (transferred; **still public**) |
| Host | Railway, project `FIRE Capital Tools`, service `fire-capital-tools` |
| URL | `https://fire-capital-tools-production.up.railway.app` |
| Deploy | GitHub auto-deploy from `master`. Verified via the Railway GraphQL API: `serviceInstances.source.repo = firecapitaltools/fire-capital-tools` |
| Volume | `/data`, ~0.1 GB of 4.9 GB |

Every persistent database uses a `*_DB_PATH` env var pointing at `/data`.
The user sets Railway env vars themselves — do not attempt to.

`USER_STORE_PATH=/data/users.json` is now set too (2026-08-25), so signup
accounts have somewhere durable to live. **That the volume actually
preserves them across a redeploy is not yet demonstrated** —
`docs/known-issues.md` entry 1 carries the evidence and the six-step check.

**`docs/known-issues.md`** is where anything believed-but-unverified goes,
one entry each, dated, with what would close it. Read it alongside this
file; it is short by design and it is the first place to look before
trusting a claim about the deployed environment.

Railway's GraphQL API sits behind Cloudflare and returns **error 1010**
to a request with no browser `User-Agent`. That is a blocked fingerprint,
not a bad token.

---

## What is merged and live

Twelve commits landed on `master` this session, in five merges. All were
deployed and verified against production before moving on.

| merge | what it does |
|---|---|
| `9e8fdc5` | Notetaker **Word export**, sections chosen per update |
| `4da1901` | **Dead-reader sweep** + `SOURCE_DATE_EPOCH` pin |
| `b613a76` | **Rate/count fix** in the Site DD capex export |
| `51275b9` | **Capex export links** on the assessment detail page |
| `6ba1bad` | **Route-reachability sweep** |
| `07e746e` | **Properties foundation** — a record that names its deal belongs to it |
| `e71d382` | **Manual-cost rate fix** — the unit belongs to the item |
| `aa2be2d` | **Notetaker sections v2** — CapEx Update, Next Steps, prompt v2 |

**Deployed test suite: 1450 tests, OK, 19 skipped.**

### Word export (`9e8fdc5`)

`python-docx==1.2.0` pinned. Sections are a **toggle over whatever the
update already has**, every box ticked by default — that is "all", not a
curated subset, because Michelle's real updates carried a different set
each time. `select_sections()` filters without reordering; order comes
from the update, never from the request. An empty section renders its
"not discussed" line and stays visibly empty. Nothing is generated to
fill it.

Found while checking the button was reachable: `notes_db.list_updates()`
had existed since the table did and **no route ever called it**, so a
generated update was reachable only by the redirect immediately after
making it. The index now lists updates.

### Rate/count fix (`b613a76`) — the most consequential change here

Assessment 11 exported a capital budget of **$5.75**. One line, interior
repaint. The researched figure for `walls_ceiling` is **$5.75 per square
foot**, and the export multiplied it by a quantity of 1 — where 1 was the
*instance count* the grouping produces ("forty toilets are one line of
quantity 40"). It then printed "No estimate: 0 item(s)" and "100% of the
total is researched" over the top.

**Seven of thirty-six researched figures are rates** (`RATE_UNITS` =
sqft, lf) and they are the expensive ones: flooring, repaint, roof
covering, facade, paving, roof drainage. On a full walk those dominate a
budget and every one would have come out in single digits.

Now: a rate prices only from a **measured quantity**. Without one the
line keeps its rate, states the measurement it needs, and is excluded
from the total. Per-item figures are untouched. Totals are `None`, never
`0.0` — zero claims the work is free and sums in silently.

The summary is held to the same standard: **no total at all** when lines
exist and none could be priced, "Priced subtotal" when partial, and three
buckets kept distinct — `priced` / `researched-but-unmeasured` /
`unresearched`. An **empty** budget still reports `0.00`, because nothing
recorded as needing work is a finding rather than a gap.

**What Michelle sees on assessment 11 today** (verified live, read-only):

```
Total                             | No priced lines — see below
Inspector estimate                | —
Researched average                | —
Researched rate, not yet measured | 1 item(s)
No researched figure              | 0 item(s)

Nothing here can be priced yet, so there is NO total: 1 line has a
researched rate but nothing measured to apply it to.
```

This is correct and intended. **She was emailed about it before the links
went live.** It is also the strongest argument for unblocking
measured-quantity collection.

---

## Branches

| branch | head | state |
|---|---|---|
| `uw-refi-cashout` | `13c2b7d` | **built, rebased, verified, HELD on a confirmed double-count.** See below. |
| `notetaker-word-export` | `8bde934` | merged, can be deleted |
| `dead-reader-sweep` | `df98c64` | merged, can be deleted |
| `sitedd-rate-fix` | `8a874d4` | merged, can be deleted |
| `sitedd-capex-links` | `a46bd36` | merged, can be deleted |
| `route-reachability-sweep` | `bcccecd` | merged, can be deleted |

### `uw-refi-cashout` — what it contains and what blocks it

**Rebased onto current master, fully re-verified, and HELD on a
confirmed double-count.** Do not merge it as it stands.

It implements Michelle's confirmed terms: excess refi proceeds to
investors, a 1% GP capital transaction fee, payout order payoff → fees →
return of capital, no pref at the event with pref continuing to accrue on
the smaller unreturned base. Cash-in refis are refused. Invariants 1–11
all evaluate to True with a refinance present, and the no-refi behaviour
fingerprint matches master on all five scenarios with its positive
control confirmed to fire.

**THE BLOCKER: `refi_costs_pct` ALREADY INCLUDES THE BANK'S POINT**

This is the definition that will get rediscovered expensively if it is
not written down, so it is written down.

`refi_costs_pct` was authored to mean **"points and closing"** — its
original docstring says exactly that. **A point IS lender origination**,
priced as a percentage of loan size. Four signals agree:

1. The original docstring: `- refinance costs (points and closing)`.
2. The form label: "Refinance: Costs (**% of new loan**)". Third-party
   closing costs — title, appraisal, recording — are flat dollars. A
   percentage-of-loan field is origination-shaped.
3. **The acquisition side folds them together the same way.**
   `DEFAULT_ACQUISITION_COST_CATEGORIES` lists `origination_fee` as one
   of nine line items *inside* acquisition costs, beside Legal, Appraisal,
   Lender Legal and Doc Prep. There is no separate loan-fee input anywhere
   in the app.
4. The original fixture was exactly 1.0% — $52,000 on $5.2M. Precisely
   one point, which is precisely a standard bank loan fee.

Michelle then said "there is ALSO a standard 1% loan fee that the bank
takes". She was answering about the GP fee, so "also" most naturally
means *in addition to the GP fee* — but the branch as built adds it on
top of `refi_costs` as well, charging the bank's point twice.

**Cost of the double-count**, at her real 1%/1%/1%:

| | as built | if `refi_costs` already is the bank fee |
|---|---|---|
| to investors | $663,282.61 | $715,282.61 |
| levered IRR | 18.7575% | **19.0902%** |
| equity multiple | 2.1271 | **2.1472** |

**−0.33 IRR points and −0.02 on the multiple**, on figures she acts on.

**Two resolutions, and the choice is hers:**

- **(a)** Drop `refi_bank_fee_pct`; tell her the bank's point is already
  inside "Refinance Costs".
- **(b)** Keep it, and **redefine `refi_costs_pct` as third-party closing
  costs only**, so the two are disjoint. This matches how she described
  it and gives her the visibility she asked for.

**(b) is the recommendation**, and it is free right now: production has
no refi columns at all, so there is no data to migrate. But it changes
what an existing field means, so it is not a call to make silently.

**The question is with Michelle. Do not implement either until she
answers.**

---

## Michelle answered all six (2026-08-26) — and three of them CLOSE work

Her answers verbatim, with what each one settles. **Three close work
rather than opening it**, and those are recorded as decisions so nobody
re-derives them: an investigated-and-declined design and a never-considered
one look identical a year later.

### 1. Detail values — YES

> *"I AGREE WITH YOUR ASSESSMENT. WE SHOULD BE MORE DETAILED ON WHAT NEEDS
> TO BE REPLACED OR REPAIRED."*

`docs/site-dd-detail-values.md` is approved and gets its own run. It was
re-read on 2026-08-26 against everything merged since it was written and
is still current — the confirmation, and the one ordering change it
produced, are recorded at the end of that document.

### 2. Per-bed occupancy — YES, and BROADER than the question asked

> *"THIS IS IMPORTANT. WE NEED TO DISTINGUISH IF A PROPERTY IS BY UNIT OR
> BY BED. IN STUDENT HOUSING, WE NEED PER BED OCCUPANCY. WITH
> MULTIFAMILY, IT WOULD BE BY UNIT OCCUPANCY."*

She was asked whether to build per-bed for one property. She answered that
the tool needs a **mode**. That reframes the work from a special case onto
the properties foundation, and `docs/site-dd-per-bed-occupancy.md` is
revised against it. **Note what she did not say**: she did not say she owns
a by-the-bed property, and she did not answer the shared-bedroom question
that decides option B from option D. Both remain open.

### 3. Unit status — NO. **AREA_STATUSES widening is DECLINED.**

> *"UNIT STATUS ISN'T IMPORTANT FOR MY PURPOSE. WHAT IS MOST IMPORTANT IS
> THE CORRECT UNIT NUMBER, UNIT TYPE, OCCUPIED OR VACANT. ONE OTHER FIELD
> I'D LIKE TO INCLUDE ARE TWO EXTRA FIELDS FOR 1) PETS PRESENT; 2) HOW
> MANY PETS. THESE TWO WOULD BE DONE EARLY ON WHEN THE INSPECTOR WALKS
> INTO THE DOOR."*

**Considered and declined, not abandoned.** Two runs of design went into
widening the per-unit vocabulary — the one-axis-versus-two question,
`Notice` as a fourth state, `Vacant Not Ready`, and Model/Holding. The
work was sound and the reasoning is preserved in
`docs/site-dd-per-bed-occupancy.md` §3A. It is declined on her stated
requirement, which is narrower than what we designed: **unit number, unit
type, occupied or vacant.** Three of those four already exist.

The design argued the vocabulary was *"short by at least one state, and
that is true for conventional multifamily too"*. That argument is not
withdrawn — it is **outranked**. She is the person the distinction would
serve and she says it does not serve her. Do not rebuild the case from the
document without a new fact; the document is the record of why, not a
standing proposal.

**What she asked for instead** is two new fields, pets present and pet
count, which is the smallest thing in this batch and is built. They are
columns on `site_dd_areas`, not checklist items, so they cannot reach the
capital budget — see *Pets at the door, and why they are not checklist
items* below.

### 4. Acquisition fee — it is a COST. **The GP-receipt branch is CLOSED.**

> *"ACQUISITION FEE IS PART OF THE COST OF THE DEAL. IN YOUR EXAMPLE, THE
> $225K WOULD BE PART OF THE TOTAL CAPITAL RAISE NEEDED TO OFFICIALLY
> CLOSE. OTHER FEES LIKE ASSET MANAGEMENT FEES, CAPITAL TRANSACTION FEES,
> CLOSING COSTS ETC ARE ALL PART OF THE COSTS."*

**Nothing changes, and that is the finding.** `acquisition_costs()` already
folds `acquisition_fee_total` into `effective_total` / `effective_pct`,
which `underwriting_math` hands to the engine as equity required at close.
The model has always treated the fee the way she describes it. Verified in
code rather than assumed: `tools/underwriting_math.py`, `effective = (…) +
fee_total + loan_fee_total`, and `_engine_inputs(scenario,
acq["effective_pct"] + capex_pct)`.

**The second sentence is worth more than the first.** She was asked about
one fee and answered about the class — asset management, capital
transaction, closing costs, *"all part of the costs"*. That retroactively
confirms the **existing convention across the board**, not just this line
item. A convention nobody had put to her is now one she has stated. Any
future "should this fee be a GP receipt instead?" is answered in advance.

### 5. Scorecard period mismatch — HER DATA ENTRY, not our bug

> *"JACKSON'S T12 SHOULD MATCH MY SCORECARD MONTHS. IF THEY DON'T, THAT IS
> MY HUMAN ERROR. ALL PROPERTIES' T12s SHOULD MATCH THE SAME TIME PERIOD
> AS THEIR MATCHING SCORECARD."*

**`align_stated_occupancy()` stays exactly as built.** Michelle's T12 KPIs
covered 5/24–12/24 against a Jackson P&L covering Aug 2025–Jul 2026: zero
months in common, and the card says *"No months in common"* rather than
showing a number.

**The honest behaviour did its job, and that is the entry.** It was built
as a refusal to display something that could not be justified, over a
brief that would have put a plausible 50–60% figure from the wrong year
under a Jackson heading. It has now caught a **real** mistake in real data
and she has confirmed it as one. This is the payoff for a design that
declines rather than guesses, and it is worth having on the record next
time declining looks like it is costing a feature.

It also converts a rule into a stated requirement: **a property's T12 and
its scorecard cover the same period**, by her own instruction. A mismatch
is now a data-entry error to surface, not an ambiguity to accommodate.

### 6. Per-account data — SHE CANNOT REMEMBER

She does not recall what she meant. **Call Friday after 2pm.** Stays
unscoped until then — do not infer a requirement from the phrase. Note
this also leaves the [three deleting routes](#the-three-deleting-routes-a-decision-not-to-build-with-its-condition)
deferral in place: per-account data shipping is the first of its three
trigger conditions, and it has not shipped.


### Notes for the Friday call

Short, and only the things that need her rather than us.

**1. Per-account data.** What she meant. Nothing is scoped until this is
answered — do not infer a requirement from the phrase.

**2. The properties table (Blocked on Michelle item 3) — now with a
second reason.** It has been outstanding since Part 47, and until this
week the only argument for settling it was the Site DD property header.
There is now a second: **her per-bed answer did not unblock per-bed work,
it re-pointed it at this decision.**

She asked for the tool to distinguish a by-unit property from a by-bed
one. That flag is a fact about a *property* — it does not change between
inspections, and two assessments of one building that disagreed about it
would be a contradiction rather than a history. **There is no properties
table anywhere in the product**, so the flag has no correct home, and
per-bed cannot start properly until it does. See
`docs/site-dd-per-bed-occupancy.md` §R2.2.

So item 3 now blocks the larger of her two "this is important" answers,
which it did not appear to a week ago.

**3. Ask them together, not separately.** Per-account data and a
properties table are **adjacent questions**: both are about what a record
belongs to and who may see it. One asks *which property is this row
about*, the other asks *which person is this row for*. Answering them
apart risks a properties design that has to be reopened the moment
per-account data arrives, or an access model with nothing to hang
per-property permissions on.

She may well have one picture in mind that covers both. Worth putting
them side by side rather than as two items on a list.

**Also still open and worth one sentence each if there is time:** the
shared-bedroom question (*can one bedroom be leased to two people at any
by-the-bed property you own?* — it decides the shape of per-bed work), and
**one real rent roll from a by-the-bed property she owns**, which collapses
four separate unknowns at once.

---

## Pets at the door, and why they are not checklist items

Michelle: *"one other field I'd like to include are two extra fields for
1) pets present; 2) how many pets. These two would be done early on when
the inspector walks into the door."*

Two columns on `site_dd_areas`, rendered in the **unit header** above the
room list and above the unit-wide checks. Not checklist items, and the
placement is the whole of the "must not reach the capital budget"
requirement rather than a separate precaution.

### The requirement was satisfied structurally, not by a registry entry

A checklist item becomes a row in `site_dd_findings`, which is the table
the capital budget is built from. Whether a dog produced a repair line
would then depend on `needs_work()` — specifically on somebody remembering
to register the yes/no option set in `WORK_OPTIONS` with an empty
frozenset, the way `FLOORING_TYPES` and `PEST_TYPE` are. That works, and
it is a maintained fact rather than a guaranteed one.

Area columns are a different table. `build_lines()` never reads them.
There is no registry entry to forget.

The registry question was still answered rather than dodged, because it is
the shape somebody will reach for next time: `needs_work()` returns False
for a yes/no choice item and for a number item, and an option set nobody
registered falls to `WORK_OPTIONS.get(key, frozenset())`. Both are pinned,
with a positive control showing `needs_work()` still says yes to a missing
smoke alarm — otherwise the assertions would pass on a function broken
into always returning False.

### Three states, because two would be a lie

`pets_present` is nullable and the picker offers **Not stated** as the
default. "No pets here" and "nobody asked" are different facts to whoever
reads the report, and a checkbox has two positions and three meanings.

`pet_count` is nullable for the same reason and carries the falsy-zero
trap directly: **0 pets and no answer must stay distinguishable.**
`clean_pet_count()` treats empty string as None and `"0"` as 0, the
template renders `area.pet_count if area.pet_count is not none else ''`
rather than `or ''`, and the summary line guards on `is not none`. This is
the class the handoff already records — `bedrooms or '—'` rendering a
studio as unknown — applied on the way in rather than after a report comes
back saying zero pets in a building full of dogs.

### Absent means unchanged, on new columns, before anything can break

`update_area()` writes label, status and notes unconditionally as it
always has — every form that posts there renders all three. The pets
fields do **not** inherit that assumption: they are written only when the
key is present in the dict, and `save_area` passes them only when they are
present in the form. Unreachable today, cheap now, and the reason is the
same one that produced `_kept_field()`.

### The fifth label map

`PETS_LABELS` plus `pets_present_label()`, reached through the accessor,
for the reason `AREA_STATUS_LABELS` documents at length: this app runs
Jinja's default `Undefined`, so a subscripted miss renders as the empty
string and leaves no trace. A test asserts the template calls the accessor
and never `|title`.

---

## Blocked on Michelle

Nothing below should be started without an answer. Each has been
investigated; none has been built.

**1. Measured-quantity collection in the Site DD UI.** *Highest value.*
Inspectors do not record areas or lengths on the walk, so every
rate-priced item — the expensive ones — is unpriceable. This is what
turns the capex export from empty into real numbers. The question that
decides the design: **do inspectors measure on the walk, and with what?**
A tape measure per room implies one UI; a single unit square-footage from
the rent roll implies a very different one.

**2. Rent-roll upload — scope is contradictory.** Her Site DD document
says *"upload rent roll to know number of units."* Her in-app feedback
asked for **bedroom derivation from unit type and occupancy mapping**.
Those are materially different asks — the first is a fraction of the
second, which is a two-to-three session build. **This discrepancy is
unresolved and is a direct question to her.** Also still blocked on a
**2BD sample file**: the only real rent roll we have (Jackson, Appfolio)
is 16 units all `1/1.00`, so the headline feature — derive two bedrooms
from the unit type — has no test case.

**3. Site DD property header** (name, vintage, address, building count,
optional sqft). Only `property_label` exists; the other four are
genuinely new — there is **no properties table anywhere** in the product,
and the 12-property registry is assembled at request time from Deal Dive,
Underwriting and Site DD labels. Three shapes were proposed
(per-assessment columns / fields on a property record / a walk-date
snapshot with visible disagreement). It is a judgment call and was left
to her. The failure mode to avoid: per-assessment columns mean retyping
everything on re-inspection and two rows silently disagreeing about the
build year.

**4. Notetaker sections.** Renaming Operations → Property Update and
Capital Improvements → CapEx Update, plus adding **Legal Update** and
**Next Steps**. **Proven not display-only**: `build_instructions()`
interpolates `s['name']` straight into the prompt, so a rename changes
1,377 characters of what is sent to the API. `cache_key()` hashes
`prompt_version`, not the prompt text, so renaming without bumping the
version would serve results generated under the old headings. One change,
and it costs real OpenAI spend against the **$60/month** budget.
Separately: the update page renders `section.name` from the **stored**
JSON, so existing updates keep old headings regardless.

**5. Refi fee base.** See above.

---

## Verify on deployed code, not by reading it

**A standing rule, earned twice, and both times reading the code would
have concluded the opposite.**

**Instance 1 — the guard that always returned True.** Part 51 added a
check that refused to write the user store when `USER_STORE_PATH` was
unset. It read `app.config`, asked whether the key had a value, and looked
correct on the page. `config.py` resolves that key with
`os.environ.get(NAME, fallback)`, so it **always** has a value — and the
deployed app reported the store configured on a box where the variable is
not set at all. The banner never rendered; the refusal never fired. The
unit tests passed because they popped the key, which production never
does. **Deploying it is the only thing that showed the guard was inert.**

**Instance 2 — the deploy source after the GitHub transfer.** Recorded in
the original handoff: transferring the repo broke Railway's deploy
connection, and it read as "GitHub Repo not found" for roughly an hour
before anyone noticed. Nothing in the repository could have shown that.
The code was fine; the thing that was broken was outside it.

**The shape they share: the code was correct and the environment was not,
and only the environment can report on itself.** A local run inherits a
different config, a different filesystem, a different set of variables and
a different deploy path. Every one of those differences is invisible to
reading, and each is a place a correct-looking change can do nothing at
all.

**So: after any change that depends on configuration, a path, a
credential, or a deploy, exercise it on the container.** Not the unit
tests — those run in the wrong environment by definition. The check that
found instance 1 was four lines: import the app, print what the guard
returns, hit the route.

**And the corollary that makes it cheap: verifying is not merging.** Both
instances were caught by running code on the container, and neither
required a risky production write — a redirected cache, a scratch
assessment removed afterwards, an in-process config override that never
touched Railway.

## A partial defence is more dangerous than none

`save_expenses` carried acquisition lines through with a comment naming
the hazard exactly: *"reading them from this request would find nothing
and silently blank every amount."* It was the route everyone pointed at —
**including this file, in the Part 51 audit** — as the precedent for the
whole absent-means-unchanged pattern.

It was defending **three of six fields**. Rows were safe, because it
iterates storage. `growth_schedule` was safe, explicitly. `annual_amount`,
`growth_pct` and `is_included` were read straight from the request, so a
stale render left a line at `amount=None, growth=None, is_included=False`.

**Why partial is worse than absent:**

1. **It is cited as evidence.** A route with no defence invites scrutiny.
   A route with a defence and a good comment about it gets held up as the
   example, and nobody re-reads the other four fields — the comment
   answers the question before it is asked.
2. **The surviving row hides the damage.** A deleted row is conspicuous.
   A row that keeps its label, keeps its position, and quietly stops
   contributing to NOI reads as a deliberate exclusion. The defence is
   what makes the failure look intentional.
3. **It sets the standard for the next one.** The pattern gets copied at
   the depth it was found, so a half-defended precedent produces
   half-defended descendants.

**The rule: when a defence is cited as precedent, check its coverage
before repeating it.** Not whether it exists — what it covers. Both times
this bit, the defence was real and the citation was honest; the gap was
between "this route defends against X" and "this route defends X
completely", and nobody had measured which.

---

## The three deleting routes: a DECISION not to build, with its condition

> ## ✅ RESOLVED 2026-08-29. The condition fired on its own.
>
> **Trigger 2 — "more than one person can log in" — became true on
> 2026-08-27**, when a second account was created through the signup form.
> Not by anyone acting on this entry: it was noticed while gathering
> production figures for something else, and the condition below was
> specific enough that recognising it took one line of reading.
>
> The rendered-state token is built — `tools/rendered_state.py`, one
> helper, three call sites — and verified on deployed code with two
> sessions on one scenario: the stale save is refused, the other session's
> loan survives, and a current save still works including deliberate
> deletion.
>
> **This entry is kept rather than deleted, and the decision below was
> correct when it was made.** Deferring was right, the reasoning holds,
> and the only thing that changed is the world. What follows is the
> record of a deferral that worked, not of a mistake.
>
> ### All four premises were re-checked before building
>
> The investigation was weeks old and the codebase had moved, so nothing
> below was taken on trust. All four still held, with one refinement:
> **capex deletes by BLANKING a fixed set of slots** rather than removing
> DOM rows, so its exposure is a row *added* since render rather than one
> *omitted*. The destruction is identical and so is the fix.
>
> ### What it cost the user, stated rather than discovered later
>
> The refusing routes redirect, so a stale session **loses its unsaved
> edits**. `detail()` is 124 lines of context assembly; re-rendering it
> from a POST would rebuild all of it and would show fresh data everywhere
> except the section just edited. The same routes already lose the form on
> a validation refusal, so this matches the behaviour beside it. Nothing
> **stored** is ever at risk — the refusal happens before any write.



`save_loans`, `save_capex` and `save_gp_partners` delete omitted rows
rather than blanking them. **Investigated in Part 52 and deliberately left
alone.** Recorded as a decision because "not built" and "not noticed" look
identical six months later, and this file has been wrong about which was
which twice.

### Absent-means-unchanged is the WRONG fix here

Every one of these forms removes a row with
`onclick="this.closest('tr').remove()"`. **Omission is the removal
signal.** Applying the Site DD fix would make it impossible to delete a
loan, a capex line or a GP partner. This is not the same bug wearing a
different hat.

### A rendered-items manifest is impossible, and that corrects Part 49

Part 49 deferred "a hidden field listing rendered row ids" as the answer
if a real conflict appeared. The conflict appeared and **the answer does
not work**, for two reasons found by looking rather than assuming:

* **The forms carry no row identity at all.** Loans and partners post
  positional `getlist` arrays; capex posts a loop index `{{ i }}`. There
  is no id in the form to list.
* **The ids churn.** All three tables are `DELETE`-then-`INSERT` on every
  save, so ids are reassigned each time. A manifest of ids would be stale
  the moment anything was written.

### The correct shape is a rendered-state token

Hash the collection at render, embed it in the form, recompute at save.
Unchanged, proceed normally **including deletions**; changed, refuse with
"this page is out of date — reload and reapply". It needs no row identity,
handles deliberate removal correctly, and fails loudly instead of
guessing. One helper, three call sites.

### Why it is not built, and what would change that

The back-button path — the one that actually mattered for Site DD — **is
already closed** on all three pages by `no-store`. What remains is two
tabs open by one person. And:

* there is **one login**, the env-configured admin, with **zero signup
  users**, so two *people* is currently impossible;
* Site DD had a described two-person workflow (*"Michelle reviewing while
  MJ walks"*). Underwriting and the GP split are analyst-side, single-user
  tools with no such workflow described.

**THE CONDITION, and it is the whole reason this is a decision rather
than a shrug: build the token if ANY of these becomes true.**

1. **Per-account data ships** — that is the feature whose entire purpose
   is more than one person's data.
2. **More than one person can log in** — the moment `USER_STORE_PATH` is
   set and a second account exists.
3. **Any of those three pages becomes part of a two-person workflow** —
   the Site DD shape, arriving in a different tool.

Any one of the three, not all three. Until then the exposure is one person
with two tabs on their own analysis, and the cost of being wrong is a
reload.

---

## A condition attached to a deferral has now paid off twice

Two deferrals in this project were written with an explicit trigger rather
than as an intention to revisit. **Both fired without anyone going back to
look for them.** That is the entire argument for the practice, and it is
worth stating now that there is a pair rather than an anecdote.

| | the condition | how it fired |
|---|---|---|
| **Entrata** | survived in one statement of the rule and was lost in the compressed restatement — the shorter version read as an unconditional claim | the loss itself was the finding: comparing the two statements showed the condition had been dropped, which is how the rule got its condition back |
| **The three deleting routes** (Part 52) | *"build the token if ANY of these becomes true: per-account data ships; more than one person can log in; any of those three pages becomes part of a two-person workflow"* | **trigger 2 became true on 2026-08-27** when a second account was created through the signup form. Noticed on 2026-08-29 while gathering production numbers for an unrelated document |

**Neither was found by remembering to check.** The Part 52 one was
recognised in a single line of reading, because the condition named an
observable event — *a second account exists* — rather than a feeling like
*when this gets risky enough*. A vague condition would have required
somebody to re-derive the judgement; a specific one only required
somebody to notice a fact they were already looking at.

### What makes a condition fire on its own

* **It names something observable, not a threshold of concern.** "More
  than one person can log in" is a thing you can check in one query.
  "When collaboration becomes important" is not.
* **It is written where the deferral is**, so anyone reading the reason
  for not building reads the trigger in the same breath.
* **Any one of several, not all of them.** The Part 52 entry listed three
  and said *"any one of the three, not all three"*. Two of the three have
  still not happened.

### And the Entrata half is the warning

A condition only survives if every restatement carries it. The Entrata
rule lost its condition in a *shortened* version, which then read as
unconditional and was acted on that way. **Compression is where conditions
die** — the qualifying clause is always the part that looks droppable,
and dropping it converts a decision into a rule.

So: attach conditions, name observable events, and when restating a
conditional rule in fewer words, check that the condition survived the
edit rather than assuming it did.



---

## Rule 2 audited at its real scope, and the dropped clause was right

Part 47 checked the four routes the rule names. **The rule's next sentence
— lost to a quotation and restored in Part 50 — says "assume it applies to
any route not yet audited."** Audited properly in Part 51: there are
**eleven** collection-writing routes, and the four named ones are not the
worst of them.

Every verdict below was produced by running the route against a temporary
database, never by reading it.

| route | rewrites | an omitted field or row | stale render? |
|---|---|---|---|
| `site_dd.save` **(property scope)** | findings, via upsert | **BLANKS condition, note, and `overall_notes`** | **YES — `site_dd.detail` has no `no-store`** |
| `site_dd.save_area` | findings, via upsert | preserved *(fixed Part 49)* | mitigated |
| `site_dd.save_room` | findings, via upsert | preserved *(fixed Part 49)* | mitigated |
| `underwriting.save_loans` | whole loan stack | **DELETES the row** | two-tab only |
| `underwriting.save_capex` | whole capex budget | **DELETES the row** | two-tab only |
| `investor_report.save_gp_partners` | whole partner list | **DELETES the row** | **YES — `investor_report.detail` has no `no-store`** |
| `underwriting.save_expenses` | expense set | rows kept; **amount → None, growth → None, `is_included` → False** | two-tab only |
| `underwriting.save_acquisition_costs` | acquisition lines | **DELETES the line**; operating lines carried through | two-tab only |
| `underwriting.save_assumption_years` | per-year overrides | override reverts to "follow the flat rate" | two-tab only |
| `underwriting.upload_t12` | expense set | n/a — a file, not a form | no |
| `underwriting.upload_rentroll` | unit lines | n/a — a file, not a form | no |

### The finding that matters most: the Part 49 fix missed a route

`site_dd.save` is the **property-scope** form, and it does not use
`_collect()`. It has its own inline collection loop with the same
collapsing read the fix removed elsewhere:

```
raw = (request.form.get(f"condition_{key}{suffix}") or "").strip()
```

Demonstrated live against a temp database:

```
complete save : condition='repair'  note='ponding at the drain'  overall_notes='walked the roof'
STALE save    : condition=None      note=None                    overall_notes=None
```

**The Part 49 fix was scoped to the function it found, not to the
pattern.** That is exactly the failure the dropped clause names, and it
happened in the same session that recovered the clause. `_kept_cost`,
`_kept_label` and `_kept_measure` are all used here, so the cost, label
and measure survive — only the judgement and the notes are lost, the same
asymmetry as before.

### Three routes delete rather than blank, which is worse

`save_loans`, `save_capex` and `save_gp_partners` build their list purely
from what the form posts. An empty POST removes the collection entirely,
and a stale render removes whatever it did not know about:

```
loans in storage: 3   ->   stale page posts the 2 it knew   ->   ['Senior', 'Mezz']
the third loan WAS DELETED
```

There is no row left carrying a null. The loan is gone.

### The route everyone points at as the defence is only half defended

`save_expenses` is cited — correctly — for carrying acquisition lines
through, and it also does absent-means-unchanged for `growth_schedule`.
But its **value** fields are read straight from the form:

```
before: amount=60000.0  growth=3.0  included=True
after : amount=None     growth=None included=False
```

The row survives, so nothing looks deleted; the line simply stops
contributing to NOI and reads as deliberately excluded. **A partial
defence is more dangerous than none, because it is the one people cite.**

### Not fixed yet, deliberately

Nothing above is repaired in this run. Fixing them one at a time is how
the fifth one gets missed — which is precisely what happened to
`site_dd.save`. The whole picture first, then one change that addresses
the pattern.

Two cheap mitigations are already identified: `no-store` is missing on
`site_dd.detail` and `investor_report.detail`, both of which render
forms that write collections.

---

## Per-account data — a question for Michelle, not a task

Her words, and the whole of it:

> *"Data should be per-account, not site-wide, with a way to link accounts
> and share specific deals."*

**Genuinely untouched, checked rather than assumed.** No `user_id`,
`owner_id`, `account_id`, `tenant_id` or `created_by` on any table in any
of the twelve databases. `current_user` appears in exactly two places,
both admin gates in `admin.py`. Every logged-in user sees every deal,
scenario, assessment and report.

**Nothing later superseded it.** The properties foundation, `deal_id`
linking and the Investor Notes registry all answer *"what does this record
belong to"*. This asks *"who may see it"*. Different axis; no part of one
is a part of the other.

**The three open questions, recorded as questions:**

1. **Who is an account?** People at her company, outside partners, or
   both. The answer decides whether this is user-scoping or real
   organisation-level multi-tenancy.
2. **Does sharing mean full access or read-only?** The backlog raised this
   and it was never answered.
3. **What happens to what already exists?** Ten scenarios, four
   assessments, two deals, twelve cached lookups and three properties of
   history currently belong to nobody. They have to become somebody's, and
   only she can say whose.

Not scoped and not estimated. The one thing sayable without her: it
touches every table and every route, and there is nothing partial to build
on.

---

## Site DD Lite: designed only, still

**Confirmed twice — Part 47 and Part 50.** `status` exists on the
assessment, is validated, and is displayed in three templates. **Nothing
consumes it as a filter**, which is why the feature never shipped: not
difficulty, just nothing reading the field.

Michelle settled the design herself: *"the normal tool should be fine if
we make it toggleable enough"* — vacant units and common areas only, a
lighter output, one tool rather than two.

**Small build, blocked on nothing but a decision.** It is a query filter
plus a UI control on a field that already exists and already validates.
The original handoff flagged its status as unconfirmed; it is confirmed
now, and the answer is that it was designed and never built.

---

## The eleven standing rules of the original handoff, audited

**The document this file replaced had eleven numbered standing rules. This
file inherited some of them, silently dropped others, and nothing noticed
for thirty-six runs.**

The original was **never in the repo** — `ae22394` created `HANDOFF.md`
fresh rather than editing a predecessor, and `git log --diff-filter=D`
finds no deleted handoff-shaped file in any branch. So there was no
recoverable copy here, and no in-repo check could ever have found the
gap.

**It is committed now, in Part 50, at
`docs/original-handoff-2026-08-16.md`** — verbatim, 21,116 bytes, marked
superseded. It took three attempts: the paste failed twice, and only
moving the file onto disk worked, which is the chat-context lesson
demonstrating itself.

**AND THE RECOVERY HAD INHERITED SEVEN TRANSCRIPTION LOSSES.** Part 47
wrote the eleven from a quotation rather than from the document, and
diffing the two in Part 50 found the quotation had dropped material from
seven of them. Four were clauses; three changed what a rule says:

| rule | what the quotation lost |
|---|---|
| 2 | *"assume it applies to **any route not yet audited**"* — so the Part 47 audit checked exactly the four named routes as though they were the scope. **They are examples of a pattern, not an enumeration of it.** |
| 5 | the entire mechanism. The original is *"any number not confirmed ships with a **test-enforced** 'not confirmed' disclaimer"*, with `deal_readiness_defaults.py` named. Part 47 recovered a different rule — "never assert what you have not read" — which forbids where the original permits-with-a-disclaimer. |
| 7 | `openai_usage.py` named by file, "must be used by any new AI feature, tagged correctly". |
| 8 | *"**Never combine build-and-merge into one silent action**"* — an operative clause we follow but had stopped recording. |
| 1, 3, 9 | wording and tails, including rule 3's "rebase + byte-hash-verify if it has" and rule 9's "this is the expected, correct behavior, not a deviation to avoid". |

All eleven are now verbatim in
`docs/original-handoff-standing-rules.md`, verified by a normalising diff
against the source rather than by reading.

**A rule recovered wrong is worse than one recovered late**, because the
error inherits the authority of the recovery. Rule 5 is the clear case: it
was restored confidently, it read well, and it was not the rule. Rule 2 is
the expensive one: the missing clause is precisely the one that would have
told the Part 47 audit its four-route check was not exhaustive.

**The lesson is narrower than "keep the predecessor" and worth stating
separately: recover from the artifact, not from a memory of it — including
your own.** Both parties here had a faithful memory of a document neither
was reading, and it still lost seven clauses.

| # | rule | status |
|---|---|---|
| 1 | every persistent DB path: env-var-with-fallback, **both** failure states demonstrated | **absent — restored below** |
| 2 | full-collection-rewrite routes silently blank what a POST omits | **present but weakened — corrected below** |
| 3 | merge discipline | present, intact |
| 4 | `deal_analyzer_math.py` is sacred | present, **correctly superseded** |
| 5 | no fabricated authority | **absent — restored below** |
| 6 | no scraping | present, correctly narrowed |
| 7 | OpenAI spend discipline | present, and since generalised |
| 8 | one prompt at a time, easiest to hardest | half present |
| 9 | say so when the instruction is wrong or stale | **absent — restored below** |
| 10 | reachability is not correctness | present in substance, framing lost |
| 11 | Census and BLS have no paid tiers | absent here, **lives in better code** |

### Rule 2 in detail, because it is a data-loss rule and it is still live

The current text names four routes and says a partial POST "silently
blanks fields". **Checked against the code rather than assumed, and the
hazard is real — demonstrated by running it:**

```
save_area, complete POST  -> stored answer stays 'good'
save_area, PARTIAL POST   -> stored answer becomes None
```

`_posted_instances()` returns `{1} ∪ existing ∪ posted`, so **instance 1
of every catalogue item is always emitted**, whether the form mentioned it
or not. An item absent from the POST is written back with
`condition=None`. `replace_expense_lines` and `replace_loans` are both
still literal `DELETE … INSERT`, so the wholesale-rewrite shape is
unchanged.

**But the shape has shifted in one place, and that is the useful part.**
`save_expenses` has grown a specific defence since the rule was written:

> *"Acquisition costs are edited by their own form and are not rendered as
> inputs here. Reading them from this request would find nothing and
> silently blank every amount, so they are carried through untouched
> instead."*

Somebody hit this exact hazard in that route and fixed it there. The rule
is therefore **narrower than it was in one route and unchanged in the
other three** — which is worth knowing, because "we haven't hit it lately"
is not evidence the hazard is gone. We have barely written to production.

Two corrections to the current wording while restoring the weight:

* it lists `replace_loans` among the blanking routes but describes
  `replace_expense_lines` only as "reassigns line IDs on every save".
  **Both** are wholesale replacements; the ID reassignment is a second,
  separate consequence.
* it dropped *"multiple real incidents were recovered because of this"*.
  That sentence is why the rule is obeyed rather than noted.

**RESTORED, with its weight: always post complete forms; always snapshot
before a real production write. This rule exists because production data
was lost and recovered, more than once.**

### Rule 1, restored and widened

*"Every persistent DB path: env-var-with-fallback, verified via live
in-process code, never trust the Railway dashboard. Any new `*_DB_PATH`
must demonstrate **both** failure states (unset → visible red banner
naming the var) and success, not just the good one."*

Still true, still not written down anywhere until now. And Part 46 found
the same hazard through a different door: a test redirected a cache with
`MARKET_CACHE_DB_PATH`, which is not a real variable, so the redirect
silently did nothing and wrote to the developer's own database. **A
misspelled env var fails open — it does not raise, it returns the
default.**

So the rule covers both directions: the production path and the test
redirect away from it. `mode=ro` is the member of this family that fails
**closed**, which is why it has never caused an incident, and patching
`get_db_path` is the test-side equivalent — a typo there raises.

### Rule 5, restored: no fabricated authority

Absent entirely. The only two occurrences of "fabricat" in this file are
about Entrata estimates, not the rule.

**Never present a number, a source, a quota, a limit or an API behaviour
as established unless it was read from the thing itself.** This session
is the argument: the RentCast `bedrooms` parameter, the `to_capex_lines`
glob, the Jinja `Undefined` claim and the `normalize_month` behaviour were
all asserted confidently and all four were wrong. It is the parent rule of
"check the premise against the code" and of the Part 28 message standard,
both of which survived — the general form did not.

### Rule 9, restored: say so when the instruction is wrong

*"When investigation shows the instruction was wrong or stale, say so and
propose the correct thing rather than building what was asked."*

Absent as a rule and **practised constantly** — the Part 43 brief's
"hers is the only figure available" was false for Jackson, the Part 46
brief cited a rule that does not exist in the repo, and the Part 45 brief
carried a false premise about RentCast. Each was reported rather than
built around. That the behaviour survived without the rule is luck, or
rather it is the rule having been absorbed; writing it down costs nothing
and makes it inheritable.

### Rules kept as they are

**3, merge discipline** — intact and exercised every run.

**4, `deal_analyzer_math` is sacred** — deliberately superseded. The
byte-hash version proved nothing about behaviour and failed on any branch
that legitimately added a function; the two-signal behavioural fingerprint
replaced it and the old rule is named in this file so it is not
reinstated. **Do not restore the original form.**

**6, no scraping** — present and correctly narrowed in Part 41 to
contractor-pricing and listing sites, explicitly not licensed APIs.

**7, OpenAI spend discipline** — present as **Money**, and since
generalised beyond OpenAI: RentCast has the same shape (shared cap,
per-feature counter, confirm-before-spend, caching), most recently the
size-override gate. Worth stating as one rule about metered third-party
calls rather than one about OpenAI.

**10, reachability is not correctness** — the substance is here (five
features shipped "correct, tested and unreachable", two sweeps, the
navigate-don't-drive-URLs rule) but the four-word framing is the memorable
part and is restored with them.

### Rule 8, half restored

*"One prompt at a time, easiest to hardest, report before merging each
part."* The **one-at-a-time** and **report-before-merging** halves are
present and enforced. The **easiest-to-hardest ordering** is not, and is
not what we do — work runs in the order the prompt sets. Recorded as
lapsed rather than restored, because restoring a rule nobody follows
teaches the next reader to ignore the list.

### Rule 11, not restored — it lives somewhere better

*"Census and BLS have no paid tiers at all."* Absent from this file, but
**live in `tools/service_costs.py`** as structured entries with
`free=True`, a pricing model, `configured_key` and a `last_verified`
date — user-facing, and re-verifiable rather than remembered.

One correction: the original states it flatly, while the code is more
careful — the Census entry records that the free tier *"is near-certain
but has not been formally confirmed."* **The code is the more honest of
the two.** Restoring the flat version to this file would make the record
worse. It stays where it is, and this entry says where.

---

## A rewrite is verified against the document it replaced, not by reading it

Part 41 recorded that a rule stated twice loses its condition in the
shorter statement. **This is the same failure at document scale, and it is
worse, because what is lost leaves no trace at all.**

`HANDOFF.md` replaced a stale predecessor. The rewrite was the right call
— the old document had the repo under the wrong owner, called a built
branch unbuilt, and carried two false premises that cost real
investigation time. **The staleness was real and the cost of the fix was
rules going out with it.**

**The mechanism: a rewrite keeps what the writer is currently holding in
mind and drops what reads as history.** Nobody deletes a rule. They write
a new document about the live problems, and a rule nobody has needed
lately never comes up. So the rules most likely to be lost are exactly the
ones that have not fired recently — and a rule that has not fired recently
is either obsolete or *load-bearing and quiet*, which are indistinguishable
from inside the rewrite. Rule 2 is the second kind: no incident lately,
because we have barely written to production.

**THE CHECK: when a document is replaced rather than edited, it is not
verified by reading the replacement. It is verified by walking the OLD one
for things the new one lacks.** Reading the new document tells you it is
coherent, which it will be — coherence is what the writer optimised for.
Only the old one can tell you what is missing.

Corollaries earned here:

### Why nobody was wrong, which is the part that generalises

Two statements stood in direct contradiction and both were true:

> *"Standing rule 1 already demands both failure states be demonstrated."*
> *"No such rule exists in the repo, and the phrase appears nowhere in it."*

**The original handoff was never a repo file.** It was a document pasted
into the conversation that opened this project. One party was reading it
from that context; the other was reading the repository. Neither could see
what the other was looking at, and neither was mistaken.

**THE HAZARD: knowledge that lives only in a chat context disappears when
the chat does.** It is not merely undocumented — it is invisible to every
instrument, because every instrument this project has reads the repo. A
grep cannot find it, a test cannot pin it, a diff has nothing to compare.
It survives exactly as long as someone remembers to carry it forward, and
it looks identical to settled knowledge right up until the window closes.

**This project has already paid this cost once.** A conversation was lost
to size, and the project carried itself forward on a document that then
lived only in the *next* conversation. Each hand-off looked safe because
the document was right there — in a context that was itself temporary.
Thirty-six runs later four standing rules were gone and the only reason
they came back is that one person still had the original.

**THE RULE: a predecessor must be COMMITTED, not quoted.** If a document
is load-bearing enough to hand forward, it is load-bearing enough to be a
file. Pasting it into a prompt hands it forward exactly once; committing
it hands it forward permanently and makes it diffable, greppable and
testable. The cost is a few kilobytes against a failure mode with no
symptom.

The corollary for anything else living in a conversation: **if it matters
and it is not in the repo, it does not exist.** Not "is poorly
documented" — does not exist, because nothing here can see it.

* **Keep the predecessor.** The original was never committed, so there was
  nothing to diff against and no way to notice for thirty-six runs. A
  superseded document costs a few kilobytes and is the only instrument
  that can audit its successor. **Done, not just recommended:** the eleven
  are preserved in `docs/original-handoff-standing-rules.md` with the
  disposition of each, and `tests/test_handoff_standing_rules.py` diffs
  this file against them, so the next rewrite drops one loudly. It is
  positive-controlled — removing a restored rule fails it by name.
* **A numbered list is a checkable artifact.** "Eleven standing rules"
  survived as a *count* in someone's memory, and the count is what made
  this audit possible. Prose loses items silently; a numbered list makes
  the loss arithmetic.

**`tests/test_handoff_rule_scope.py` cannot catch this, and it is worth
saying why rather than widening it.** That test compares statements
*within* one document and flags a prohibition that lost its condition. A
rule that exists in no statement at all has no scope to disagree with and
nothing to compare against. **Absence is not detectable from inside the
document** — it needs the predecessor, which is a diff, not a lint. The
test is correctly scoped and is not being widened.

---

## Standing rules

Some of these changed. Where they did, the old rule is named so it is not
reinstated by accident. **Four were recovered in Part 47 after being
dropped by the rewrite that created this file — see the audit above.**

**Every persistent DB path: env-var-with-fallback, and BOTH failure states
demonstrated.** *Recovered in Part 47; it was rule 1 of the original
handoff and had been missing since. **Applied in Part 51 to the one store
that was violating it.***

`USER_STORE_PATH` was unset while twelve `*_DB_PATH` variables were set
and pointing at `/data`, so the user store fell back to `users.json`
beside the source file — the container filesystem, replaced on every
deploy. Signup would have accepted an account, logged the user straight
in, and lost it at the next push, surfacing days later as "my password
stopped working". Fixed while there were zero signup users and therefore
nothing to migrate. Unset now produces a **named refusal and a visible
banner**; it no longer writes anywhere. Verify via live in-process code,
never from the Railway dashboard. A new `*_DB_PATH` must be shown failing
(unset → a visible banner naming the variable) as well as working — the
good path alone proves nothing, because **a misspelled or unset env var
fails OPEN**: `os.environ.get` does not raise, it returns the default.
That applies to test redirection too, which is the same hazard through a
different door: patch `get_db_path` rather than set a variable, because a
wrong attribute name raises where a wrong string key is silent. `mode=ro`
is the member of this family that fails CLOSED, which is why it has never
caused an incident.

**No fabricated authority.** *Recovered in Part 47; rule 5 of the
original. **Corrected in Part 50** — the Part 47 recovery was written from
a quotation and restored a DIFFERENT rule than the one the original
carries.*

The original, verbatim: *"Any number/threshold not confirmed by Michelle
or a real cited source ships with an explicit, **test-enforced** 'not
confirmed' disclaimer (established pattern: `deal_readiness_defaults.py`,
reused in Quick Deal Analyzer's grading and Site DD's cost table)."*

That is a **mechanism**, not a principle, and it is live:
`deal_readiness_defaults.py` carries
`REQUIRED_DISCLAIMER_PHRASE = "not confirmed"` and
`tests/test_deal_readiness.py` enforces it. The Part 47 version — "never
present a number as established unless it was read from the thing itself"
— is a reasonable rule that this session repeatedly earned, but it is not
this one. It forbids asserting; the original permits shipping an
unconfirmed number **provided the page says so and a test makes it say
so**. Both are kept: the original because it is the rule and has an
implementation, the paraphrase because the RentCast `bedrooms` parameter,
the `to_capex_lines` glob, the Jinja `Undefined` claim and
`normalize_month` were each asserted confidently and each was wrong.

**When the instruction is wrong or stale, say so and propose the right
thing rather than building what was asked.** *Recovered in Part 47; rule 9
of the original.* Practised constantly and written down nowhere: three
consecutive briefs carried a false premise and each was reported rather
than built around.

**Reachability is not correctness.** *Framing recovered in Part 47; rule
10 of the original.* Five features shipped correct, tested and
unreachable. Passing tests say a thing works, never that anyone can get to
it. The two sweeps and "verify by navigating, not by driving URLs" below
are the enforcement; this is the sentence that says why they exist.

**Merge discipline.** Investigate → report → build → report before
merging → merge only on explicit go-ahead → deploy → verify on production
→ report. One merge at a time; never chain. Report each part separately.
**Never combine build-and-merge into one silent action** — *restored in
Part 50; rule 8 of the original carried this clause and the Part 47
recovery dropped it.*

**Verification is by behaviour, not by file hash.** *This replaced the
old rule.* `deal_analyzer_math.py` used to be checked by byte-hash — but
a branch that legitimately adds a function will always fail that, and it
proves nothing about behaviour. The current approach is a **two-signal
fingerprint matrix**: a behaviour hash over the *intersection* of keys
present on both sides, plus a schema diff reported separately and never
hashed. The one-signal version reported divergence on four scenarios in
which not a single pre-existing value had changed.

**Every comparator gets a positive control before it is trusted.** An
instrument that has never returned a difference has not been tested. This
is not optional and it has caught real defects:

- The first dead-reader sweep matched `name(` as text and was **satisfied
  by a prose comment** mentioning `list_updates()` — a checker reporting
  safety it never established. It now walks the AST.
- The first route sweep matched `url_for` only and produced **two false
  positives** (`/manifest.json`, `/service-worker.js`) in its first six
  results.

**Reachability is enforced by two sweeps, not by discipline.** *This is
new.* Four separate features shipped correct, tested and invisible:
`feedback_db.list_feedback()`, `notes_db.list_updates()`, the notetaker
itself, and the Site DD capex export. `tests/test_dead_readers.py`
requires every public reader in `tools/*_db.py` to have a caller outside
its own module and outside tests. `tests/test_route_reachability.py`
requires every GET route to be referenced by a template. Both carry
allowlists with **a written reason per entry**, and both self-check for
stale entries.

**Verify by navigating, not by driving URLs.** Every one of the four
invisible features passed its own tests. Harvest hrefs from rendered HTML
and follow them.

**Production data, and FULL-COLLECTION-REWRITE ROUTES ARE DANGEROUS.**
*Rule 2 of the original handoff, restored to full weight in Part 47.*

Read-only means `mode=ro`. **Always snapshot before a real production
write**, and verify restoration by **content fingerprint, not file hash** —
SQLite page reuse changes the file hash after an insert-then-delete even
when the content is identical.

`save_area`, `save_expenses`, `save_capex`, `replace_expense_lines` and
`replace_loans` **silently blank anything a POST does not include**.
**Always post complete forms.** This rule exists because production data
was lost and recovered, more than once — that sentence was dropped in the
rewrite and it is the reason the rule is obeyed rather than noted.

Re-checked against the code in Part 47 and **the hazard is live**,
demonstrated by running it: `save_area` with a complete POST leaves a
stored answer as `good`; with the item merely absent it becomes `None`,
because `_posted_instances()` returns `{1} ∪ existing ∪ posted` and so
emits instance 1 of every catalogue item whether the form mentioned it or
not. `replace_expense_lines` and `replace_loans` are both still literal
`DELETE … INSERT` — the first ALSO reassigns line IDs on every save, which
is a second consequence and not the main one.

**One route has since grown a defence, and it is the model:**
`save_expenses` carries acquisition-cost lines through untouched because
they are edited by a different form, its comment noting that reading them
from that request "would find nothing and silently blank every amount".
Somebody hit this there and fixed it there.

**Do not read "no incident lately" as "hazard gone".** We have barely
written to production.

**AND THE LIST OF FOUR IS NOT THE SCOPE.** *Restored in Part 50 — the
Part 47 recovery dropped this clause, and the Part 47 audit then checked
exactly the four named routes as though they were the rule.* The original
ends: *"assume it applies to **any route not yet audited**."* The four are
examples of a pattern, not an enumeration of it. Any route that rebuilds a
collection from a form is in scope until someone has looked at it.

**Money — for every metered third-party call, not just OpenAI.** *Rule 7
of the original, which named OpenAI only; the shape has since generalised
and the rule is stated generally.* A shared cap, a per-feature counter,
confirm-before-spend, and cache the result so a re-view costs nothing.
OpenAI runs against a shared **$60/month** budget and was overspent once
(2 calls instead of 1). RentCast runs against **50 lookups/month** with
the same machinery: a usage gate that refuses at cap independently of the
disabled button, and a confirmation naming the call and the running count
before any re-spend.

**No scraping — and here is what that does and does not cover.** *Narrowed
in Part 41; it previously read "Michelle explicitly does not want
scraping" with no domain, which is broader than anything it was ever
argued from.*

**What it forbids:** building the reference cost table by scraping
contractor-pricing or listing sites. That is Michelle's explicit
instruction, and `site_dd_reference_costs.py` is built to make it
structurally impossible — "no client, no scheduled fetch, and no retailer
is queried at runtime or at any other time … it has no imports that could
reach a network." The 36 figures are a one-time manual research pass over
published contractor-estimate sources (Angi, HomeGuide, HomeAdvisor, Fixr,
Homewyse, This Old House).

There is a second, separate finding of the same shape, about a different
site: **city-data.com** was the originally suggested source for market
demographics and its terms exclude *"any use of data mining, robots,
spiders, or similar data gathering and extraction tools"* for commercial
or derivative use. `underwriting_market.py` records that scraping it would
be "both fragile and a term we would be breaking", and FIRE Metrics
already covers the same ground from documented government sources.

**What it does NOT forbid: licensed data APIs.** This app already makes
routine automated external calls — RentCast and Google Places — and
nobody has ever treated them as violations, because they are not
violations. `market_data_service.py` draws the line in as many words:
RentCast is a *"real public REST API, sourced from public
records/listings — not scraping"*, and Google Places is the official API.

**So a paid cost-data API is the direct answer to the reference-cost
problem, not a breach of her instruction.** RSMeans is the named
candidate — not in this file until now, but in the code, at
`site_dd_costs.py:11` and `site_dd_db.py:124`, both of which record the
reference table as "gated on the decision between Michelle's numbers,
RSMeans and disclaimed placeholders". Reading the old one-line rule as
"no automated external cost data, ever" would have ruled out the one
option most likely to solve the problem.

**Units differ by layer, and this produced a wrong run.**
`analyze_noi_series` takes `interest_rate_pct=6.5` (**percent**);
`monthly_payment` / `remaining_balance` / `annual_debt_service_series`
take `0.065` (**decimal**). Passing percent where decimal was wanted
produced $13,000,000 of annual debt service on a $2M loan.

---

## Paresh's inspection forms exist, and the previous handoff said they did not

**The correction.** An earlier handoff recorded that Paresh could not
provide his inspection script or form, and that **no reference
implementation had ever existed**. That is false. On 2026-08-18 he sent
four mature production instruments, in real use before our rebuild:

| file | what it is |
|---|---|
| `The_View_Inspection_XLSForm_v7.xlsx` | KoboToolbox unit inspection, 344 survey rows, 35 choice lists |
| `The_View_Building_Exterior_Inspection_v5.xlsx` | exterior inspection, 672 survey rows |
| `rent_roll.csv` | 84 units, bed/bath **pre-derived** into separate columns |
| `property_config.csv` | 3 rows of per-property settings driving question relevance |

**That entry was load-bearing: it is why Site DD was rebuilt from
scratch.** The rebuild happened without them, and the rebuilt tool is not
wrong -- its repeatable-items design is structurally better than the
exterior form's 672 hardcoded rows, where a four-floor building needs a
whole new form. But the checklist *content* in those files is mature in
ways ours is not, and none of it informed the rebuild.

Version numbers are the tell we missed: **v7 and v5**. Those are not
drafts. Somebody iterated on them in production for a long time.

Files are in the user's Downloads folder as of 2026-08-18. **Get them
into durable storage** -- a Downloads folder is not where the only copy
of a reference instrument should live.

---

## THE STANDING RULE THIS SESSION EARNED

**Check the premise against the code before scoping anything.**

Three separate things were treated as blockers, in some cases for
several rounds, and each cost nothing once somebody actually looked:

| assumed blocker | reality |
|---|---|
| Notetaker section changes cost real OpenAI spend | Production had **zero** transcripts and zero updates. Nothing cached, nothing to regenerate. The bump was free. |
| `underwriting_scenarios` needs a `deal_id` migration | It **already had one**, in the base schema, with an index, NULL on all ten rows. |
| A Site DD rent-roll upload needs a new parser | The existing ResMan parser already returns all 152 Oxford Pointe units correctly. It only cannot **open** `.xls`. |
| Paresh could not provide his inspection form; no reference implementation ever existed | He sent four, on being asked. v7 and v5, in production use. **Nobody re-asked for eight months.** |

The first three needed one query or one grep apiece. The fourth needed an
email. The pattern is that a plausible-sounding claim hardens into a fact
the moment it is written down, and nobody re-checks it because it already
sounds settled.

**THE SHARPENED FORM: an unavailable resource is worth re-asking for, not
just re-checking in the code.**

The first three were premises about our own code, and a grep settles
those. The fourth was a premise about a **person** -- what somebody could
or would provide -- and no amount of reading the codebase could ever have
falsified it. It stayed true-sounding for eight months and it caused a
from-scratch rebuild.

Availability is a fact about a moment, not a property of a resource.
People find files, change jobs, change their minds, or were asked
badly the first time. When a "cannot be obtained" is load-bearing --
when it is the reason something is being built the hard way -- re-ask
before committing to the expensive path.

Two false premises earlier in the same session -- see below -- came from
exactly the same mechanism, and they cost investigation time rather than
just delay.

So: before scoping, estimating, or declining anything, spend the one
minute it takes to check it against the code. Especially when the claim
came from a previous handoff, and especially when it is the reason
something is not being done.

---

## Premises that turned out to be false

These came from confident statements in a previous handoff, in briefing
text, or -- in the fourth case -- from one of our own reports. Every one
cost investigation time. **Check premises against the code**, and where
the premise is about a checker we wrote, run the checker.

1. *"Quick Deal Analyzer shares `deal_analyzer_math`."* It does not.
   `quick_analyzer_math.py` imports only stdlib; every mention of
   `deal_analyzer_math` in it is docstring prose, including the line
   "deal_analyzer_math.py is not imported here." The only live caller of
   `analyze_noi_series()` is `underwriting_math.py`.

2. *"The bedroom filter refetches and recency filters client-side, which
   is why one works and the other doesn't."*  Both are client-side and
   wired identically -- `bedsSel.addEventListener("change", apply)` and
   the same line for recency. The differential a tester observed was
   **comp-set composition**: RentCast returns comparables matched to the
   subject's size, so when it resolves the subject as a studio, all
   fifteen comps are studios and "studio" versus "all sizes" show the
   same rows. Plausible, survived the reporter's own description of the
   symptom, and died on the cached data.

3. *"Site DD has PDF export only; no XLSX path exists anywhere."*
   `site_dd_capex_export.build_xlsx()` had been live the whole time,
   wired to `/tools/site-dd/assessment/<id>/capex.<fmt>`, already
   satisfying every requirement that was being specified as if new. The
   real defect was that nothing linked to it.

4. *"Widening the dead-reader sweep's `tools/*_db.py` glob would have
   caught `to_capex_lines()`."* **It would not.** The sweep is gated on
   **two** things and only one of them is the glob:

   ```
   READER_PREFIXES = ('list_', 'get_', 'fetch_', 'find_', 'count_',
                      'search_', 'load_', 'read_')
   ```

   `to_capex_lines` begins with `to_`, so it fails the prefix gate
   wherever it lives. Catching it needs the prefix list widened too,
   which is a different and much noisier instrument -- measured in
   `docs/site-dd-to-capex-lines.md` at 81 hits, 54 of them
   framework-dispatched routes.

   **This one is worth more than the other three, because of how it
   propagated.** It was asserted in a Part 31 report, repeated back in
   the Part 35 prompt as settled, and acted on as the premise for a
   piece of work. Neither side checked the mechanism. A claim that
   travels from a report into a prompt and back has been *confirmed by
   repetition*, which is not confirmation at all -- and it is the same
   failure as the RentCast disclosure, where four cached addresses
   agreeing stood in for checking all seven.

   The rule that catches this one is narrower than "check premises
   against the code", because the premise here was about **our own
   instrument**: *before claiming a checker would or would not have
   caught something, run it.* It takes one command.

5. *"`area_status_labels[st]` raises on an unknown key."* **It does not.**
   This app runs Jinja's **default `Undefined`**, so a missing key
   renders as the **empty string**:

   ```
   status=occupied           subscript=' &middot; Occupied'
   status=vacant_not_ready   subscript=' &middot; '          <- dangling
   status=None               subscript=''
   ```

   The accessor was still the right change, for a worse reason than the
   one given: silent, not loud. An unrecognised value produces a dangling
   separator and leaves no trace that anything was wrong, where
   `area_status_label()` answers "Not stated". Note the NULL case, which
   was the one flagged as the live hazard, is **not** the hazard at all --
   both display sites are guarded by `{% if area.status %}` and render
   nothing either way. The hazard is a non-NULL value from an older
   vocabulary, which is exactly what widening AREA_STATUSES would
   introduce.

   Both behaviours are now pinned in
   `tests/test_area_status_labels.py`, so configuring Jinja with
   `StrictUndefined` fails a test rather than silently invalidating a
   docstring.

   **Same propagation path as #4, one run later.** Asserted in a Part 35
   report, restated in the Part 36 prompt as the reason to do the work,
   acted on by both sides. Nobody rendered a template.

**Four of these five share one shape: a claim about a MECHANISM -- a
parser, a checker, a template engine -- believed rather than executed.**
The rule from #4 covers all of them and is worth reading as general:
*before claiming what a mechanism does, run it.* Every one of these cost
more to discover than the single command that would have settled it.

A claim that travels from a report into a prompt and back has been
**confirmed by repetition**, which is not confirmation. When a prompt
states one of our own findings back as settled, that is the moment it is
least likely to be re-checked and most likely to be wrong.

### 6. An APPROVAL can outlive its premise, and nothing expires it

*"Normalize at entry — canonicalise the address when a deal is created or
edited."* Approved in Part 23, restated in prompts, **unbuilt for fifteen
runs**, and investigated properly for the first time in Part 38. It is
aimed at a code path the problem does not use.

The duplicate rows came from the **Rent Comps standalone search box**,
which takes a free-text address whenever no `deal_id` is supplied.
Production has two deals; neither is Steiner or Belvedere, and **ten of
twelve cached rows correspond to no deal at all**. A canonicaliser on
`new_deal()` / `edit_deal()` would have run **zero times** against the
addresses that actually collided — and could not have merged them anyway,
since they differ by the street-type suffix that the same decision
correctly ruled out.

**This is a different failure from the five above.** Those are false
*claims*, and the fix is to run the mechanism. This is a false *plan*: the
reasoning that produced it was sound, the constraint it protects is still
right, and the decision was never wrong when made — it was aimed using a
premise about where the data comes from that nobody had checked.

An approval is the most durable thing in a handoff. It reads as settled,
it carries the authority of having been decided, and unlike a claim it
invites no re-examination at all — the question feels closed. It sat
through fifteen runs precisely *because* it was approved.

**The rule: when an approved-but-unbuilt item finally comes up to build,
re-derive what it is aimed at before building it.** Not whether it is a
good idea — that was settled — but whether the thing it targets is the
thing that is broken. The check here was one query against the deals
table, and it retired most of a plan that had been carried for fifteen
runs.

---

## A rule stated twice loses its condition in the shorter statement

Part 40 audited every standing rule in this file against one question: *is
it recorded at the scope its argument actually supports, or at a broader
scope that happens to contain it?* That question came from
`normalize_address_key`, where a conclusion about **street suffixes** was
written down as a prohibition on **the whole function** and blocked a safe,
unrelated fix for fifteen runs.

The audit found one more instance, and it turned out to be a sharper
pattern than "rules drift broad".

**Entrata was in this file twice, at two different scopes.** *Revised cost
estimates* said: "Do not scope it until a sample exists — the Oxford
Pointe experience is the argument." *Open operational items* said: "Do not
start the Entrata parser seam." Same file, same decision. The long version
carried the condition, the reason and the exit criterion. The short version
carried none of them.

**The mechanism is not drift. It is compression.** Nobody rewrote the
Entrata rule to be stricter. Someone summarised it, and a summary keeps the
imperative because that is the actionable part — while the condition, the
reason and the exit criterion are the parts that read as background and get
dropped for length. What survives compression is the *prohibition*, and
what is lost is everything that says *when it stops applying*.

That is why this is worse than ordinary staleness. A rule with no exit
criterion cannot expire, because there is nothing written down that would
tell you it had. It just keeps being true-looking.

**And the short version is the dangerous one, because of where it lives.**
*Open operational items* is a list you read when deciding what to do next.
*Revised cost estimates* is prose you read when you already care about
Entrata. The stripped statement sits in the higher-traffic place and is the
one that actually steers a decision. Same for the scraping rule: the
one-line form under **Money** is where anyone looks, and it had no domain
at all.

**This is checkable rather than merely rememberable, which is the useful
part.** The check is mechanical:

> **Where a rule appears in both a discussion and a summary, re-read the
> summary.** If the summary states a prohibition without its condition,
> that is the statement to fix — not the discussion, which is already
> right.

Both narrowings in Part 41 now cross-reference each other, so a future edit
to one has a pointer to the other.

**How much of this a test can actually carry, measured rather than
assumed.** `tests/test_handoff_rule_scope.py` guards the Entrata rule and
fails if either statement of it is re-stripped. It guards **only** that
one, and the file records why at length:

- **The discovery version does not work.** Three designs were built and
  measured against a HANDOFF known to be correct; all three produced
  **100% false positives**, and the first also *failed its positive
  control* — clustering on the words inside each imperative could not
  match "Do not start the Entrata parser seam" to "Do not scope it until
  a sample exists", because the long form says "it". The root cause is
  linguistic, not tuning: of 16 uses of "never" in this file, **13 are
  descriptive** ("never shipped", "never exercised"). Separating a rule
  from a sentence about the past is a judgment, and a regex attempting it
  flags prose.
- **Scraping is deliberately not registered.** Entrata's qualifier is a
  **condition**, and condition words are a closed lexical class, so a
  missing one is detectable. Scraping's qualifier is a **domain**, and it
  is not: the original bare rule said "reference costs are a one-time
  manual research pass", so any pattern loose enough to accept the
  narrowed rule also accepts the original. Making its control fire would
  have meant tuning the pattern until two known strings landed right,
  which is fitting an instrument to its test cases.

So the convention below is the real protection, and the test holds the
line only where a machine can honestly tell the difference. That is the
same trade as the dead-reader glob: the noisy half refused, the narrow
half kept.

**When writing a rule in a summary: carry its condition, or link the full
statement.** An imperative alone is not a shorter version of a conditional
rule. It is a different and stricter rule.

### The three that were left broad on purpose

The same audit found three rules stated more broadly than their evidence,
and **they were deliberately not narrowed**. Recording that is part of the
result, because otherwise the next audit re-finds them and someone
"corrects" them:

| rule | evidence | why it stays broad |
|---|---|---|
| *"guard the container, not the number"* | the falsy-zero audit found exactly **one** real member in 53 | the broad form costs nothing and prevents the next instance. Prophylaxis at zero cost is a fair trade. |
| *"verification is by behaviour, not by file hash"* | generalised from one code module under change | a file hash is still right for an uploaded artefact or a vendored dependency, but nothing is being blocked |
| *"verify by navigating, not by driving URLs"* | four features that passed their own tests while unreachable | the evidence is about **reachability**; the wording reads wider, and in practice it is applied correctly |

**A rule broader than its argument is only a defect when the extra scope
forbids something valuable.** That is the test that separates these three
from `normalize_address_key` and Entrata. All three cost nothing today; the
other two blocked real work.

---

## The falsy-zero audit: one member IN TEMPLATES, and the convention it implies

> **THE SCOPE WAS NARROWER THAN THIS ENTRY SAID.** Corrected 2026-08-29.
>
> It reads below as though the falsy-zero *class* has one member. What
> was actually swept is **53 `or`-fallback idioms in Jinja templates plus
> 6 in Python** — display fallbacks, one idiom, mostly one language. The
> negative result is correct for that, and was wrongly recorded as a
> result about the class.
>
> **A truthiness guard on a numeric in Python is the same class through a
> different idiom, and was never in scope.** `if rate:` reading `0.0` as
> absent was found in Part 61 during unrelated work on
> `site_dd_reference_costs.for_item()`, where concrete flooring carries a
> `0.0` rate. An audit that had covered it would have found it.
>
> **The Python pass was then run, in Part 63.** See *the second sweep*
> below.

`{{ rentcast.property.bedrooms or '—' }}` rendered a **studio as unknown**,
because 0 is falsy. That looked like a class of bug, so all 53 `or`-fallback
idioms in templates plus 6 in Python were audited.

**The class has exactly one member.** Everything else is safe, and for
reasons worth recording so nobody re-runs the audit:

  * `gp.rating`, `review.rating` -- Google ratings are 1.0-5.0; absent is None
  * `crime_rating`, `climate_risk_rating` -- these are LABELS; the numerics
    are separate fields (`crime_index_score`, `climate_risk_score`)
  * `hold_years` -- `_validate()` rejects `< 1`
  * OM `property[k]` / `asking_terms[k]` -- the schema declares **every
    field `{"type": "string"}"`, deliberately, because they are verbatim
    quotes. Empty string is the real "not stated" case.
  * everything else is a date, name, note, caption, label or address

`bedrooms` was the only member because it is the one field here where
**zero is a common, real, user-facing value** -- a studio.

**THE HOUSE CONVENTION: guard the container, not the number.**

    {{ money(x) if obj else '—' }}     right -- asks "does the object exist"
    {{ x or '—' }}                     wrong for anything numeric

Every ternary in the codebase already guards the container, which is why a
genuine zero NOI still renders as `0`. Keep it that way.

### The second sweep: numeric truthiness in Python, and it came back empty

**Run 2026-08-29, AST-based, over every non-test `.py` file in the repo.**
Looked for `if <numeric>:`, `if not <numeric>:`, `x or <default>`,
short-circuiting `and`/`or` chains over numbers, `filter(None, …)` and
truthiness-based comprehensions.

**Two passes, because the first instrument was too blunt to trust.** A
name-vocabulary regex alone returned **310 hits** — it matched `value`,
`index`, `next_page`, anything. The second pass keeps a hit only when the
same name is used in **arithmetic or a numeric comparison in the same
file**, which is evidence the name is a number rather than a guess that
it is. That gave **122**.

**Of those 122, the honest count of live defects is zero.** They fall into
three groups:

| | what it is | verdict |
|---|---|---|
| **Division guards** — `(a / b) if b else …` | `b == 0` cannot be divided by | **correct.** `expense_ratio`, `noi_margin`, `per_unit`, `gap_pct`, `completion_pct`, `avg_rent`, `used_pct`, `equity_multiple`, `deduction_pct` are all this |
| **Lists and strings** — `values`, `months`, `schedule`, `amounts`, `body` | not numbers | false positives of the name filter |
| **Shortcuts whose zero branch is identical** | skipping does the same thing as running | **harmless**, checked individually |

The third group is the one worth naming, because each looked like a hit
and each had to be read rather than counted:

* `waterfall_math.py` `if pref_rate:` — a **0% preferred return** is a
  real deal structure, so this looked live. It is not: the loop it guards
  computes `round(base * pref_rate)`, which is `0` for every year, so the
  guarded and unguarded results are identical.
* `site_dd_capex_export.py` `if l["total"]:` — a `0.0` line is added to
  `by_source` and skipped for `by_category`, which is a genuine
  asymmetry. It is numerically invisible: the omitted contribution is
  `0.0`, so `priced_total` and the category breakdown still agree.
* `underwriting_math.py` `if mgmt:` — a **0% management fee** is real
  (self-managed), and `expenses += 0` is a no-op.
* `debt_service / 12 if debt_service else 0.0`, twice — an all-cash deal
  has `0`, and `0 / 12` is `0.0`.

**So `if rate:` was the only member, and it is fixed.** That is a real
negative result this time rather than a mis-scoped one — and it is worth
noting the result is the same as Part 55's while the *reason to believe
it* is completely different.

#### The mirror class, which this sweep found and was not looking for

**Twelve division guards return `0` for "cannot compute" rather than
`None`**, conflating *the ratio is zero* with *there is no ratio*:

    used_pct     = ((total - free) / total * 100) if total else 0.0
    noi_margin   = df["NOI"].sum() / income_sum   if income_sum else 0
    deduction_pct = (deductions / gpr * 100.0)    if gpr else 0.0
    avg_rent     = total_rental / occupied        if occupied else 0.0

This is falsy-zero **reversed**: not zero read as absent, but absent
reported as zero. A property with no GPR shows a 0.0% deduction rate,
which reads as *"nothing is being deducted"* rather than *"we cannot say"*
— and that is the same failure the Site DD cost work spent several runs
removing, arriving from the other direction. Several neighbouring guards
in the same files correctly return `None`, so the codebase already knows
the right answer and is inconsistent rather than wrong-headed.

**Not fixed here.** It is a separate class, it changes what numbers appear
on screens Michelle reads, and twelve call sites is its own run.




---

## Four things about specific bugs, kept because each will recur

### "Fails on one property" has been wrong four times. Check all properties first.

**Standing rule: before accepting a property-specific premise, test the
other properties.** Four instances now, all in one testing cycle:

  1. *Bedroom filter doesn't refresh* -- comp-set composition, any address
     whose comps are uniform behaves the same.
  2. *MMR prints 33 pages, "all but oxford work"* -- the stray selected tab
     differed per SOURCE FILE, not per property. ERA was clean by luck of
     how its workbook was saved. Fixing "the Oxford bug" would have fixed
     nothing.
  3. *Scorecard trend chart unlabelled for Jackson* -- any upload whose GPR
     parses as zero behaves identically.
  4. The GPR parsing bug below, same shape.

The framing is seductive because it sounds like a narrowed, tractable
problem. It usually means "this is the one the tester happened to open".

### The MMR print mechanism, because a new source workbook will hit it again

The download is the source MMR with a Summary sheet prepended, and it
inherits **whatever tabs were selected when somebody last saved the source
file**. Excel's default print option is "Print Active Sheets" -- PLURAL --
so a stray selected tab prints alongside Summary, and source sheets are
raw exports with no print area (General Ledger is 1,168 rows on OXPT).

`scope_workbook_for_print()` deselects everything but Summary and gives
each content-bearing source sheet a print area. Measured before the fix:
OXPT carried "Prospect Source Summary", Maple Valley "Cash Flow", Canyon
"Work Order Summary", ERA nothing. **The selected-tab state varies per
uploaded file**, so a new source workbook can present as a new bug.

### The address-duplicate decision: do not change the SUFFIX handling
### (the zip half of this rule was changed in Part 39, deliberately)

> **Part 38 Step B investigated this and the plan below does not survive
> the data.** The four duplicate rows came from the **Rent Comps
> standalone search box**, not from deal entry — production has two deals,
> neither of them Steiner or Belvedere, and ten of twelve cached rows
> match no deal. So "canonicalise when a deal is created or edited" would
> have run zero times against the addresses that collided, and could not
> have merged them anyway, since they differ by the street-type suffix
> that is ruled out just below. Both pairs were confirmed to hold
> equivalent data; nothing was deleted. Full write-up, including a live
> ZIP+4 cache-miss defect on deal 1, in
> `docs/address-normalize-at-entry.md`.

The cache holds separate paid rows for `24 steiner` / `24 steiner street`
and `598 belvedere` / `598 belvedere street`, because the key function only
lowercases and collapses whitespace.

**Merging them requires dropping the street-type suffix, and that collides
real addresses**: `100 Main St`, `100 Main Ave` and `100 Main Blvd` all
become `100 main`. Those coexist in real cities, and serving one street's
comps for another is far worse than four wasted calls.

Changing the key function also **orphans every existing cached row** --
they carry keys under the old function, so every lookup misses and triggers
a fresh paid call. Re-warming 12 rows to prevent 4 costs more than it
saves, immediately.

**Decision: normalize at ENTRY instead** -- canonicalise the address when a
deal is created or edited, one address at a time with a human present.
Approved, not yet built. Plus a one-off merge of the four duplicate rows.

---

**PART 39 CHANGED THE ZIP HALF OF THIS, AND THE HEADING ABOVE USED TO SAY
"do NOT change normalize_address_key".**

Both arguments above are about **street suffixes**, and both are still
right about street suffixes. They were then applied to the **zip** by
association, and there they were overbroad. `normalize_address_key` now
truncates a ZIP+4 to its ZIP5, because both objections evaluate the other
way for that case:

| | dropping a suffix | truncating a +4 |
|---|---|---|
| **collides?** | yes -- `100 Main St/Ave/Blvd` are three real streets | no -- merges only inputs identical in address, city, state and all five zip digits, which is one address |
| **orphans?** | yes -- every existing row is keyed under the old function | no -- **zero** of the twelve cached rows carries a ZIP+4, and `market_data_cache` is the only table on the volume holding an `address_key` |

It fixed a live cost: deal 1 stores `94941-1604` while its cached row was
written from a ZIP5 entry, so its key **missed its own data** and every
Rent Comps open spent a paid call on a row already in the table.

Only the key is truncated -- the `zip` column still stores whatever the
user typed, so a deliberate ZIP+4 is not discarded.

**The suffix rule stands and is now pinned by
`tests/test_address_key.py`**, which fails if anyone tries to merge
`24 Steiner` with `24 Steiner Street` that way. That is the safe place for
this decision to live: a test that fires, rather than a heading that has
to be read and believed.

**The lesson is the heading itself.** "Do NOT change
`normalize_address_key`" was a true conclusion generalised one step past
its evidence, and it then blocked an unrelated and safe fix for several
runs. A rule recorded at the level of *the function* rather than *the
transformation* forbids more than its argument supports. Write down what
the reasoning actually covers.

### Jackson's GPR: SETTLED 2026-08-24 with the real files

**This section previously said Jackson's dialect was probably unmapped and
that the fix needed the actual upload. The upload arrived. The diagnosis
was wrong, and so was the blast radius.**

`kpis.py` reads Gross Potential Rent from one account code:

    gpr = self.get_val("4110", month)

**Jackson has no GPR and cannot have one.** Its T12 is a **Beam
Properties, Inc.** export, **cash basis**, "Income Statement - 12 Month",
carrying **no account codes anywhere** — the Account Name column holds
names like "Rent Income" under a "RENTS" header. Every one of its 609
non-empty cells was searched for *gross*, *potential*, *scheduled*,
*market*, *vacancy*, *4110* and *4000*: no hits. The single "4000" match
is the float `87384.54000000001`.

A cash-basis statement records **rent received**. GPR is an **accrual**
concept. This is not an unmapped dialect; it is a different kind of
document.

Eagle Rock's is the contrast: an **Ince Property Management "Accounting
Tree Report"**, accrual, with the full hierarchy — 4110 Gross Potential
Rent, 4100 Gross Possible Rent, 4120 Loss/Gain to Old Lease, 4200
Deductions (4210/4220/4250/4260/4265), 4000 Net Rental Income. Note its
hierarchy is expressed by **which column holds the label**, not by
indentation within one column.

**THE TRAP: do not map Rent Income to 4110.** Collected rent is not gross
potential rent. Equating them makes physical occupancy compute as **100%
every month** — confidently, silently, and wrong in the direction that
flatters the asset. Same shape as the $5.75-per-sqft capex total and the
RentCast right-number-wrong-unit problem.

#### CORRECTION: "NRI reconstruction is skipped" was wrong, and was wrong when written

The old bullet read: *"NRI reconstruction is skipped — `if "4000" not in
self.accounts and gpr != 0` — so if code 4000 is also absent, NRI is not
rebuilt either."* Read the condition again: reconstruction only runs when
**4000 is absent**. **Jackson has 4000**, mapped from its "Rent Income"
line, so there is nothing to reconstruct and nothing was skipped.

Verified by running the real file through the real parser:

```
Jackson    4110 absent, 4000 PRESENT, 4220 absent
           income/expenses/NOI/expense_ratio/noi_margin  all correct
           phys_occ, econ_occ                            None
Eagle Rock 4110/4000/4220 present -> phys_occ 0.5687, econ_occ 0.4429, status ok
```

**So Jackson's income, expenses, NOI and ratios were correct the whole
time. Physical and economic occupancy are the only casualties.** The
warning card's "every other number is unaffected" was, for Jackson,
accidentally true — which is worse than being wrong, because it was
asserted without being checked.

**What the mis-scoped claim obscured is the genuinely dangerous case: a
file missing BOTH 4110 and 4000.** Then `nri` stays 0 and total income is
**understated rather than absent** — a wrong number that sums, not a blank
that is visibly missing. Confirmed on deployed code: a synthetic file with
only other income returns `total_income = 200.0` and `nri_found = False`,
where the rental income is simply gone.

**Nothing in the portfolio does that today**, which is exactly why nobody
noticed the claim was mis-scoped: it named a real hazard, attached it to
the wrong file, and no file in hand could contradict either half.
`nri_found` now carries this fact to the warnings card so the reassurance
is conditional instead of hopeful.

**Any upload whose GPR parses as zero still behaves identically.** Jackson
is the one that was tried — the fourth instance of a
reported-as-property-specific problem that was not.


---

## A month's own digits were being read as its year

**Fixed in Part 44. Latent, never fired, production clean — verified, not
assumed.**

`PnLParser.normalize_month` found the month and then ran a *fresh* search
for the year across the whole string. `(20\d{2}|\d{2})` matched the
month's own digits whenever the month was two-digit or zero-padded:

```
'5/24'    -> May 2024   correct, by luck: '5' is one digit
'10/24'   -> Oct 2010   the '10' was taken as the year
'11/24'   -> Nov 2011
'12/24'   -> Dec 2012
'06/25'   -> Jun 2006
'10/2024' -> Oct 2010   even with the year spelled out in full
```

October, November, December and every zero-padded month, misfiled by up to
a decade.

**Where it sits is why it mattered.** This is the P&L path.
`scorecard_history` is keyed `PRIMARY KEY (property_key, month)` and
`month_start` drives the trend's chronological order, so a misfiled month
writes a *different row* and sorts to a different place. It cannot collide
with the correct one, so it would never announce itself.

**BLAST RADIUS, ESTABLISHED BEFORE FIXING**

* **THE NUMERIC BRANCH WAS UNREACHABLE ACROSS ALL TWENTY REAL FILES.**
  Every P&L export in hand writes a month NAME with a four-digit year —
  `'Aug 2025'`, `'Jun 2025\nActual'`, `'Jan 2025'` — across Jackson
  (Beam), Eagle Rock and OXPT (Ince) and Canyon, in both `.xlsx` and
  converted `.csv`. All twenty parse through the month-name path; not one
  reaches the numeric branch.

  **This was a LATENT bug, not a live one, and that should decide how
  hard anyone guards it.** Nothing was ever wrong on screen, no history
  row was ever misfiled, no user ever saw a bad month. It was worth
  fixing because the cost of being wrong is high and silent, not because
  it was costing anything. So: do not build an elaborate defence around
  it, and do not go hunting for corrupted data — there is none. If an
  export family ever does arrive with `m/yy` headers,
  `tests/test_pnl_month_normalisation.py` already covers it.
* **Production history is clean.** Read read-only: 36 rows, three
  properties, every month between Aug 2025 and Jul 2026, nothing outside
  2020–2030. **So this was a code fix with no data correction behind it**,
  and no month keys were rewritten under the live history table.
* **Regression evidence:** all 20 real P&L files produce a byte-identical
  parse fingerprint before and after (`2ff8958f95c76dda`), and that
  comparator was positive-controlled — shifting every resolved year by one
  moves it.

**The fix works in tokens.** The month token is consumed, then the year is
sought in what remains, which makes digit-stealing impossible rather than
unlikely. A four-digit token can never be read as a month.

**And where a file states its own period, that now beats inference.** The
default-year fallback was *today's calendar year*, which is a guess about
the clock rather than about the document — a 2025 T12 opened in 2026 would
file every yearless column under 2026. It now prefers the range the file
declares (`'Period Range: Aug 2025 to Jul 2026'`,
`'June 2025 - May 2026 - Accrual - ...'`). This only affects files whose
columns carry no year at all, so it changes nothing for any current format.

**Still approximate, deliberately — and the condition is what decides
whether anyone should care.**

A T12 crosses a year boundary, so a *single* default year is necessarily
wrong for part of any twelve-month range: a file running Aug 2025 to Jul
2026 has five months in 2026 that a default of 2025 would misfile.

**It matters ONLY for a file whose columns carry no year at all, and no
current format does that.** All four export families — Beam, Ince, Canyon
and the converted CSVs — write the year into every column header, so the
default-year branch is never reached and the approximation never bites.
That condition is the whole point; without it this reads as a live defect
rather than a dormant one.

**The real answer, when a file finally needs it:** assign years by walking
the sequence forward from the period's start month, incrementing the year
each time the month number wraps past December — not by resolving each
column independently against one default. The period range is already
parsed into `self.period`, so the start month is available.

It is a larger change to the column-mapping path, where six call sites
share `default_year`, and it should be made against a real file that
requires it rather than speculatively.

**How it was found is the part worth keeping.** Not from a symptom —
there was none. It surfaced while building something *else* that needed to
parse `m/yy` headers, and the question "can I reuse the existing one?"
was answered by running it rather than reading it.

---

## The first false premise caught by the prompt that carried it

**The claim.** A Part 21 report recorded that RentCast's
`/avm/rent/long-term` takes no bedrooms parameter. The Part 45 brief
repeated it as settled, sourced from that report.

**It is false.** RentCast documents `propertyType`, `bedrooms`,
`bathrooms` and `squareFootage` as query parameters on that endpoint, and
is explicit about what they do: *"if provided, these values will override
any attributes that are looked up automatically."* `lookupSubjectAttributes`
defaults to true, which is why an address resolves to a single unit at
all. Corroboration that those docs describe the endpoint we actually
call: they give `compCount` a default of **15**, and every cached row in
production carries exactly 15 comparables.

This is the same propagation path as the `to_capex_lines` glob and the
Jinja `Undefined` claim — asserted in a report, restated in a prompt as
settled, and about to be acted on. **Confirmed by repetition, which is not
confirmation.**

### What made this one harmless, and it is worth copying

The brief that carried the false claim also said: *"Establish what the
endpoint actually accepts for this before designing around it — if the
override cannot be expressed as a request parameter, the feature may need
a different shape and I would rather know that before it is built than
after."*

So the premise arrived **with an instruction to check it**, and the check
took one documentation fetch. Nothing was built on the false claim. Every
earlier instance in this file cost real work precisely because the claim
arrived alone, wearing the authority of a previous report.

**THE HABIT: when repeating a claim from an earlier report, attach an
instruction to verify it.** Not a hedge, not "I think" — a specific
instruction naming what would settle it. It costs one sentence in the
prompt and it converts a load-bearing assumption into a task, which is
the difference between a premise that gets checked and one that gets
inherited.

The corollary for the receiving side: **a prompt that tells you to verify
something is telling you it is not yet known.** Treat the instruction as
the real content, not as politeness around a fact.

## A misspelled environment variable fails open

**What happened.** A test redirected the market-data cache away from the
developer's real database by setting `MARKET_CACHE_DB_PATH`. There is no
such variable — the real one is `MARKET_DATA_DB_PATH`. The redirect did
nothing, the test passed, and two rows were written into the working
copy's own `market_data_cache.db`. No quota was spent, because the network
layer was mocked, but the writes were real and had to be cleaned up.

**The mechanism is the point.** `os.environ.get(NAME, "")` with a
misspelled NAME does not raise, does not warn, and does not return
anything anomalous. It returns the default, and the default is *the real
production-shaped path*. So the failure is silent AND it fails toward the
thing you were trying to avoid touching.

**The shape that cannot fail this way is patching the function:**

```python
mock.patch.object(cache, "get_db_path", lambda: tmp)   # typo -> AttributeError
os.environ["MARKET_DATA_DB_PATH"] = str(tmp)           # typo -> silently the default
```

A wrong attribute name raises immediately; a wrong string key is
indistinguishable from an unset one.

**Verified rather than reasoned:** rerunning the fixed tests leaves the
local cache row count unchanged, where the env-var version added two rows
per run. That is the check — *count the rows in the file you were trying
not to write to* — and it is cheap enough to be routine.

### This extends the positive-control rule, not a rule about DB paths

The Part 46 brief said "Standing rule 1 already demands both failure
states be demonstrated for production DB paths". **No such rule exists in
this file**, and the phrase appears nowhere in the repo — the only "fails
open" text was the line written into the test the day before. Recorded so
the reference is not inherited as real.

The rule this genuinely belongs under is the one that does exist:
**every comparator gets a positive control before it is trusted — an
instrument that has never returned a difference has not been tested.** A
test-isolation redirect is an instrument in exactly that sense, and it had
never been shown to redirect anything. Extended, it reads:

> **An isolation mechanism gets the same positive control as a
> comparator.** Before trusting that a test writes somewhere harmless,
> demonstrate that the real target does not change — and prefer a form
> whose misuse raises over one whose misuse silently returns the default.

`mode=ro` is the production-side member of the same family and is already
recorded under *Production data*: it fails CLOSED, raising on a write
attempt, which is why it has never caused an incident.

### The eighth, and the only one caught by accident

**`item.get("kind")` returns `None` for twenty of the fifty-nine
catalogue items, so a partition check written against it examined 39 of 89
definitions and reported success.**

Part 62 needed to confirm the claim underneath the detail-values design:
that no item key writes `detail` under two meanings, because `kind`
partitions the item set. The check was one loop over `every_item()`
asking each item its `kind`. It printed *"item keys with more than one
kind: none"* — the answer the design predicted, from a third of the data.

**The catalogue is assembled from three sources and they do not agree on
the field name.** Room and unit checklist items carry `kind`; the twenty
**item-bank** entries carry **`default_kind`**. `every_item()` merges them
deliberately — its docstring explains that bank items are shaped like
checklist items so a bank washer/dryer is judged by the same rule as the
laundry checklist's — but "shaped like" stops one field short.

**It surfaced by luck.** The next line sorted the results, and sorting
`None` against a string raises. Without that `TypeError` the vacuous
answer would have been the answer, and it happened to be the same answer
the correct check gives — so nothing downstream would ever have
contradicted it.

Re-run properly on the *effective* kind across all four sources, the real
result was **not** what the design claimed: `pest_evidence` is
`KIND_CHOICE` in nine room checklists and a condition item in the property
checklist. Harmless — property scope never writes `detail` — but the
design's stated claim was false and is now corrected to the weaker one
that is true.

#### The general form

**A catalogue assembled from several sources with different key names
will silently answer a question about one source as though it covered all
of them.** The failure is not a wrong answer; it is a right-looking answer
computed over a subset, and the subset is invisible because the missing
rows return `None` rather than raising.

#### The check that would have caught it deliberately

**Assert the population size before asserting anything about its
contents.**

    self.assertGreater(len(defs), 80)          # keys
    self.assertGreater(total, 150)             # definitions
    self.assertEqual(sources, {"room", "unit", "bank", "property"})

Three lines, and they run before the partition assertion. **A partition
check over 39 of 89 definitions is not a partition check**, and no amount
of care in the comparison itself would have revealed that. This is the
counting equivalent of the positive-control rule above: an instrument that
has never been shown to *see* its whole input has not been tested, in the
same way that one which has never returned a difference has not been.

Pinned in `tests/test_sitedd_scope_details.py`, with its own control —
dropping the bank source from the population makes the size assertion
fail, which is what makes it an instrument rather than a comment.

#### Eight this session, and this is the first found by accident

The others were all caught by a control that was there on purpose: the
dead-reader sweep satisfied by a prose comment, the route sweep's two
false positives, `assertFalse(x and False)`, the length-threshold check
that broke on an 11-character string, `calls == [2]` asserted after three
calls, the `MARKET_CACHE_DB_PATH` redirect that never redirected, and the
Part 60 bisect that counted a module's own unrelated failure as a
reproduction.

**That one was caught because the instrument was checked. This one was
caught because sorting raised.** The difference is worth keeping in view:
seven were a discipline working, and the eighth was a `TypeError` doing a
control's job.



---

## Two claims that nothing visible could have contradicted

These belong together. One is ours, one came from a prompt, and both would
have shipped because the world offered no symptom either way.

**1. "Every other number is unaffected" — accidentally true.** Recorded
above. Asserted without being checked, and for Jackson it happened to
land, because 4000 was present. A false claim that fails loudly is cheap;
a claim that is right for the wrong reason teaches nothing and gets reused.

**2. "Where ours cannot be computed, as with Jackson, hers is the only
figure available" — false for Jackson specifically.** From the Part 43
brief. Michelle's T12 KPIs sheet covers **5/24 – 12/24**; Jackson's P&L
covers **Aug 2025 – Jul 2026**. **Zero months in common.** Hers was not
the only figure available; it was not a figure about those months at all.

Built as briefed, it would have put a plausible number from the wrong year
under a Jackson heading, next to a Jackson P&L, labelled as Jackson's
occupancy. Around 50-60% either way — nothing about it would have looked
wrong, and the person best placed to catch it is the one whose workbook it
came from, who would have had every reason to trust it.

**The shared shape: an availability claim about two datasets, made without
checking that they describe the same thing.** "We have a figure for X" and
"we have a figure that applies to X" are different statements, and the gap
between them is invisible until someone lines the periods up. Neither claim
had a symptom: no error, no blank, no contradiction on the page.

**The check is the same one both times, and it is mechanical: before
pairing two sources, confirm they cover the same keys.** Not that both
exist, not that both are about the same property — that the specific rows
you are about to put side by side describe the same period. It cost one
comparison of two header lists.

`align_stated_occupancy()` now enforces exactly this, and the card says
"No months in common" rather than showing anything, which is the form the
brief should have taken.

---

## Michelle's occupancy figures are not a substitute for ours

Both Scorecard workbooks carry a **T12 KPIs** sheet stating *Physical
occupancy* and *Economic Occupancy* per month, computed by Michelle's own
template. Scorecard Pro has never read them: the scorecard upload feeds
only `ScorecardTargetParser` (which extracts Income, Expenses and NOI —
the word "occupancy" appears nowhere in `parsing.py`) and
`ScorecardUpdater`, which writes P&L data *into* the workbook. Occupancy
is recomputed from a GPR that, for Jackson, does not exist.

**Somebody will find her numbers sitting unread and "fix" it by reading
them. Four reasons that is not a drop-in substitute, all verified.**

**1. Neither workbook actually computes physical occupancy.** Eagle Rock's
values are static numbers. Jackson's *Economic* Occupancy cells are Google
Sheets `IMPORTRANGE` formulas pointing at an external spreadsheet, wrapped
in `IFERROR(..., <cached value>)`. The definition lives outside the file
in both cases, so nothing in the workbook says what "physical occupancy"
means here.

**2. We can only ever read a stale cache.** Excel cannot evaluate
`IMPORTRANGE`, so the cached value openpyxl returns *is* the `IFERROR`
fallback — checked to full precision on three cells, identical every time
(`0.818502203898756`, `0.775209985453521`, `0.705534337730499`). A number
read this way is a snapshot of whenever the sheet last refreshed in Google
Sheets, and nothing in the file says when that was.

**3. They disagree with ours, and are probably a different metric.** On
the one month where Eagle Rock's sheet and its P&L overlap (6/25): hers
**0.6044 / 0.5419**, ours **0.5687 / 0.4429**. Ours is dollar-weighted —
`1 - |vacancy loss| / GPR` and `NRI / GPR`. Hers is most likely unit-based
(occupied units / total units), which is the textbook definition and a
genuinely different quantity. Neither is wrong; they are not the same
measurement.

**4. THE PERIODS DO NOT MATCH, and this is the one that bites.** The T12
KPIs sheet is a snapshot, not something regenerated per upload. Its month
headers are **plain text** (`'5/24'`, number format `@`), so they are not
dates and will not coerce:

| | T12 KPIs sheet covers | the P&L it shipped with |
|---|---|---|
| **Jackson** | 5/24 – 12/24 (8 months) | Aug 2025 – Jul 2026 |
| **Eagle Rock** | 10/24 – 9/25 (12 months) | Jun 2025 – May 2026 |

**Jackson overlaps by zero months.** So "where ours cannot be computed,
hers is the only figure available" is false for the very property that
raised the question — hers is for a different year entirely, and showing
it beside a Jackson P&L would read as Jackson's occupancy for months it
does not describe. Eagle Rock overlaps on four.

**The rule: align by month or show nothing.** Never by position, never by
"the workbook is for this property so the numbers are for this period".

## A test that greps source must strip comments first

Second instance, same root cause, and now cheap enough to state as a rule.

The first: the original dead-reader sweep matched `name(` as text and was
**satisfied by a prose comment** mentioning `list_updates()` — a checker
reporting safety it never established. It now walks the AST.

The second, Part 42: `test_scorecard_missing_gpr_warning` asserts the card
no longer says *"This file does not state Gross Potential Rent"*. It
failed on a template where that string appears **only inside the comment
explaining why the wording was changed**. Part 41 hit the same shape from
the other direction, where the HANDOFF rule-scope check flagged a section
that quoted stripped rules as examples.

**The mechanism is not coincidence, which is why it recurs: the person
documenting a change quotes the thing being changed.** A careful comment
about a removed string is the single most likely place for that string to
survive, so "assert the old wording is gone" and "explain why the old
wording went" collide by construction — and the better the comment, the
more certainly they collide.

**The rule: strip comments before grepping source, and prefer a syntactic
strip to a clever pattern.** A `//` or `#` line is a syntactic category
and removing it is exact; deciding whether prose *discusses* a string
rather than *states* it is a judgment, and Part 41 measured that judgment
at 100% false positives when attempted with a regex. Where the language
allows, walk the AST instead — that is what the dead-reader sweep does now
and why it stopped being fooled.

---

## A claim that holds across the sample you have is not established

Three instances this session, all the same shape: someone reasons to a
plausible mechanism, checks it against the cases that prompted the
question, finds agreement, and ships it as fact.

  1. **The refetch-versus-filter hypothesis.** Both rent-comp selects are
     client-side and wired identically. The hypothesis survived the
     reporter's own description of the symptom and died on the cached data.
  2. **Scorecard Pro's warnings card** asserts *"this file does not state
     Gross Potential Rent"*. What the code knows is that **nothing matched
     account code 4110** -- and the parser carries several account
     dialects, so those are different claims. It also promises "every
     other number is unaffected" while NRI reconstruction is skipped.
  3. **The RentCast subject disclosure**, which we wrote ourselves *one
     step after* flagging (2). It asserted comparables are matched to the
     subject's size, inferred from four cached addresses where it held.
     False on three of the seven we had: Lubbock 2 of 15, both Belvedere
     rows 3 of 15.

**The rule: check the claim against every case you have, not the ones
that prompted it.** Seven addresses were sitting in the cache the whole
time; looking at four of them is what shipped a false statement to a real
user.

### A proxy that looks decisive: comp-set identity is NOT same-address

Part 38, deciding whether two cached rows were genuine duplicates. The
obvious test is whether they carry the same comparables. It is worthless:

```
22 Steiner St  VS  24 Steiner   ->  same comp set: True, overlap 15 of 15
                                    same rent estimate, same range
                                    same distances to FOUR decimals
```

**Two different buildings, indistinguishable in the cache.** RentCast
resolved no subject property for either, so both got the same area-level
sample — and where it resolves no subject, comparables are not matched to
the subject at all. Every address on that block gets the same fifteen.

So an identical comp set is evidence of *proximity*, not identity, and it
is exactly the kind of proxy worth distrusting: high-dimensional
(15 addresses, prices, distances), expensive-looking, and intuitively
conclusive — fifteen identical records *feels* like proof. The real
discriminators are the **subject resolution** and the **rent estimate**.

**It was caught only by a positive control, and the control fired on the
second try.** The first comparator keyed comparables on `id`; there is no
`id` field in a cached comparable, so every `.get("id")` returned `None`
and the check compared `[None] * 15` against itself. It would have called
two unrelated comp sets identical. Re-keyed on `address` it ran correctly
— and then the control against a known-different address *failed*, which
is what exposed the proxy.

Two lessons, and the second is the one that generalises: **a comparator
keyed on a field that does not exist reports agreement, not an error** —
so assert the key is present before trusting the comparison. And a
positive control is not only a test of the instrument; **when it fails it
is sometimes telling you the signal itself is not discriminative.**

The corollary for messages specifically: **a page may only state what it
can count.** If the composition is in the DOM or the payload, compute the
sentence from it. If the cause is genuinely unknown, say what is missing
rather than why.

### The audit that found it

Five honest-incompleteness messages were checked against what the code
establishes. Four are sound: the capex three-bucket sentence (it counts
`is_rate and unit_cost is not None` versus `unit_cost is None`), "cost
entered, unit not specified" (cost exists, unit is None, and the
magnitude hint is explicitly labelled a hint), the unpriced-item reasons
(human-authored claims about the world that do not pretend to be derived),
and the capex "whole **recorded** budget" phrasing, which is carefully
qualified.

The fifth was the RentCast disclosure, now fixed.

One message is sound but **prescribes an action nobody will take**:
"Needs a measured floor area before it can be totalled." Michelle's answer
-- *"don't worry about calculating paint, we just need to determine the
conditions"* -- means no measurement will ever be recorded. The
"condition-only, priced by scope" rewording is queued and now has two
reasons.

---

## Uncommitted work reported as a branch, twice

**Before reporting a branch as ready, verify it exists at the claimed SHA:
`git log -1 <branch>` plus `git status --porcelain` for a clean tree.**

Twice this session a report said "built and verified on branch X" when the
work was sitting **uncommitted in the working tree** and the branch pointed
at master's head:

  * `sitedd-checklist-gaps` (Part 21) -- caught at the start of the next
    run, which opened by committing it.
  * `scorecard-trend-labels` (Part 26) -- caught only when `git merge`
    answered "Already up to date."

Nothing was lost either time, but the reports claimed a durability they
did not have, and a context-limited session ending on that claim is
exactly how work does get lost. Tests passing is not evidence the work is
committed.


---

## Things that are true and easy to lose

**`SOURCE_SITE_DD` is dead code, and it is the model for how to leave
one.** `underwriting_capex.py` defines it and `summarize()` counts it,
and **nothing writes it**. Its own comment says it is "the reserved value
for rows Site DD's repair list will one day write" -- and that sentence is
the entire reason its status was recoverable. Production holds 4 capex
lines, all `source='manual'`. Consequence, verified: **Site DD capex does
not reach Underwriting**, so the rate bug never touched equity, IRR or
equity multiple. It wants an implementation, not a cleanup: see the
waiting-half convention below.

---

## Dead paths: five found, four different ways, and the convention that follows

**Five features have shipped correct, tested and unreachable:**

| | found by |
|---|---|
| `feedback_db.list_feedback()` | the dead-reader sweep |
| `notes_db.list_updates()` | the dead-reader sweep |
| the notetaker itself | a navigation check -- the sweep cannot see a self-referential cluster |
| the Site DD capex exports | looking for links from the detail page |
| `site_dd_costs.to_capex_lines()` | an investigation, Part 35 |

**Four different means. A sixth instrument is not the lesson.**

That was measured rather than assumed. The candidate sweep -- *a public
module-level function called nowhere in production, not even by its own
module* -- yields **81 hits**, of which **54 are Flask route handlers**
the framework dispatches and `test_route_reachability` already covers,
leaving **27** real candidates. Triaged:

| | |
|---|---|
| legitimate public API, uncalled today | 11 |
| symmetric CRUD accessors | 4 |
| internal helpers of one large module | 7 |
| genuinely superseded leftovers | 3 -- **deleted** |
| real unfinished work | 1 -- `to_capex_lines` |

**None of the 27 concealed a feature.** That is the number that decides
it. `list_feedback` and `list_updates` were different in kind: each was a
working feature with no way in, so a person lost something every day.
Nothing in the 27 is costing anyone anything. A sweep producing 27
entries needing 27 written reasons, 26 of which say "this is fine", is
permanent maintenance for a yield already in hand.


### The sixth, and the first the instrument caught before a person did

**`/fire-metrics/`, 2026-08-28.** Beckett's `72d6be1` added a standalone
FIRE Metrics view linked from no template. `test_route_reachability`
failed on his push **within hours, on a commit nobody on this side had
read**, and named the endpoint.

Compare how the first five were found: two by the dead-reader sweep, one
by a navigation check, one by looking for links from the detail page, one
by an investigation. **Every one of them after the fact, by a person going
looking — and the notetaker only after Michelle asked for two features
that already existed.** That is the cost of finding these late: she spent
a call describing work that was already built and shipped.

This one cost one test run and no human attention at all.

**Worth stating plainly because the sweeps were expensive to build and
their value had been theoretical.** `test_route_reachability` was written
after the fact, against a class of bug already found, which is the
position where an instrument looks like bookkeeping — it can only confirm
what is already known until the day something new trips it. This is that
day, and it caught a stranger's commit rather than our own, which is the
harder case and the one a convention cannot cover.

It also did the second half of its job: the failure message names the
endpoint, says why it matters (*"a person can reach them only by typing
the URL"*), and offers the allowlist with a written reason. The diagnosis
is in the failure, not in whoever remembers the history. Full write-up for
Beckett in `docs/beckett-open-test-failures.md`.

**No change to the "a sixth instrument is not the lesson" conclusion
above.** That was about adding *another* sweep; this is the return on one
already built, and the two are not in tension.

### The waiting-half convention

**When a feature is built in halves and one half ships alone, that half
carries a comment saying what it is waiting for.** A convention, not an
instrument, and it costs nothing.

The comment states three things:

1. **That nothing calls it**, so a reader is not left inferring it.
2. **What the other half is** -- the route, the writer, the screen.
3. **Whether it is safe to wire as-is.** This is the part `SOURCE_SITE_DD`
   did not need and `to_capex_lines` badly did: it has drifted three
   correctness fixes behind `build_lines()`, and connecting it would put
   the `b613a76` rate bug into equity and IRR. Someone finding it in six
   months needs that warning **in the file**, not only in a doc.

Both live examples are worth reading: `underwriting_capex.SOURCE_SITE_DD`
for the short form, `site_dd_costs.to_capex_lines()` for the form that
also has to say "do not connect this yet".

### The three that were deleted, and why they were not waiting halves

`investor_notes_match.count_mentions`, `openai_usage.get_usage`,
`site_dd_reference_costs.coverage`. The test that separates a leftover
from a waiting half: **does anything else now do the job?**

* `count_mentions` -- superseded *inside its own module* by
  `_distinct_spans`, which counts DISTINCT mentions because summing
  per-phrase counts was wrong. Its word-boundary test was **kept** and
  rerouted through `score()`; the property is real and this app has a
  deal called Jackson, so "jacksonville" must not match it.
* `get_usage` -- a single-feature slice of what the live
  `usage_for_month()` already returns in full.
* `coverage` -- its docstring said "for the report header", which reads
  like a waiting half. It is not: that header exists and was built
  differently, from budget *lines* rather than catalogue keys, as
  `summarize()`'s three buckets plus `researched_pct`, with the reference
  table and the unpriced list printed in full on their own sheets.

`to_capex_lines` fails that test and so survives: nothing else writes
Site DD findings into Underwriting.

---

## The ten label-map subscripts, and where each guard actually sits

Recorded for whoever widens a vocabulary next. `AREA_STATUS_LABELS` and
`ASSESSMENT_STATUS_LABELS` are now read through accessors and a test
forbids subscripting them. **Ten other subscripts remain, all safe today,
but not all safe for the same reason** -- and the difference is what
matters when a vocabulary grows.

Jinja here runs the **default `Undefined`**, so a missing key renders as
the **empty string**. A subscript that misses is therefore silent, not
loud (see false premise #5).

| site | expression | guarded by |
|---|---|---|
| `site_dd_area.html:19` | `condition_labels[c]` | **construction** -- `c` iterates `CONDITIONS` |
| `site_dd_area.html:76` | `room_type_labels[r.room_type]` | **a route check** -- `site_dd.py:622` |
| `site_dd_detail.html:242` | `condition_labels[c]` | **construction** |
| `site_dd_room.html:3` | `room_type_labels[room.room_type]` | **a route check** |
| `site_dd_room.html:24` | `condition_labels[c]` | **construction** |
| `site_dd_room.html:48` | `room_type_labels[room.room_type]` | **a route check** |
| `site_dd_room.html:310` | `room_type_labels[prev_room.room_type]` | **a route check** |
| `site_dd_room.html:346` | `room_type_labels[r.room_type]` | **a route check** |
| `investor_notes.html:105` | `source_labels[s]` | **construction** -- `s` iterates `sources` |
| `underwriting_detail.html:392` | `capex_scope_labels[s]` | **construction** -- `s` iterates `capex_scopes` |

**Five are guarded by construction** and cannot break: the loop supplies
the key. **Five are guarded by a route check** --
`if room_type not in uc.ROOM_TYPE_LABELS` at `site_dd.py:622`, before
`create_room()` is reached. `create_room()` itself does not validate.

That is the fragile half. The guard sits one layer away from the read, so
a second writer -- a bulk import, a copy-layout variant, a fixture, a
future rent-roll seeder creating rooms directly -- writes an unvalidated
`room_type` and five templates go quietly blank. Nothing fails; a room
simply loses its name.

**This is the same reasoning that made the status maps worth doing before
the widening rather than after.** The cheap version of the protection is
this table; the real version is an accessor at each read. If room types
are ever widened, do the accessor first.

**The Railway token in `~/.railway/config.json` expires roughly hourly,
and a stale one looks exactly like a permissions problem.** Every
GraphQL query returns `Not Authorized` -- not `401`, not `expired`, just
Not Authorized on every field including `me`. This cost real time: it
presents as "our token lacks the scope for this", and the natural next
move is to go hunting for a permissions fix that does not exist.
`railway status` refreshes it. Check expiry before concluding anything
about access:

    python -c "import json,pathlib,datetime as d; u=json.loads((pathlib.Path.home()/'.railway'/'config.json').read_text())['user']; print(d.datetime.fromtimestamp(int(u['tokenExpiresAt'])))"

**Push safety is `git merge-base --is-ancestor origin/master master`, not
`local == origin`.** After committing, local is *supposed* to be ahead of
origin, so an equality check fails every time and reads as "master moved,
do not push". The ancestor check asks the real question: has origin moved
somewhere my commit is not built on? This is not academic -- **Beckett
pushes to master directly**, and did so three times inside a single run
on 2026-08-18. Fetch and re-check before every merge; do not trust a
local head.


**The acquisition and refinance sides AGREE about origination. RESOLVED in
Part 46.** Both mean third-party costs only, with the lender's fee on its
own visible line: `refi_bank_fee_pct` on the refinance, `loan_fee_pct` on
acquisition. Each is a percentage of its own loan, because that is what a
point is.

*This section previously read "now disagree about origination, on
purpose", and that was correct at the time.* The disagreement was
deliberate for one reason only -- **Michelle had been asked about the
refinance side and not about the acquisition side**, so changing
acquisition would have been inventing an answer. It was flagged in the
engine docstring and pinned by a test rather than quietly fixed.

She was then asked, and answered: *"Yes, please split the lender's
origination fee out of the acquisition costs for consistency."*

**The unasked question was the whole of it.** Nothing about the code
argued for keeping the two conventions apart; the only thing holding the
inconsistency in place was that nobody had put the question to her. That
is worth noticing as a pattern — an "unasked question" recorded in a
handoff is a task with a one-sentence cost, not a permanent state, and
this one sat for several runs because it was written down as a
disagreement rather than as a thing to ask.

`DEFAULT_ACQUISITION_COST_CATEGORIES` now carries eight third-party
entries. Production had **zero** acquisition-cost lines when the ninth was
removed, so nothing was orphaned.


**The route sweep cannot see a self-referential cluster.** Pages that
link only to each other all look referenced while the group has no way
in — which is exactly what the notetaker was. Confirmed by running the
sweep at the commit before the nav entry landed: **it does not flag it.**
`NavShellTests` is the narrow answer (every blueprint index must appear
in `base.html`) and is labelled partial in the file. It does not
generalise to deep pages.

**Eagle Rock's confirmed figures**, reproduced exactly from production
scenario 4 by passing `capex_lines=` to `analyze_scenario()`:

| | |
|---|---|
| NOI year 1 | $482,120.76 |
| equity invested | $2,688,848.65 |
| levered IRR | 19.11% |
| DSCR | 1.3990 |
| equity multiple | 2.2645 |

The four capex lines sum to $97,665.38; with 5% contingency, $102,548.65
— exactly the equity difference from the no-capex run, which produces
20.12% and 2.3543. Both figures are real; they differ only by capex.

**`test_fire_metrics_improvements` accounts for a 161-test gap** between
local and container runs. It imports `httpx`, which is **undeclared** —
it arrives only as a hard dependency of `openai`. Locally, where `openai`
is absent, the whole module fails to import. Beckett's code; not fixed
here. `openai` already ships an `httpx2` extra, so the fragility is real
rather than hypothetical. Reconcile counts by **unique test ID**, never
by line-grep — a line-grep tally produced a phantom 14-test discrepancy.

**Assessment 11's fingerprint: `11fdd001f2fca08e` is RETIRED.** Its
algorithm was never written down and it cannot be reproduced, so it could
never have detected a change — an unreproducible fingerprint is not a
check, it is a number that gets copied forward. Two replacements, each
with its algorithm stated, because they answer different questions:

**The DATA fingerprint — has the assessment itself changed?**

```
sqlite3, mode=ro, /data/site_dd.db
rows = SELECT * FROM site_dd_findings WHERE assessment_id=11 ORDER BY id
blob = json.dumps([dict(r) for r in rows], sort_keys=True, default=str)
fp   = hashlib.sha256(blob.encode()).hexdigest()[:16]

2026-08-20  ->  f6451ecb366f6ab4   (23 findings)
```

**The EXPORT CONTENT hash — has what Michelle READS changed?**

Hashes rendered content, never file bytes: a PDF carries timestamps and a
XLSX carries zip metadata, and neither says anything about the budget. It
replicates the export route exactly — `needs_work()` filter,
`apply_reference()`, `build_lines()`, `summarize()`, `build_xlsx()` — then
hashes the summary, each line's visible fields, and every XLSX cell.

```
2026-08-20  ce25f0d9ad5de0e8  -> d0b8436a3998f63b   (Part 39 Step B)
```

The two are independent on purpose. The data hash held steady across that
change while the export hash moved, which is the correct signature for a
wording change: her walk did not change, what the budget says about it
did.

**Assessment 11 is Michelle's live work.** Nabob Hill, inspector MJ,
2026-08-16, one unit, one kitchen, 23 findings. Read-only, always. Its
`property_label` created a 12th entry in the notetaker property registry
and does not resolve to Deal Dive deal 2 (1120 Jackson Street) *by label*,
which is plausibly the same building.

**CORRECTED 2026-08-20.** The sentence that stood here — "`deal_id` is
`None` on all three assessments and nothing populates it" — was wrong on
both counts, and read read-only to check:

```
assessment  2 | '19 bay vista drive' | deal_id = None
assessment  6 | '19 bay vista drive' | deal_id = None
assessment 11 | 'Nabob Hill'         | deal_id = 2      <- set
assessment 12 | 'Nabob Hill'         | deal_id = None
```

There are **four** assessments, not three, and **assessment 11 is already
linked to deal 2**. `create_assessment()` takes `deal_id` in its INSERT
(`site_dd_db.py:537`), so it is populated at creation — "nothing populates
it" was a claim about our own code that one grep settles, which is
false-premise shape #4 exactly. Whether Michelle has confirmed the two are
the same property is a separate question and is still open; what is
settled is that the column is written and this one is set.

**The propagation on this one is worse than the usual shape, and it is
worth being blunt about it.** The link was not discovered — *it was
ordered*. The user asked for assessment 11 to be linked to deal 2, it was
done, and the false sentence went on standing in HANDOFF and was repeated
across several prompts afterwards **by the person who had ordered the
link**. So this is not "a plausible claim nobody re-checked". It is a
claim contradicted by an action the author took themselves, which the
written record outlived.

The other false premises argue for *checking the code*. This one argues
for something the code cannot supply: **when you have changed the world,
go back and correct what the document says about it.** A handoff is not
just a place claims go stale — it is a place your own completed work can
be overwritten by an older sentence.

---

## Code written for the case in hand, not for the shape of the problem — three times this week

The property checklist rendered `(items.get(key) or [none])[0]`. The first
instance of an item and nothing else. A second roof could be created, was
stored correctly, reached both exports correctly — and was **invisible on
the page that exists to edit it**. Michelle could add a building and then
never see it again.

`instance_no`, `instance_label` and `add_instance()` had existed since
repeatable items landed. `add_instance()` already worked at every scope.
`build_lines()` already grouped on the instance label. The machinery was
complete. One template subscripted it down to a single row, because when
that template was written every property item was assumed to occur once.

**That is the third instance of the same failure in one week, and the
count is the reason this is written down.**

| # | what was built | what the problem's shape actually was |
|---|---|---|
| 1 | Part 49: the absent-means-unchanged fix applied to the routes we were looking at | `site_dd.save` — the property-scope route — was missed entirely, and it is the one that writes the header fields |
| 2 | Part 47: an audit of standing rule 2 that found four collection-writing routes | There were **eleven**. The audit had been scoped to the routes already in mind |
| 3 | Part 54: a property checklist that renders one row per item | Items repeat at property scope for the same reason they repeat everywhere else — a building is not special |

Each of the three passed its own tests. Each was correct about the case
its author was holding. None of them asked *what is the general shape of
this thing, and does my change cover all of it?*

**The tell, in all three: a change scoped by enumeration.** "These
routes", "these four", "this item". An enumeration written from memory is
a list of what you happened to think of, and it looks identical to a
complete list once it is on the page. The correction is cheap and
mechanical — derive the list rather than recall it. `grep` for the write
call, not for the routes you remember; loop the collection, do not index
it. Part 51 re-ran the rule 2 audit by grepping for the writer and the
count went from four to eleven in one command.

Related: [Rule 2 audited at its real scope](#rule-2-audited-at-its-real-scope-and-the-dropped-clause-was-right)
and [Dead paths: five found, four different ways](#dead-paths-five-found-four-different-ways-and-the-convention-that-follows).

---

## "Same rows, different hash" — a method, not a guess

The Part 53 deployed verification of `save_expenses` ended with its own
safety check failing:

```
   !! production restored exactly — (215, 'fa7ef69a0d49b195') -> (215, 'a559a0802f942f5e')

RESULT: FAIL
```

Same table set, **same 215 rows**, different fingerprint. The scratch
scenario had been created and deleted correctly and the row count proved
it. That combination invites the two worst responses — assume a silent
corruption of production data, or assume the fingerprint is broken and
stop trusting the instrument.

**It was neither, and the way it was settled is the part worth keeping.**

### What was actually done

The deploy that landed between the two readings had added a column,
`loan_fee_pct`, to `underwriting_loans` (the origination-fee split). The
hypothesis was therefore: the fingerprint hashes whole row dicts, so a new
key changes the hash even when no value changed.

That hypothesis was not argued. It was **executed**, read-only, against
production as it stood:

```python
def fp(drop=()):
    blob = {}
    for t in TABLES:
        rows = [dict(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY id")]
        for r in rows:
            for d in drop:
                r.pop(d, None)          # the column, removed from the HASH
        blob[t] = rows
    return (sum(len(v) for v in blob.values()),
            hashlib.sha256(json.dumps(blob, sort_keys=True,
                                      default=str).encode()).hexdigest()[:16])

print("current, as-is             :", fp())
print("current, minus loan_fee_pct:", fp(("loan_fee_pct",)))
```

```
current, as-is             : (215, 'a559a0802f942f5e')
current, minus loan_fee_pct: (215, 'fa7ef69a0d49b195')
=> only change is the added column: True
```

Removing that one key from the hash reproduced the before-fingerprint
**exactly**. Not "consistent with", not "probably" — there is no room left
for a changed value to hide, because a changed value would have survived
the pop and moved the hash anyway.

### Note what was NOT done

**No `ALTER TABLE`, no `DROP COLUMN`, no copy of the database, nothing
written.** The column was removed from the *computation*, in a
`mode=ro` connection, at the point where the row became a dict. Dropping
the column for real would have proved the same thing and would have meant
running DDL on production to answer a diagnostic question — which is how a
verification step becomes the incident it was checking for.

The instrument was already a content fingerprint rather than a file hash
([the two-signal rule](#verify-on-deployed-code-not-by-reading-it)), and
that is exactly what made this possible: a hash computed from rows in
Python can be recomputed under a different projection. A file-level or
`PRAGMA`-level hash cannot be interrogated this way at all.

### The general form

**When a fingerprint moves and the rows look the same, recompute it with
the one structural change you know about projected out, and see whether
the old value comes back.**

* It comes back → the change was purely additive, no value moved, and you
  can adopt the new fingerprint as the baseline with a reason.
* It does not come back → the structural change is *not* the explanation,
  and you have narrowed a vague worry into a real search with the noise
  already removed.

This is a **positive control on the instrument** — the same discipline
this file applies to comparators everywhere else. A fingerprint that can
be made to return to its old value on demand is a fingerprint that is
still measuring what it claims to measure.

### What it cost, and what guessing would have cost

One read-only script. The alternatives were: accept "probably the
migration" and carry an unexplained hash change forward as permanent
background noise, or spend a session auditing values that were never
wrong. The first is how an instrument quietly stops being trusted; the
second is how a day disappears.

**Conclusion of record: additive migration only, no value altered — and
the next person seeing "same rows, different hash" has a method rather
than a guess.**


---

## A guard is correct relative to the thing it protects — three instances, one outage

A guard is not a piece of code that is safe. It is a piece of code that is
safe **about one specific thing**. Move it and the code travels; the
protection does not. Three instances this session, and the third put a
client off her own dashboard.

| | the guard | what it was supposed to protect | what it actually did at the new site |
|---|---|---|---|
| 1 | Part 51's `app.config` check for `USER_STORE_PATH` | writing accounts somewhere non-durable | **always returned `True`.** `config.py` resolves with `os.environ.get(NAME, fallback)`, so the key always holds a value. Asking "is it set?" is asking a question whose answer is always yes |
| 2 | the test redirect for `MARKET_CACHE_DB_PATH` | keeping tests out of the real cache | **failed open.** The variable does not exist — `MARKET_DATA_DB_PATH` does — so the redirect silently did nothing and two rows went into the developer's own cache |
| 3 | the user-store guard in `signup()`, copied into `login()` | a WRITE that would be silently lost on the next deploy | **blocked a READ that was already safe**, and with it every login including the env-configured admin. A client was locked out of production on 2026-08-24 |

### Why the third one is the clearest case

In `signup()` the guard is exactly right. A person is about to create an
account; if `USER_STORE_PATH` is unset that account goes to the container
filesystem and disappears at the next push, surfacing days later as *"my
password stopped working"*. Refusing is the correct answer, and it stays.

Copied into `login()` the same three lines mean something entirely
different, because **login does not write anything**. It calls
`User.verify`, which calls `find_stored_user`, which calls `_load_store`,
which returns `{"users": {}}` for a file that is not there — already safe,
already correct. And underneath that sits the admin branch, which reads
`ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` from the environment and never
touches the store file at all.

So the guard defended nothing on that route and cost everything: an early
`return` in front of authentication locks out every account, for a reason
unrelated to what the guard is about. The one consequence the store's
state genuinely has for logging in — a *saved* account cannot be read, so
"invalid username or password" is a false statement about that person's
credentials — was the one thing the guard did not say.

### The check, before reusing a guard anywhere

**What does this guard protect, and does the new call site touch that
thing at all?**

Two questions, and the second is the one that gets skipped. It is not
"does this guard make sense here" — a store guard on a login page reads
perfectly sensible, which is exactly the problem. It is the narrower,
duller question of whether the resource being defended is even in reach
of this code path. Follow the call, all the way down, until you find the
write, the read, or the network call the guard exists to stand in front
of. If it is not there, the guard is not protecting this route; it is just
failing it.

Two corollaries, both earned:

* **An early `return` in front of authentication is never a small
  change.** It converts "this feature is unavailable" into "nobody can get
  in", and those have completely different blast radii.
* **Ask what the guard's failure mode costs at the NEW site.** Failing
  closed is right in front of a lossy write and wrong in front of a login.
  The same guard is conservative in one place and catastrophic in the
  other.

### All three were found by running code. None by reading it.

This is the part worth keeping, because all three had been read over
without anyone noticing:

* Instance 1 passed its unit tests, which popped the config key — a state
  production never reaches. It was caught **only by deploying** and
  watching the banner fail to appear.
* Instance 2 was caught by finding **two unexplained rows** in a local
  cache, not by re-reading the patch that put them there.
* Instance 3 was caught by a **client's screenshot**, and then pinned by
  counting `User.verify` calls on the deployed container: zero with the
  store unset, one with it configured. Reading `auth.py` had not revealed
  it — the guard looks entirely reasonable sitting there.

Every one of these is invisible to inspection and obvious to execution,
which is [the standing rule about verifying on deployed code](#verify-on-deployed-code-not-by-reading-it)
arriving from a third direction. **Instrument the thing and watch it
behave. A guard that is never reached and a guard that always passes look
identical in a diff.**

---

---

## Falsy-zero, both directions — and the second one is worse

Zero and unknown are different facts. Everywhere they meet needs a
deliberate answer, and this codebase has now had the question wrong in
**both directions**.

| direction | what it looks like | found |
|---|---|---|
| **Zero read as absent** | `{{ rentcast.property.bedrooms or '—' }}` rendered a **studio as unknown**. `if rate:` read a `0.0` concrete flooring rate as "no entry". | Part 55 audit; Part 61, by accident |
| **Absent written as zero** | `noi_margin` returned `0` with no income and posted **"Low NOI Margin: 0.0%" as a red flag**. `deduction_pct` returned `0.0` with no GPR and imported **"0.000000"** into a field tagged `PROVENANCE_T12`. | Part 63 sweep, as an incidental |

**THE SECOND DIRECTION IS THE MORE DANGEROUS ONE, and the reason is about
readers rather than code: a blank prompts a question and a confident zero
does not.**

A studio showing "—" for bedrooms is wrong and *looks* wrong; somebody
asks. "Low NOI Margin: 0.0%" in the red-flag column is wrong and looks
like a finding. Nobody doubts it, because the tool has said it in the
colour it uses for things that need acting on. The same asymmetry runs
through the other pair: a blank vacancy field invites a number, whereas
`0.000000` tagged as imported from the T12 asserts that the file said so.

It is the same failure as Jackson's occupancy and the $5.75 repaint
budget, inverted — **fabricating a confident number where absence is the
truth** — and it arrives through a guard that reads as defensive
programming.

### The tell, and it is cheap to look for

**A division guard whose `else` branch is a number rather than `None`.**
`(a / b) if b else 0` says "when I cannot compute this, the answer is
zero", which is almost never what the author meant. `else None` says "I
cannot compute this", which is.

Both fixes had a **precedent in the same file** — which is what makes this
a convention drift rather than a design gap:

* `noi_margin` was the odd one of three neighbours. `occ_avg` five lines
  above returns `None` and guards its comparisons; `expense_ratio_avg`
  four lines below divides by **the same `income_sum`** and returns
  `None`; and the per-month version of the identical quantity at
  `kpis.py:357` had always returned `None`.
* `deduction_pct` contradicted a docstring one module away.
  `quick_analyzer_math._f()` says, of this very field: *"a missing
  vacancy rate and a vacancy rate of zero are different claims and must
  not collapse into each other."*

Neither fix invented anything. Both moved an outlier onto a rule already
written down beside it.

### What "absence explained" meant in each case

Not the same thing, and that is the point — the house pattern is that
absence is *explained*, not that it is *announced identically everywhere*.

* **`noi_margin` says nothing.** The absence is already explained on that
  screen: the warnings card carries *"Nothing in this file matched Gross
  Potential Rent"* and the occupancy column reads "No GPR". A fourth
  message would repeat the page; a flag would grade what cannot be
  measured. Its two neighbours are silent in the same circumstance, so
  silence is also the consistent answer.
* **`deduction_pct` says it out loud**, because a blank form field with no
  explanation is a mystery. The existing T12 warning was **extended**
  rather than replaced: it now adds that the deduction rate cannot be
  worked out without a gross figure, so the field is left blank to be
  entered. And the blank is not a dead end — `build_noi()` answers with a
  named refusal that tells the analyst exactly what to do.

---

---

---

---

## A schema lists what the platform supports, not what your account may call

Railway's GraphQL API defines `volumeInstanceBackupCreate`,
`volumeInstanceBackupRestore`, `volumeInstanceBackupLock` and
`volumeInstanceBackupScheduleUpdate`. Introspection shows all four, with
argument names and descriptions. `volumeInstanceBackupList` and
`volumeInstanceBackupScheduleList` both answer successfully and return
`[]`.

**From that I concluded the capability existed for this volume, was
simply unconfigured, and that switching it on was one person and one
setting.** It was reported that way, approved on that basis, and acted on
in the following run.

**It was wrong.** The workspace is on the **Hobby** plan:

    subscriptionPlanLimit.volumes.maxBackupsCount   0

Zero backups are permitted. `volumeInstanceBackupCreate` returns **`Not
Authorized`** — with a token refreshed sixty seconds earlier, while
`volumeInstanceBackupList`, `volumeInstanceBackupScheduleList` and `me`
all returned normally in the same script.

### Two readings, and the optimistic one was taken

An empty list had two meanings and both were available from the start:

| reading | implication |
|---|---|
| *configured to zero* | a setting nobody has turned on |
| *not permitted* | a plan boundary, not a setting |

Nothing in the response distinguishes them. **An empty result is not
evidence of an empty configuration** — it is equally consistent with a
capacity of zero, and a list endpoint has no way to say which.

The same trap sits in the schema itself. **Introspection describes the
API, not the caller's entitlement.** A mutation appearing in
`__schema.mutationType` means the platform implements it for somebody, and
says nothing about whether this token may invoke it. There is no
per-account schema.

### One call settled it, and it should have been the first one

    READ  volumeInstanceBackupList          -> OK
    READ  volumeInstanceBackupScheduleList  -> OK
    READ  me                                -> OK
    WRITE volumeInstanceBackupCreate        -> DENIED (Not Authorized)

Reads and the write in one script with one fresh token. That is the whole
experiment, it costs one request, and it distinguishes the two readings
immediately. **The general rule this file already carries — *before
claiming what a mechanism does, run it* — applies to permissions exactly
as it applies to parsers.** A capability is not established by being
listed; it is established by being exercised.

### The stale-token trap sits in front of it, and both were live

The first denial WAS staleness — the token was 21 hours expired, and this
file's own note says a stale token presents as `Not Authorized` on every
field including `me`. Refreshing it was right. **But refreshing it and
retrying the same mutation would have produced the same message for a
completely different reason**, and stopping at "still denied, so it must
be the token" would have been just as wrong in the other direction.

What separated them was running reads and the write *together after the
refresh*. Staleness denies everything; an entitlement boundary denies one
thing. **The discriminator is not retrying — it is a control that should
succeed.**

### What survived, and why the distinction matters

Everything in the same reconnaissance that was **read or measured** held
up, and it is worth marking which is which:

| claim | how it was obtained | still true |
|---|---|---|
| a backup covers the whole volume | every mutation keyed on `volumeInstanceId` | yes |
| restore is in place, no undo exists | argument descriptions, and no reverse mutation | yes |
| backups are metered as `BACKUP_USAGE_GB` | the `MetricMeasurement` enum plus a usage query | yes |
| all twelve DBs are `journal=delete`, `synchronous=FULL` | run on the container | yes |
| **the capability was available to us** | **inferred from a listing** | **no** |

Four measured, one inferred, and the inferred one was the only one that
was wrong. That is not a coincidence and it is the entry.


## When a positive control passes, doubt the instrument first

A positive control is supposed to fail. That is its whole function: break
the thing under test, watch the test go red, and only then believe the
green. **Twice this session a control has come back green when it was
broken, and each time the useful finding was in the control rather than
in the code.**

| | the control | what its passing revealed |
|---|---|---|
| `ALARM_STATES` | emptying the option set was expected to drop a missing smoke alarm from the budget. It did not. | `needs_work()` **rule 3** caught it anyway — `detail` was itself a work-condition string. The control was fine and the code had a second path nobody had written down |
| **`ceil` vs `round`** | replacing `math.ceil(baths)` with `round(baths)` was expected to break the bathroom count. It did not. | **the test could not tell them apart.** Python's `round(1.5)` is `2`, and 1.5 is the only fraction in the file |

The second is the more instructive, because the code was right and the
*claim about it* was unverified. `rooms_for()`'s docstring said **"ceil,
not round"** and gave a reason. Every test passed under either. So the
docstring was asserting a property nothing checked — a rule stated, not a
rule tested.

`round(2.5)` is `2` and `math.ceil(2.5)` is `3`. That is where they part,
and it is now the case that pins it. No unit in either rent roll has 2.5
baths and `parse_unit_type()` would refuse one — the test exists for the
rule, not for the data.

> **The rule: when a positive control passes, the first hypothesis is
> that the control is blunt, not that the code is safe.** A control that
> cannot fail has told you nothing, and it looks exactly like a control
> that did its job. Ask what value would distinguish the two
> implementations, and check that the test uses it.

Both instances were found because the control was *run and its result
read*, rather than run and assumed. The habit of writing controls is not
sufficient on its own; the result has to be looked at with the
expectation that it might be uninformative.

---

## Recording a hazard does not prevent it — generating the fixture does

Part 69 recorded, in this file, that a table transcribed by hand is a
hypothesis and must be checked against its source. The entry was written
after verifying an 18-row test table against the rent roll it described.

**One run later I transcribed 152 unit labels by hand, from a truncated
print, and produced 155.** Three duplicates and several units that do not
exist. The tests caught it immediately — `len(REAL_LABELS) == 152` failed
— but only because the fixture happened to carry its own size assertion.

**This is not recorded as a lapse to apologise for. It is evidence about
what recording achieves.** The rule was written down, in this document, by
me, four days earlier. It was correct, it was prominent, and it did not
fire — because the moment of transcribing does not feel like the moment
the rule describes. It feels like typing.

### The fix is mechanical, not mnemonic

    labels = [x["unit"] for x in parse(...)["units"]]
    write_fixture(labels)          # generated, in the commit

The fixture is now emitted from the parse and committed with a comment
saying so. Nobody has to remember anything.

**The general form: a rule that depends on someone recalling it at the
right moment is weaker than a step that makes the wrong version
impossible to produce.** Where a hazard has a mechanical fix, prefer it to
a written warning — and treat a hazard that recurs *after* being recorded
as evidence that the written warning was never going to be enough, rather
than as evidence that somebody should have read more carefully.

This is the same shape as the size assertion two entries above: *assert
the population before its contents*. Both replace a thing to remember
with a thing that fails.


## 152 units, no warnings, and every lease date silently absent

The `.xls` loader shipped in Part 68 read the Oxford Pointe rent roll
completely — **152 units, `source_format` "ResMan Rent Roll", warnings
empty** — and reported `lease_start`, `lease_end`, `move_in` and
`move_out` as `None` on **every one of the 152**, while the file plainly
contained them.

**xlrd hands back a raw serial for a date cell and keeps the cell type
separately.** `sheet.cell_value(r, c)` on a date returns `45839.0`, not a
`datetime`. openpyxl returns a `datetime`, so `_as_date()` — which parses
datetimes and strings — had never needed to consider a bare float. It
declined all of them, and declining is spelled `None`, which is also how
the parser spells *"this field is not stated"*.

### The output could not have looked better

Nothing said anything was wrong. The unit count was right, the format was
recognised, the warnings list was empty, and every field that *should*
have been empty was empty. Four columns of real data had become four
columns of honest-looking absence.

This is the **"data present, silently reported missing"** family, and it
sits with the falsy-zero pair rather than apart from them:

| | |
|---|---|
| zero read as absent | a studio's `0` bedrooms rendered as "—" |
| absent written as zero | `noi_margin` graded `0.0%` as a red flag |
| **present read as absent** | **every lease date on 152 units** |

All three are the same confusion — a value and its absence sharing one
representation — and this one is the hardest to notice, because the output
of a parser that dropped a column is indistinguishable from the output of
a file that never had it.

### What caught it, which is the part worth keeping

**Comparing the output against the file, rather than checking the return
value.** The return value was checked first and it passed: 152 units, no
warnings, the number Part 35 predicted. Everything asserted about it was
true.

What found the defect was opening the workbook separately and asking what
was in the date columns — `ctype=DATE`, `44883.0 -> 2022-11-18` — and only
then noticing the parser had said `None`.

> **The rule: for an importer, the test is not "did it return something
> plausible" but "does what it returned match what is in the file".** A
> parser can only be verified against its input. A count and a clean
> warnings list establish that it did not crash, which is a different
> claim and a much weaker one.

The same reasoning is why the fix went in the **loader** and not in
`_as_date()`. The loader is where the format difference lives and where a
serial is known to be a date; `_as_date()` receives a bare float with no
idea which workbook it came from, and **45839 is a plausible rent as well
as a plausible date**. A converter that guessed there would be inventing
exactly the kind of value this file is careful never to invent.


## The four that STAY, and why — do not "fix" these

Recorded so somebody reading the two merges above does not finish the job.
Nine division guards were examined. Two were live defects and are fixed.
**One must not change and four are not worth changing.**

### `effective_pct` must stay `0.0` — it looks like the others and is not

`underwriting_math.py:443`, `(effective / price * 100.0) if price > 0 else 0.0`.

`None` breaks it **twice**:

* `_engine_inputs(scenario, acq["effective_pct"] + capex_pct)` — `None`
  raises on the addition.
* `templates/tools/underwriting_detail.html` does
  `'{:,.3f}%'.format(acq.effective_pct)` — raises again.

And the semantics are right as they stand: **no purchase price means no
percentage-of-price**, the engine requires a number, and zero acquisition
cost as a fraction of nothing is the only answer that composes. This is
the case where `None` would be the defect.

### The four cosmetic ones stay

* `completion_pct` in **both** `site_dd_conditions.py:238` and
  `site_dd_unit_checklist.py:781`. `total_items` counts a **fixed
  catalogue** and is never zero, so the guard is unreachable — and it
  feeds **four templates** through `'%.0f%%'|format`, every one of which
  raises on `None`. Four screens of blast radius for a state that cannot
  occur.
* `mmr_report/parsers.py:93` `pct_occ` and `:359` `avg_rent` — a "Total"
  row declaring zero units, or a building with zero occupied units. MMR
  file shapes, not analysis output.

### Two deliberately deferred, not overlooked

* **`pct_change`** (`scorecard_pro/kpis.py:446`). A category whose first
  half averaged zero reports *"no change"*. Worth doing, and note it has a
  **pre-existing ambiguity independent of this**: `len < 2` returns the
  same `0.0`, so two different unknowns already share one value. Fixing
  the division guard alone would leave half the problem.
* **`used_pct`** (`admin.py:120`). An unreadable volume reports `0.0`, so
  `level` computes to `"ok"` — a storage monitor saying healthy because it
  cannot see. Wrong failure direction, but `statvfs` returning a zero
  block count on a live mount is unreachable.

---

## "Twelve" was nine, and a pattern match is not a reading

**The Part 63 sweep reported "twelve division guards". There are nine.**
The brief for Part 64 then carried "twelve" forward as fact and scoped a
run on it.

The grep shape `if <name> else 0` bundled **three different mechanisms**:

| | count | what it actually is |
|---|---|---|
| genuine division guards | 9 | `(a / b) if b else 0` — the thing being looked for |
| `return row["n"] if row else 0` | 6 | `COUNT(*)` queries. A COUNT always returns a row, and `0` is the correct answer to "how many" |
| `payment / 12 if payment else 0.0` | 3 | the denominator is the **constant 12**. `0 / 12` is `0.0`, so the guard is a no-op |

Only reading each member separated them, and the separation changed the
conclusion: of nine, two were live, one must never change, and six were
tidiness or less.

**This is the third correction of this shape in one session** — a category
asserted from a pattern match rather than from reading its members:

1. **Part 62**: the design's `for_item` sketch had one fallback where
   there are two cases, and would have repriced concrete flooring.
2. **Part 63**: the design's nine scope items were three different kinds
   of item; three were `KIND_CHOICE` and could not take a scope detail at
   all.
3. **Part 65**: twelve guards were three mechanisms; nine were guards.

The general form: **a set assembled by shape is a hypothesis, and its
count is the least reliable thing about it.** Every one of these read
correctly, produced a plausible number, and was wrong about what the
members were. The fix is not more careful grepping — it is that the
grep's output is the *input* to the work, never a finding, and the finding
only exists once each member has been opened.

---

## The reassurance on the approval screen was computed with the wrong counter

**The seeding preview told somebody approving a 152-unit write that it
would preserve `2` findings on an assessment holding `23`.**

`area_finding_count()` filters `condition IS NOT NULL` — deliberately, and
correctly for the question it was written for, which is *"is copy-layout
still safe to offer"*. That is a question about **answers**. Saving a room
writes a row for every checklist item, so an area can hold dozens of rows
and two answers, and assessment 11 is exactly that shape: **23 rows, 2
with a condition.**

The preview reused it for a different question — *"how much of your work
does this write leave alone"* — where every row counts. A row with no
condition can still carry a note, a cost or a measurement, and even an
empty one is a row the seed does not touch.

**The direction of the error is the point.** Understating what is
protected, on the one screen where a person approves the largest write
this platform has ever made, argues *against* proceeding for a reason that
is not true. A number that reassures wrongly and a number that alarms
wrongly are not equally bad here — but neither is acceptable when the
person reading it cannot check it.

**Fixed by adding `area_finding_rows()` rather than changing
`area_finding_count()`.** The old function has a live caller with a
correct reason for the filter; changing it would have moved the defect
rather than removed it. Both now carry docstrings saying which question
they answer and naming the other. Confirmed on production after the merge:
the reconcile against assessment 11 reports **`findings_preserved: 23`**.

**The general shape, and it is not "count the right rows".** It is that
**a counter is an answer to one question, and reusing it silently
re-answers a different one.** The call site read perfectly well —
`area_finding_count(conn, area_id)` is obviously the number of findings in
an area — and nothing about it hinted at a filter. Same family as [a guard
being correct relative to the thing it
protects](#a-guard-is-correct-relative-to-the-thing-it-protects--three-instances-one-outage):
the code travels, the reason it was right does not.

---

## A migration check that could not have failed, because it ran on the old code

**Part 75 verified the `seed_batch` migration by running an isolation
script on the container, and reported PASS. The check proved nothing: the
container was carrying the pre-merge code, so the migration it was
verifying did not exist there and never ran.**

The tell was in the output and was nearly read past — the script printed
its list of new columns and the list was **empty**. A migration that adds
two columns, verified by a run that added none, reporting success.

**Why it looked right.** Every other verification in this project is run
on the container *on purpose* — [verify on deployed code, not by reading
it](#verify-on-deployed-code-not-by-reading-it) is one of the oldest rules
here, and it is correct. The rule assumes the deployed code is **the code
under test**. For anything not yet merged that assumption inverts: the
container is the one place guaranteed to be running something else.

> **The rule: "run it on the container" verifies a merge, never a branch.**
> Before a merge, the container is a control, not a subject. Verify branch
> code locally against a copy of production data — pull the database down
> and run the new code against it — and re-verify on the container after
> the deploy.

**And the same isolation, run properly after the merge, produced exactly
the predicted result.** 2026-08-30, on the container, through the app's
own `get_connection()` (which is what any page load does):

```
before             : (38, '1d980444f657b0bb')
after              : (38, 'df9226d2379e7bef')
after, minus column: (38, '1d980444f657b0bb')
```

The [projection
method](#same-rows-different-hash--a-method-not-a-guess) settles it:
popping `seed_batch` out of the computation returns the old fingerprint
**exactly**, so the change is purely additive and no stored value moved. 38
rows before and after, assessment 11 still `f6451ecb366f6ab4`, and zero
rows carrying a batch id, because nothing has been seeded.

**Adopt `df9226d2379e7bef` as the Site DD baseline**, replacing
`1d980444f657b0bb` in the restore runbook's known-good table.

**The migration is idempotent and additive, and it fires on the first
connection anybody opens** — `init_schema()` runs inside `get_connection()`
on reads as well as writes. It had not fired for the first four minutes
after the deploy simply because nobody had opened a Site DD page. That is
worth knowing before it is mistaken for a failed migration.

---

## Decision: the first real seed goes into a FRESH assessment

**Settled 2026-08-30. Both seeding design documents listed "which
assessment a roll seeds into" as open; this closes it for the first run
only.**

**The first Oxford Pointe seed creates a new assessment and writes into
that.** Not assessment 11, not any assessment somebody has walked.

The reason is not that the reconcile is doubted — it reuses areas, appends
only the shortfall, deletes nothing and touches no finding, and that is
tested. It is that **the one failure the batch undo cannot reverse is a
wrong reuse**, and a wrong reuse requires an existing area to match
against. Into an empty assessment there is nothing to match, so the
undoable failure is the only failure available, and `seed_batch` covers it
completely.

The snapshot still gets taken. This decision reduces what the snapshot has
to be right about; it does not replace it.

**What this does not decide:** seeding into a walked assessment is a real
requirement — re-uploading a roll after an inspection is the case §3.3 of
the seeding design exists for — and it stays supported and tested. The
decision is about **which one is done first, with a person watching**, not
about which ones are allowed.

---

## The first real seed: 152 units and 894 rooms, written and undone and written again

**2026-08-30/31. Assessment 21, "Oxford Pointe", created fresh for this.
Production, through the routes, with the real ResMan file
(`Rent Roll (11).xls`, 189,440 bytes, sha256 `345d5c84f47b7e54`).**

This is the largest write this platform has ever made — before it, every
area in Site DD across all assessments was **2** and every room was **1**.

| | |
|---|---|
| areas created | **152** |
| rooms created | **894** |
| rows carrying the batch id | **all of them** — 0 areas and 0 rooms with `seed_batch IS NULL` |
| findings created | **0** |
| findings anywhere, before and after | **31** |
| assessment 11 | `f6451ecb366f6ab4`, unchanged through every step |
| status split | 134 occupied / 18 vacant — the file's own Property Occupancy total |
| notes written | two: `Rent roll status: UE` on 217, `Notice to vacate 2026-08-13` on 640 |
| whole-database fingerprint | `(39, 'bedad2a7023d64a2')` → `(1085, '687e30e37f036e32')` |
| detail page at full scale | **15 ms, 228 KB** for 152 area cards |

**Every figure on the screen matched the write.** The preview said 152
units, 894 rooms, 0 preserved, 0 refused, and the button said *"Create
152 units and 894 rooms"*; the database agreed on all four. That is not a
coincidence — the apply re-parses the file, re-reconciles it and refuses
if what it computes differs from what the screen displayed.

### The round trip was exercised on the real thing, not on a copy

The undo ran from the assessment page and the database came back to
`(39, 'bedad2a7023d64a2')` — **the pre-seed fingerprint exactly**, not
"consistent with" it. Then it was seeded again: 152 and 894 once more,
under a new batch id, 31 findings still untouched.

**Note what the second seed's fingerprint does NOT do: return to the
first seed's value.** Row ids and `created_at` differ, so
`687e30e37f036e32` is a third value and that is correct. The check that
means something is the *undo* returning to the pre-seed value exactly;
expecting a re-seed to reproduce a prior fingerprint would be expecting
the database to forget that anything happened.

**The platform's only rollback is application-level** — Hobby plan,
`maxBackupsCount: 0`, known-issue 3 — so exercising it once where it
matters was the point of doing this rather than believing it. Three
snapshots now sit on the volume: one taken by hand before anything
(`site_dd.before-first-seed.20260831-033837.db`) and one taken by
`apply_seed` itself before each of the two writes.

### Why a fresh assessment, restated now that it has run

The decision was recorded before the seed and it held up for the reason
given: **into an empty assessment there is nothing to wrongly reuse.**
`reuse_count` was 0, every one of the 1,046 rows carries a batch id, and
the undo therefore reached all of it. A wrong *reuse* — the one failure
that leaves no batch marker and needs the snapshot — was not merely
unlikely here, it was unavailable.

---

## A CSRF failure looks exactly like an authentication failure

The first attempt at the seed posted the rent roll to the preview and got
back **302 to `/login`**. The obvious reading is that the login bypass had
not taken — and it is wrong. `app.errorhandler(CSRFError)` flashes
*"Your session expired. Please log in again."* and redirects to the login
page, so a POST with no CSRF token is answered exactly like a POST from a
stranger.

The fix was to do what a browser does: **GET the page first and post the
token it rendered.** That is also the more faithful test, since it
exercises the form the user actually gets.

**The general shape is one this file already knows in another costume:** a
stale Railway token presents as `Not Authorized` on every field, and the
natural next move is to hunt for a permissions problem that does not
exist. Same here — one status code, two completely different causes, and
the discriminator is a control that should succeed: a GET that renders,
or a second POST that carries the token. **When a failure names a
plausible cause, check that the named cause is the one that fired.**

---

## Wiring a waiting half, and what the comment on it should say afterwards

`apply_seed` and `undo_seed` shipped merged and unreachable on purpose,
carried the Part 37 waiting-half comment for exactly one merge, and were
wired in the next. The comment did not survive as written, and should
not have: **a waiting-half notice that outlives its wiring is worse than
none**, because it tells the next reader a feature is unreachable when it
is reachable. What replaced it says where the callers are, and keeps the
one clause that is still true — **neither sweep covers this module**, so
if the apply panel is ever deleted from the template nothing automated
will notice the module has gone dark again. `tests/test_sitedd_seed_route.py`
is what would fail, because it harvests the form out of the rendered page
instead of posting to a URL it typed.

### The three gates, and why three

Each answers a different way of being wrong, and no one of them covers
another:

| gate | the failure it catches |
|---|---|
| **the held upload** | the apply is reading a different file from the one previewed |
| **the rendered-state token** | the assessment changed between preview and apply — two tabs, two people |
| **the figures** | file and world both fine, and the plan means something other than what the screen said |

The third is the one that would not exist without asking what the other
two miss. It is also the cheapest: five integers in hidden fields,
compared against the same five re-derived at write time, and **nothing is
written on a disagreement** — one of them is wrong about production, and
which one matters more than resolving it automatically.

**The preview now keeps the uploaded file, and that reverses a documented
decision.** It used to throw the bytes away, on the argument that storing
a file for a write nobody has approved is exactly the side effect that
screen exists to avoid. That argument is still right about *durable*
storage and it cannot survive an approve-then-write flow: a browser
cannot re-post a file it was given, so the alternative is asking the
person to choose the file a second time — which invites them to choose a
different one. The bytes go to the system temp directory under a random
id, are deleted whether the apply writes or refuses, and are swept after
six hours. Verified after the run: zero files for assessment 21 remained.

---

## Assessment 21, and why its honest name does not go in the label

**Assessment 21 is the first real seed: Oxford Pointe, 152 units, 894
rooms, batch `seed-20260831-034600-0c16c9`, no findings, status `draft`,
inspector `seed import`.** It exists because the write was tested on real
data, and Michelle has not asked for it.

**Recommendation: keep it.** The data is correct, it is the property she
will walk, and deleting it means doing the whole thing again later — with
the added cost that the *next* run would be the first one, again, with
nothing learned carried forward. The undo is proven on this exact batch,
so "keep" is reversible in a way that "delete and redo" is not.

**But the honest name does not belong in `property_label`, and that is
worth stating because it is the obvious place to put it.**
`site_dd_assessments.property_label` is read by `investor_notes.py` as a
source of **property identities** — `SELECT DISTINCT property_label FROM
site_dd_assessments` builds the registry the notetaker matches against.
A label reading "Oxford Pointe (TEST)" would put a test marker into a
registry that has nothing to do with seeding, and the same shape has
already happened once: assessment 11's label created a twelfth registry
entry nobody intended.

So the provenance goes in **`overall_notes`**, which is displayed and
editable on the assessment page and is read by nothing else.

### And adding that note is not free, which was worth measuring first

*The general finding this came from now has its own entry —
[Rule 2 in the other direction](#rule-2-in-the-other-direction-a-save-materialises-what-nobody-touched)
— because it is about every scope, not about assessment 21.*

`site_dd.save` is the property-scope route, and it is one of the eleven
full-collection-rewrite routes. Measured on a fresh assessment rather
than assumed:

```
findings before:                        0
findings after a notes-only save:      32     all with condition = NULL
```

`_posted_instances()` returns `{1} ∪ existing ∪ posted`, so a save that
carries nothing but `overall_notes` still writes **a row for every
property-scope checklist item**. On assessment 21 that turns "no findings"
into thirty-two blank ones — and the next seed preview of that assessment
would then correctly report **"32 findings preserved"**, which is true and
reads as though somebody had started walking it.

**Nothing is lost by it** (the rows are empty and the checklist treats
them as unanswered), and it is still the wrong way to attach one sentence
of provenance. The note is better typed into the box by the person who
owns the assessment, or written straight to `overall_notes`.

**Status: not written yet.** A direct `UPDATE` on production was declined
by this session's command policy, and the route costs the 32 rows above,
so the sentence is recorded here and the write is a decision rather than
a side effect.

---

## Snapshots accumulate and nothing prunes them

**Established rather than assumed: `take_snapshot()` writes and never
deletes, and no other code path touches `/data/backups` at all.** The only
sweeper in the seeding code is `_sweep_seed_pending()`, which clears held
uploads out of the system temp directory and has nothing to do with
snapshots.

Measured on the volume, 2026-08-31:

| | |
|---|---|
| volume | **5 GB**, 4.57 MB used across everything |
| `/data/backups` | 3 files, **270 KB** |
| `site_dd.db` after the seed | **188 KB** — so each future snapshot is at least that |
| `/data/uploads` | 52 files, 2.1 MB |

**A seed's snapshot is a copy of the whole database, so it grows with the
data.** Once 152 units are actually walked — say thirty findings each —
`site_dd.db` lands somewhere over a megabyte and every snapshot after
that costs the same. Even at one seed a week for a year that is tens of
megabytes against five gigabytes.

**So this is not a space problem, and framing it as one gets the fix
wrong.** It is a **legibility** problem, and it arrives much sooner: a
directory holding fifty near-identical files named for batch ids is where
somebody picks the wrong one at the worst possible moment. The runbook
already insists on verifying a snapshot's contents before restoring it,
which is exactly the step that gets skipped when there are fifty
candidates and the volume is on fire.

### The proposed rule, not built

1. **Prune at write time, in `apply_seed`, right after the snapshot is
   taken.** There is no scheduler in this platform and adding one for
   this would be a worse trade than the problem. The seed is the only
   thing that creates snapshots, so it is the honest place to bound them.
2. **Keep everything from the last 30 days, and at least the newest 10
   whichever way that falls.** Both, not either: a burst of ten seeds in
   one afternoon must not evict a month of history, and a quiet year must
   not leave one file.
3. **Never delete the newest snapshot, whatever its age.** A rule that can
   empty the directory is not a retention rule.
4. **Only ever consider files matching `site_dd.seed-*.db`.** Anything a
   person took by hand — `site_dd.before-first-seed.20260831-033837.db`,
   which is the only copy of the state before the largest write this
   platform has made — is exempt **by construction rather than by a list
   somebody maintains**. See known-issue 3: there is nothing behind it.
5. **Report what was pruned** in `apply_seed`'s result, the way it already
   reports the snapshot it took. A deletion nobody sees is how the next
   restore finds a gap it cannot explain.

**A convention to adopt with it:** name deliberate, keep-forever
snapshots `site_dd.keep-<what>.db`, so "do not delete this" is expressed
in the filename instead of remembered. That is the same move as
`seed_batch` — put the fact in the data, not in a person.

### Six snapshots lived outside the convention — RESOLVED 2026-08-31

> **Moved, and the heading was wrong twice over.** It said *five* and
> then listed *six*, which is the arithmetic a numbered list is supposed
> to make impossible and did not, because the count was written before
> the list. All six are now in `/data/backups` under
> `<database>.keep-<what>.db`; the two byte-identical `pre_stepd` copies
> were dropped after re-verifying the hashes immediately before each
> delete rather than trusting the measurement from the run that found
> them. Six files, four kept, and the runbook's "where snapshots live"
> is one place again.

`/data` held `deal_dive.db.pre_part14`, `deal_dive.db.pre_stepd`,
`investor_notes.db.pre_part14`, `underwriting.db.pre_part14`,
`underwriting.db.pre_stepd` and `site_dd.db.pre_part14` — hand copies
taken beside their databases rather than in `/data/backups`. They totalled
about 385 KB and nothing pruned them either.

**They matter less for their size than for what they do to the runbook.**
§3 said snapshots live in `/data/backups/`, and for six files that was not
true — somebody following it under pressure would not have found them.
The sentence being wrong was the cost, and it was fixed twice: first by
naming both places honestly, then by making one place true.

---

## Rule 2 in the other direction: a save MATERIALISES what nobody touched

**The full-collection-rewrite hazard has always been described as
blanking what a POST omits. It also does the opposite, and the opposite
has never been written down.** A save that carries nothing at all still
writes a row for every item in scope, because `_posted_instances()`
returns `{1} ∪ existing ∪ posted` — instance 1 of every catalogue item is
emitted whether the form mentioned it or not.

Measured on a fresh assessment rather than reasoned about, one empty save
per scope:

```
start                       0 findings
after a notes-only property save     32     all condition = NULL
after an empty unit save             42
after an empty room save             60
```

**Sixty rows from three saves that said nothing.** Every one is honest —
unanswered, not wrong — and nothing is lost by them. That is exactly why
this is worth recording: there is no symptom, no error, and no incorrect
value anywhere.

### The consequence, which is on a screen where somebody approves a write

The seeding preview reports **findings preserved** using
`area_finding_rows()`, which counts every row rather than only the
answered ones. That change was correct and was made for a good reason: an
unanswered row can carry a note, a cost or a measurement, and *"preserved"
means every row that survives*.

But the two facts meet badly. **Rows are created by opening a page and
saving it**, so an assessment nobody has really walked can report
*"28 findings preserved"* — a true statement about rows that reads to a
person as *work already done*. The number is not wrong; the word
"findings" is doing more work than the data supports.

**Both fixes were right and the tension is real**, which is the part to
carry rather than a verdict:

* counting only answered rows understated what a 152-unit write protects,
  which is the wrong direction on an approval screen (Part 76);
* counting every row overstates *effort*, because visiting a page creates
  rows.

**A proposal, not built: count rows carrying any content** — a condition,
a note, a cost, a measure or a quantity — rather than all rows or only
answered ones. That is the number that means "somebody put something
here", it still protects the note-without-a-condition case that motivated
the change, and it reads as zero on an assessment that has only been
opened. It is one `WHERE` clause and it needs a decision about what
counts as content.

### Why this belongs beside the blanking rule and not inside it

The blanking direction destroys information and is caught by looking for
*absence*: a value that used to be there is gone. This direction creates
information and is invisible to that check — nothing is missing, the
counts only ever go up, and every row it writes is defensible. It is the
same mechanism, `_posted_instances()`, read from the other end, and a
reader who has internalised "post complete forms" has no reason to expect
it.

**The check that finds it: count the rows a save creates, not just the
ones it changes.** Three POSTs and a `COUNT(*)` settled this, and the
same three lines would settle it for any other route built on the same
helper.

---

## Closed, unconfirmed

**Deal Dive search box.** Michelle reported a search problem; asked later
which screen she meant, she replied *"I CAN'T REMEMBER…"*. The fix that
went in — `ae19794`, "make the filter box say what it is, and wire up
Enter" — is live on master and is correct on its own terms: the box now
labels itself as a filter and Enter submits.

**Closed without confirmation that it was the screen she meant.** Nobody
has matched the fix to the original report, and nobody now can. If a
search complaint resurfaces, treat it as a new report rather than a
regression of this one. Do not spend further time reconciling it.

---

## Open operational items

- **The repo is public.** `private: false`, 0 forks/stars/watchers.
- **`uw-refi-cashout` is held on Michelle's answer**, not on staleness.
  It was rebased and re-verified; the blocker is the fee-base
  double-count described above.
- **Five merged branches can be deleted** once you are comfortable.
- **The seed is wired and has been run once.** `site_dd.seed_apply` and
  `site_dd.seed_undo` reach `apply_seed()` and `undo_seed()`; assessment
  **21** holds the first real seed, 152 units and 894 rooms under batch
  `seed-20260831-034600-0c16c9`. **Neither sweep covers
  `site_dd_seed_write`** — not a `tools/*_db.py` module, no reader prefix,
  POST-only routes — so if the apply panel is ever removed from the
  template, `tests/test_sitedd_seed_route.py` is the only thing that
  fails.
- **A cosmetic warning** on every Site DD PDF report:
  `site_dd_report.py:146 UserWarning: No artists with labels found to put
  in legend`. Harmless, noisy, unfixed.
- **`GET /` , `/manifest.json`, `/service-worker.js`** are reachable via
  literal paths rather than `url_for`; the route sweep understands this.
  Three routes are allowlisted: `fire_metrics.debug_refresh` and the two
  POST-minted token downloads.
- **Do not scope the Entrata parser seam until a real sample export
  exists.** *Narrowed in Part 41; this line read "Do not start the Entrata
  parser seam" — the prohibition without the condition or the reason.*
  We have never seen an Entrata file, so every estimate would be
  fabricated. **Oxford Pointe is the evidence: the file format decided the
  answer, not the design** — an upload we assumed needed a new parser
  turned out to need a loader branch and `xlrd`, and the existing ResMan
  parser already returned all 152 units correctly. The exit criterion is a
  sample file, and nothing else. Full statement in *Revised cost
  estimates* below; **the two must say the same thing — see
  [Rules stated twice](#a-rule-stated-twice-loses-its-condition-in-the-shorter-statement).**
- **Do not build the rendered-state token for `save_loans`, `save_capex`
  and `save_gp_partners` until one of three things is true.** Those routes
  delete omitted rows, and absent-means-unchanged is the WRONG fix because
  omission is how those forms express removal. **The exit criterion is any
  ONE of: per-account data ships; a second person can log in; or one of
  those pages joins a two-person workflow.** Until then the back-button
  path is closed by `no-store` and the exposure is one user with two tabs.
  Full statement under *The three deleting routes* above; **the two must
  say the same thing — see
  [Rules stated twice](#a-rule-stated-twice-loses-its-condition-in-the-shorter-statement).**
- **Do not rework P&L column-year assignment until a file arrives whose
  columns carry no year.** The fix is to walk the period forward from its
  start month rather than resolve each column against one default. A T12
  crosses a year boundary,
  so the single `default_year` is wrong for part of any range. **No
  current format reaches that branch**: Beam, Ince, Canyon and the
  converted CSVs all write the year into every column header, so this is
  dormant, not broken. The exit criterion is an export family that omits
  the year. Full statement under *A month's own digits were being read as
  its year* above; **the two must say the same thing — see
  [Rules stated twice](#a-rule-stated-twice-loses-its-condition-in-the-shorter-statement).**


---

## The $15 freeform rate ceiling is provisional

`site_dd_reference_costs.FREEFORM_RATE_CEILING = 15.00` decides whether a
hand-typed cost on a **freeform** item (one with no reference entry, so no
unit to inherit) is read as a rate and refused a total, or as a job price
and multiplied by the instance count.

**The reasoning:** every researched rate in the table is at most $11.50;
the cheapest researched per-item figure is $195. Nothing occupies that
seventeenfold gap, so $15 sits just above the rate ceiling and refuses as
little as possible.

**Why it is a guess, not a derived constant.** That gap is evidence about
the **36 curated entries**. A freeform item is by definition not one of
them, so the number is applied to exactly the category it was not
measured on.

**Known failure mode, asserted in a test:** a freeform "replace one
outlet cover, $8" is refused. That is a real line item and the
justification — no capital job costs twelve dollars — is an assumption
about a field built to hold anything.

The behaviour is still correct: silently multiplying a rate by a headcount
is the worse error, and a refusal is visible and correctable where a wrong
total is neither. **The real fix removes the guess**: an explicit
per-item/per-unit choice on freeform costs. That is a UI control Michelle
has not asked for, and it is flagged rather than built.

---

## Revised cost estimates (2026-08-17)

Several of these moved once the premise was checked. See the standing rule
above.

| item | cost today |
|---|---|
| **Site DD rent-roll upload** | **Roughly halved.** The original 2–3 session estimate assumed a new parser. The existing ResMan parser already returns all 152 Oxford Pointe units correctly — it needs a **loader branch plus `xlrd`**. Remaining: ~1 session for the parser/Underwriting path, a second for Site DD seeding. The idempotent re-upload reconcile is the expensive part, not the parsing. |
| **Site DD property header** | **Now small.** The `deals` columns landed in `07e746e`. What remains is a form block and a display block. |
| **Site DD Lite** | **Small.** `status` exists, is validated, and is displayed in three templates. It is a query filter plus a UI control. It never shipped because nothing consumed the field, not because it was hard. |
| **Entrata parser seam** | **Deliberately unscoped.** We have never seen an Entrata file, so every estimate would be fabricated. Do not scope it until a sample exists — the Oxford Pointe experience is the argument: the file format decided the answer, not the design. **Also stated in *Open operational items* above; keep the two in step.** |
| **`SOURCE_SITE_DD` cleanup** | Trivial: delete a constant and a counter branch, or implement the hand-off. |
| **Manual freeform UI control** | Small, but unrequested. See the provisional threshold above. |

---

## What has not been verified

Stated plainly so it is not mistaken for tested ground.

> **Anything with a written-down way to settle it now lives in `docs/known-issues.md`**, one entry each, with what would close it. This list stays for the standing caveats that have no single check to run. If you find yourself writing "someone should verify X", it belongs in that file, not here.

- ~~The AI synthesis path was never exercised.~~ **Now verified.** One
  authorized generation on 2026-08-17 against a deliberately thin
  transcript returned all six headings correctly named, and **Next Steps
  came back empty** rather than inventing a plan — which is the specific
  failure that section invites. Tagged `investor_notetaker`, counter 1 → 2.
  Transcript deleted, notes fingerprint restored exactly.
- ~~**No 2BD rent roll has ever been parsed.**~~ **Closed 2026-08-29.**
  The Oxford Pointe ResMan roll parses completely: 152 units, 18 distinct
  type strings, six distinct layouts, **77 of them 2 bed / 1.5 bath**.
  Bedroom and bathroom derivation is built and tested against all 18
  strings rather than a sample. Seeding remains unbuilt and is designed in
  `docs/site-dd-rentroll-seeding.md`.
- **The unit-label letter rule is still untested.** Oxford Pointe's
  labels are numeric -- not one starts with a letter -- so the 60%
  threshold below has still never run against a lettered file. The second
  lettered roll has not arrived.
- **The unit-label normalizer is a spec, not code.** The 60% threshold
  for detecting a letter-labelled building is a guess from one file and
  should be revisited the moment a second lettered roll exists.
- ~~Manual costs could reproduce the rate bug.~~ **Closed in `e71d382`.**
  The unit is looked up from the item, so a hand-typed figure on
  walls_ceiling is a rate. Freeform items are covered by the provisional
  $15 ceiling described above — which is itself the remaining soft spot.

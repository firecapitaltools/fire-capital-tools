# Writing the seed — design

**Design only. Nothing built, nothing written. 2026-08-30, master `08041f6`.**

The preview shipped in Part 70 and produces, for Oxford Pointe, **152
areas and 894 rooms**. This is the design for actually writing them.

## The scale, stated plainly

Measured on production today, read-only:

| | rows |
|---|---|
| Every area in Site DD, all assessments, ever | **2** |
| Every room | **1** |
| Every finding | **31** |
| **One Oxford Pointe seed** | **152 areas + 894 rooms** |

**A single import is roughly 350× the areas and 900× the rooms this
platform has ever held**, into the database carrying Michelle's live walk
(assessment 11, 23 findings, read-only by standing instruction).

That is the whole reason this document exists. None of it argues against
proceeding.

---

## 1. Transaction shape — one transaction

**One transaction, not batches.** `sqlite3` gives it for free: a single
connection, one implicit transaction, one `commit()` at the end, and a
`rollback()` on any exception.

**Batching is the wrong trade here, and the reason is the reconcile.** A
partial seed is worse than a failed one: if a write dies after 80 units,
the assessment now holds 80 areas that the *next* upload's reconcile will
correctly treat as **existing work to preserve**. The rules that protect
an inspector's real rooms — reuse, append the shortfall, never delete a
surplus — would faithfully protect 80 half-written units. **The safety
rule becomes the thing that entrenches the damage.**

So the requirement is not "make failure unlikely", it is **make partial
success impossible**. All-or-nothing.

### Is 1,046 rows in one transaction actually fine?

Yes, and it is worth stating why rather than assuming.

* SQLite handles this size trivially — it is a single-file database doing
  ~1,000 inserts, which is milliseconds of work, not seconds.
* The volume is 142 MB of 5,000 MB. `site_dd.db` is 96 KB; this seed adds
  on the order of 150 KB.
* Nothing else writes Site DD concurrently. There is one web process.

**Use `executemany` for the rooms**, not a loop of `create_room`, and take
the area ids from `lastrowid` per area. The current `create_room` also
does a `SELECT MAX(sort_order)` per call — 894 of those is 894 needless
round trips, and sort order is already known from the layout.

---

## 2. Rollback — and the answer is uncomfortable

**Checked on production, read-only, today:**

    volumeInstanceBackupList(/data)          -> 0 backups
    volumeInstanceBackupScheduleList(/data)  -> 0 schedules

The queries succeeded and returned empty lists — this is not a
permissions failure or an unsupported plan. **Railway's backup capability
exists for this volume and nothing is configured.** The mutations
`volumeInstanceBackupCreate`, `volumeInstanceBackupRestore`,
`volumeInstanceBackupScheduleUpdate` are all exposed to Jasper's own
account, so enabling it is his to do and does not need Michelle.

> **So today there is no restore point for `/data`. None. If a seed
> writes the wrong thing, nothing outside the application can put it
> back.**

That single fact decides this section.

### What a fingerprint does and does not do

The verification habit throughout this project is a content fingerprint
before and after. **It proves something changed. It cannot undo it.**
Every prior run restored production by *deleting the scratch row it had
just created* — a rollback by construction, available because the write
was one row we could name. 152 areas and 894 rooms is not that.

**"Delete the 152 areas by hand" is not a rollback.** It is a second
large write, performed under pressure, against a database in a state
nobody planned for.

### The design: a seed batch, recorded, reversible by construction

Three layers, cheapest first.

**a. A seed batch id, stored on every row the seed creates.**

A nullable `seed_batch` TEXT column on `site_dd_areas` and
`site_dd_rooms`, carrying one id per import. Then the rollback is one
statement per table, scoped exactly to what this import made:

    DELETE FROM site_dd_rooms WHERE seed_batch = ?
    DELETE FROM site_dd_areas WHERE seed_batch = ?

**It cannot touch anything a person made**, because a hand-created area
has `seed_batch = NULL`. It cannot touch a reused area either — reuse
does not set the column, since the area was not created by this batch.
This is the same additive-nullable-column pattern used four times
already, and the same "absent means not ours" discipline.

**One thing it does NOT solve, stated rather than glossed:** rooms
appended to a *reused* area carry the batch id and would be deleted,
which is right — but any finding an inspector recorded against one of
those rooms in the meantime would be orphaned. The undo must therefore
**refuse when any batch room has findings**, and say which. An undo that
destroys an inspector's work to correct our own is not an undo.

**b. A pre-write snapshot of the one file.**

Before writing, copy `site_dd.db` to
`/data/backups/site_dd.<batch>.db`. It is 96 KB; the volume has 4.8 GB
free. This is the only layer that survives *"the seed was fine but the
reconcile matched wrongly and reused an area it should not have"* — the
case (a) cannot reverse, because reuse leaves no trace.

Use SQLite's own `VACUUM INTO` or the backup API rather than a file copy,
so the snapshot is consistent rather than a copy of a file mid-write.

**c. ~~Ask Jasper to turn on Railway volume backups.~~ NOT AVAILABLE.**

> **Corrected 2026-08-30.** This said the backup capability existed and
> was merely unconfigured, and that enabling it was one person and one
> setting. **Both were wrong.** The workspace is on the **Hobby** plan,
> whose `subscriptionPlanLimit.volumes.maxBackupsCount` is **0**;
> `volumeInstanceBackupCreate` returns `Not Authorized` with a fresh
> token while every read succeeds. It is a billing decision on Michelle's
> account, not a setting. See known-issue 3.

**So layers (a) and (b) are not a supplement to infrastructure backups.
They are the only rollback that exists.** Nothing outside this
application can put `/data` back, today or after a bad seed, and that
raises the bar on both:

* the `seed_batch` undo must be exact, because there is no second chance
  behind it;
* the pre-write snapshot is **mandatory, not advisable** — it is the only
  layer that recovers a wrong *reuse*, which leaves no batch marker to
  delete.

**This does not block the seeding work.** Both layers are ours, cost
nothing, and do not depend on the plan. What gates the seed is that a
restore from the snapshot has actually been performed once — see
`docs/site-dd-restore-runbook.md`. An untested snapshot is a belief.

---

## 3. Idempotence under failure

Clean re-run idempotence comes from the reconcile: same keys, same areas,
rooms reconciled, nothing doubled. **That is not the hard property.**

The hard one is a seed that fails midway and is retried. §1's single
transaction largely answers it — a failed write leaves nothing, so the
retry is a first run — but two gaps remain and both need naming.

**a. The transaction covers the database, not the process.** If the
container is killed between `commit()` and the response being rendered,
the write succeeded and the user saw a failure. They retry. The reconcile
then sees 152 existing areas, matches all of them, appends nothing, and
reports "152 reused, 0 created" — **correct, and it looks like nothing
happened.** The preview must be able to say *"this file has already been
seeded into this assessment"* rather than showing a silent no-op.

The batch id gives that for free: if every matched area carries a
`seed_batch` and none is new, the screen says so.

**b. Two people, or two tabs.** Two simultaneous seeds of the same file
into one assessment would both read "no existing areas" and both write.
The rendered-state token built in Part 67 is exactly this problem and
exactly this answer: hash the assessment's areas at preview, carry it into
the write, refuse if it changed. **Reuse that helper rather than
inventing a second mechanism.**

---

## 4. What the user sees

**~1,046 inserts in one SQLite transaction is fast** — tens of
milliseconds, not seconds. The slow part is parsing the workbook, which
the preview already does and which took well under a second on the
container.

**So: the request blocks, and that is correct.** No background job, no
progress bar, no polling. Adding asynchrony here would introduce a job
runner this platform does not have, to solve a wait that does not exist.

**If the browser is closed mid-write**, the transaction still commits —
the work is server-side and the connection closing does not roll it back.
That is the §3a case: the write happened, the user did not see it. The
answer is the same, and it is the preview telling them next time rather
than a mechanism.

**One thing to get right:** the POST that writes must not be replayable
by a refresh. Redirect after write, and let the batch id make a second
submission visible as a re-seed rather than silently doubling.

---

## 5. Scale effects downstream — the part to know before, not after

152 areas and 894 rooms will flow into screens verified at two orders of
magnitude less. **None of this is a reason not to proceed. All of it is
worth measuring before the first real seed rather than discovering on
Michelle's screen.**

| consumer | today | after | risk |
|---|---|---|---|
| Assessment detail page | 2 areas | **152 area cards** | renders every area with a roll-up each; a page, not a crash |
| `summarize()` condition roll-up | 31 findings | unchanged initially | seeding creates no findings, so the roll-up is unaffected until someone walks |
| Capex export (XLSX) | 1 line | unchanged initially | same reason |
| **Capex PDF** | verified at **181 lines** | unchanged initially, then grows | **paginates by measured height**; 894 rooms of findings would be far beyond anything it has rendered |
| Room list per area | 1 | up to 7 | trivial |

**The important observation: seeding writes no findings.** Every
downstream consumer that hurts is driven by findings, not by areas and
rooms. So the scale arrives in two stages — the pages get long
immediately, and the exports only get long once someone actually walks
152 units.

**What to measure before the first seed**, and it is cheap: render the
assessment detail page against a seeded scratch assessment and time it.
If 152 area cards with roll-ups is slow, that is a paginate-or-summarise
decision, and it is much better made then than the first time Michelle
opens it.

**The PDF is the one to watch later**, not now. It was verified at 181
lines by explicit test, and the height-aware paginator was built because
a fixed row count could not describe a page whose rows differ in size.
A 152-unit walk would put thousands of lines through it. That is a
separate run and it should be triggered by findings arriving, not by
areas.

---

## 6. What this design does not answer

* **Which assessment a roll seeds into**, still open from the previous
  design. Seeding into a fresh assessment and into one already walked are
  different risks.
* **Whether `seed_batch` should also record the source filename and a
  timestamp.** Probably yes — it costs two columns and answers "where did
  these 152 units come from" a year from now — but it is a decision, not
  an obvious yes.
* **Undo in the UI, or undo as a script.** A destructive button next to a
  screen showing 152 units is its own hazard.

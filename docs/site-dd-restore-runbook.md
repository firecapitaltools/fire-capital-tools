# Restore runbook — Site DD

**For someone who is worried and in a hurry. Read §0, then go to the
section that matches.**

> # BEFORE ANYTHING ELSE: WHAT THIS RUNBOOK DOES NOT COVER
>
> **Nothing in this platform snapshots itself except `site_dd.db`, and
> only when a seed is applied.** The table is what exists on a day nobody
> typed anything. If what you have lost is not Site DD, the honest answer
> is that there is probably no snapshot of it, and you should learn that
> here rather than by reading three sections and finding no instructions.
>
> **§0a can change that in 0.37 seconds, but only going forward** — a set
> taken today does not help with something lost yesterday. The repair
> procedures in §1–§3 are Site DD's; §0a and its restore direction are
> every database's.
>
> | | snapshot exists? |
> |---|---|
> | `site_dd.db` | **yes** — taken automatically before every seed, plus hand-taken ones. §2 and §3 below |
> | the other **eleven** databases | **no.** underwriting, deal_dive, investor_report, investor_notes, market_data_cache, scorecard_pro_history, fire_metrics, feedback, rent_comps, app_settings, openai_usage |
> | `/data/uploads` — 52 files, 2.1 MB | **no** |
> | `/data/users.json` — the account store | **no** |
> | platform-level volume backups | **YES since 2026-09-01** — Pro upgrade, DAILY (6-day retention) + MONTHLY (89-day), plus one locked manual backup. **No restore has ever been performed from one** — known-issue 3 |
>
> **`/data/backups` also holds four `keep-` files** — hand copies of
> deal_dive, investor_notes, underwriting and site_dd taken on 12–17
> August. They are point-in-time copies of a world three weeks old, not
> a backup regime. Their contents are listed under *Where snapshots
> live*.
>
> **Why the gap exists, so nobody assumes it was an oversight.** The Site
> DD snapshot hangs off `apply_seed`, the one write in this application
> big enough to justify copying a database first. The other eleven are
> written a form at a time, and **there is no scheduler in this platform**
> — no cron, no timer, no background job that is not a human clicking
> something. So there is nowhere for an automatic snapshot of them to
> hang.
>
> **What that is NOT is a cost problem.** Measured 2026-08-31: a
> `VACUUM INTO` of all twelve databases is content-identical and takes
> **16 ms**; a complete real set including `uploads` and `users.json`
> measured **3.22 MB in 0.37 s** against 4,816 MB free. (An earlier
> estimate here said 2.45 MB. That was measured against a scratch copy
> and the real uploads tar is larger — the figure that counts is the one
> from a real run.)
>
> **AND THERE IS NOW A COMMAND FOR IT — §0a.** `python -m
> tools.snapshot_all` covers every row in this table in 0.37 seconds.
> **The table still says "no", and that is deliberate**: it describes
> what is protected on a day nobody types anything, which is every day
> nobody types anything. The command changes what is possible, not what
> happens automatically.

**There ARE platform backups now, and they do not replace anything
below.** Michelle upgraded the workspace to Pro on 2026-08-31;
`maxBackupsCount` went from `0` to `10`, and on 2026-09-01 a manual backup
was taken and DAILY + MONTHLY schedules enabled. See known-issues entry 3
for the figures.

**Three things about them an operator needs before relying on them.**

1. **Nobody has ever restored from one.** The entitlement and the backups
   are verified; the recovery is not.
2. **A platform restore removes every backup newer than the one being
   restored**, which is why the application-level copies below are not
   superseded — they are the only thing that can protect the moment
   before a platform restore.
3. **A restore is staged, not instant, and does not overwrite in place.**
   Railway creates a NEW volume from the backup at the same mount point
   and retains the original, unmounted, after a change you have to review
   and commit. It also **redeploys the service**. Corrected 2026-09-01;
   this document previously implied a one-way overwrite.

**And it stays worth having even if the plan changes**, which is not
obvious and is worth one line: Railway's own documentation says
*"restoring a backup will remove any newer backups you may have created
after the backup you are restoring"*. A platform restore is destructive
to the backup set as well as to the volume. A `VACUUM INTO` file sitting
in `/data/backups` is not part of that set and survives it.

**Rehearsed 2026-08-30**, in `tests/test_snapshot_restore_rehearsal.py`
and once against a copy of real production content. It is not a plan; it
has been done.

---

## §0a — Before you touch anything: take a set

    railway ssh
    cd /app && PYTHONPATH=/app python -m tools.snapshot_all

**This is the first thing to do, before every procedure in this document
and before anything you are unsure about.** It writes every database,
`users.json` and the uploads into
`/data/backups/keep-set-<timestamp>/`, verifies each copy against its
source, and prints a fingerprint per file.

**Measured on production, 2026-08-31: 3.22 MB in 0.37 seconds.** There is
no reason to skip it for cost.

**It refuses rather than half-writing.** If any database cannot be copied
or any copy disagrees with its source, nothing is kept — so a set that
exists is a set that was complete when it was made.

### Verify a set before you rely on it

    python -c "from tools.snapshot_all import verify_set;                print(verify_set('/data/backups/keep-set-<timestamp>'))"

`sound: True` means every file still matches the fingerprint recorded
when the set was written. **A snapshot nobody checked is the same belief
in a different file** — and this takes a second.

### Restoring from a set

Copy the file back over the live one, exactly as §3 does for Site DD:

    cp /data/backups/keep-set-<timestamp>/underwriting.db /data/underwriting.db

**Rehearsed on `underwriting.db`, 2026-08-31, on a copy** — the Site DD
rehearsal was the only restore anybody had ever done here, and it would
have been a poor discovery that the others behave differently. Deleting
a scenario and 109 expense lines moved the content fingerprint from
`1d8667e24f8a8032` to `f53e1498d5f65325`; restoring the snapshot returned
it to `1d8667e24f8a8032` **exactly**, with all ten scenarios and all 109
expense lines back. Production was opened `mode=ro` throughout and was
unchanged afterwards.

> **THE COMMAND CHANGES WHAT IS POSSIBLE, NOT WHAT HAPPENS.** Nothing
> runs it. There is still no scheduler, and the table above still
> describes what is covered on a day nobody types anything. A set covers
> everything — from the moment somebody runs it, and not before.

---

## §0 — The Site DD one, if a set is more than you want

*§0a covers everything and takes 0.37 seconds, so prefer it. This is the
single-database version, kept because it is what the rehearsal used and
because it needs nothing but sqlite3.*

> ### TAKE A SNAPSHOT FIRST, EVEN IF YOU ARE ABOUT TO RESTORE ONE.
>
> **A restore is not reversible.** Copying an old snapshot over the live
> database discards everything since — including work somebody did while
> the problem was being noticed. Thirty seconds now makes that
> recoverable; skipping it makes it gone.

    railway ssh
    python - <<'EOF'
    import sqlite3, datetime
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = f"/data/backups/site_dd.before-restore.{stamp}.db"
    import os; os.makedirs("/data/backups", exist_ok=True)
    c = sqlite3.connect("file:/data/site_dd.db?mode=ro", uri=True)
    c.execute("VACUUM INTO ?", (dest,)); c.close()
    print("wrote", dest, os.path.getsize(dest), "bytes")
    EOF

---

## §1 — Which repair do you need?

| what went wrong | use |
|---|---|
| A seed created areas/rooms that should not exist | **§2**, the batch undo |
| A seed appended rooms to an area that already existed | **§2** — appended rooms carry the batch marker |
| **A seed matched an existing area and changed it** — its label, status or notes are wrong | **§3, the snapshot. §2 cannot help.** |
| The database is corrupt, or you do not know | **§3** |

**Why the third row is different, and it is the one to understand before
you need it.** A wrongly *reused* area was not created by the seed, so it
carries no `seed_batch` marker. Nothing distinguishes it from an area a
person edited by hand — which is exactly why a batch delete must not
touch it, and why only a point-in-time copy recovers it.

---

## §2 — First resort: undo one seed batch

Reaches only rows the seed **created**. Cannot damage anything a person
made, because those carry `seed_batch = NULL`.

**Check what it would remove, before removing it:**

    SELECT COUNT(*) FROM site_dd_areas WHERE seed_batch = :batch;
    SELECT COUNT(*) FROM site_dd_rooms WHERE seed_batch = :batch;

**Refuse to proceed if any batch room has findings.** An undo that
destroys an inspector's work to correct ours is not an undo:

    SELECT COUNT(*) FROM site_dd_findings f
      JOIN site_dd_rooms r ON r.id = f.room_id
     WHERE r.seed_batch = :batch;
    -- must be 0. If not, stop and use §3.

**Then:**

    DELETE FROM site_dd_rooms WHERE seed_batch = :batch;
    DELETE FROM site_dd_areas WHERE seed_batch = :batch;

---

## §3 — Second resort: restore the snapshot

### Where snapshots live

**`/data/backups/`. One place, and as of 2026-08-31 that is true without
a caveat** — six older snapshots were sitting beside their databases in
`/data` as `<database>.pre_<something>`, and they were moved in.

    ls -la /data/backups/

Seven files today:

| file | what it is |
|---|---|
| `site_dd.before-first-seed.20260831-033837.db` | taken by hand before the first real seed |
| `site_dd.seed-20260831-034509-7759d0.db` | taken by `apply_seed` before the first write into assessment 21 |
| `site_dd.seed-20260831-034600-0c16c9.db` | and before the re-seed after the undo |
| `deal_dive.keep-pre_part14.db` | 2026-08-12, moved 2026-08-31 |
| `investor_notes.keep-pre_part14.db` | 2026-08-17, moved 2026-08-31 |
| `underwriting.keep-pre_part14.db` | 2026-08-16, moved 2026-08-31 |
| `site_dd.keep-pre_part14.db` | 2026-08-17, moved 2026-08-31 |

**Two of the six were dropped, not moved.** `deal_dive.db.pre_stepd` and
`underwriting.db.pre_stepd` were byte-identical to their `pre_part14`
twins — **re-verified by sha256 in the same script, immediately before
each `os.remove`, rather than on the strength of a measurement taken in
an earlier run** — and the survivor was opened and `PRAGMA
integrity_check`ed before its twin was removed. Six files, four kept.

Every one of the four holds only rows the live databases already have,
unchanged; the differences that first showed up were entirely columns
added since, which the projection method settled (HANDOFF, *"Same rows,
different hash"*). They are kept because a snapshot costs 20–100 KB and
"we checked once" is a worse reason to delete than "it holds nothing" is
to keep.

### Retention, and why nothing here can be pruned by accident

`prune_snapshots()` runs inside `apply_seed`, immediately after the
snapshot and before any write: it keeps everything from the last **30
days** and at least the **newest ten**, never deletes the newest whatever
its age, and **only ever considers files matching `site_dd.seed-*.db`**.
What it removed is returned in the result and named in the confirmation.

Checked against the real directory rather than asserted: of the seven
files above, the pruner's glob matches **two** — the two `seed-` ones.

**So every hand-taken snapshot is exempt by construction.**
`take_snapshot()` names its own output and a batch id always begins
`seed-`, so nothing a person named can match. That is what protects
`site_dd.before-first-seed.20260831-033837.db`, the only copy of the
state before the largest write this platform has made, with no platform
backup behind it (known-issue 3) — and it protects it without anybody
remembering to.

**Name a deliberate keep `<database>.keep-<what>.db`.** The exemption is
structural either way; the prefix is so the intent is legible in a
directory listing instead of living in somebody's memory.

### Verify the snapshot BEFORE relying on it

A snapshot nobody checked is the same belief in a different file. A
truncated or empty file raises here rather than silently restoring
nothing — both cases are covered by the rehearsal tests.

    python - <<'EOF'
    import sqlite3, sys
    snap = sys.argv[1] if len(sys.argv)>1 else "/data/backups/<file>.db"
    c = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
    for t in ("site_dd_assessments","site_dd_areas","site_dd_rooms","site_dd_findings"):
        print(f"{t:24}", c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    c.close()
    EOF

**Do the counts look like the world you expect?** If findings are zero and
they should not be, that snapshot is the wrong one.

### Restore

    cp /data/backups/site_dd.<the one you verified>.db /data/site_dd.db

### Confirm it worked

Compare content, not bytes. `VACUUM INTO` rewrites page layout, so a byte
hash differs on a *correct* restore and will send you hunting a defect
that is not there.

    python - <<'EOF'
    import hashlib, json, sqlite3
    T = ("site_dd_assessments","site_dd_areas","site_dd_rooms",
         "site_dd_findings","site_dd_media")
    c = sqlite3.connect("file:/data/site_dd.db?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    b = {t: [dict(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY id")] for t in T}
    c.close()
    print((sum(len(v) for v in b.values()),
           hashlib.sha256(json.dumps(b, sort_keys=True, default=str)
                          .encode()).hexdigest()[:16]))
    EOF

**Known-good values** — assessment 11 is read-only by standing
instruction, so it is the sharpest check available:

| | |
|---|---|
| whole-database fingerprint, 2026-08-31 | `(1085, '687e30e37f036e32')` |
| *before the first Oxford Pointe seed* | ~~`(39, 'bedad2a7023d64a2')`~~ |
| *before the `seed_batch` migration* | ~~`(38, '1d980444f657b0bb')`~~ |
| assessment 11's findings | `(23, 'f6451ecb366f6ab4')` |

The whole-database figure moves whenever anything legitimately changes. It
moved on 2026-08-30 when the additive `seed_batch` migration ran — the old
value comes back exactly when that column is projected out of the
computation, which is how that move was confirmed rather than assumed —
and again on 2026-08-31 when assessment 21 was seeded with 152 units and
894 rooms. **Assessment 11's does not and should not**, and it did not
move through any of it.

**A note on re-seeding, because the arithmetic invites a wrong
expectation.** Undoing a seed returns the whole-database figure to its
pre-seed value *exactly* — that is the check, and it was run on
production on 2026-08-31. Re-seeding afterwards produces a THIRD value,
not the first one: row ids and `created_at` differ. Do not read that as a
failed restore.

---

## §4 — What the rehearsal proves, and what it does not

**Proved**, on a scratch database and again on a copy of real production
content, with production opened `mode=ro` and never written:

* a `VACUUM INTO` snapshot carries the source's exact content;
* 152 injected areas, rooms appended to a real area, **and an existing
  area overwritten in place** are all reverted by a restore;
* the restored file matches the pre-damage fingerprint exactly, and
  assessment 11 comes back to `f6451ecb366f6ab4`;
* findings on a reused area survive intact;
* restoring an old snapshot discards newer work — and taking a snapshot
  first makes that recoverable;
* a truncated or empty snapshot raises rather than restoring nothing.

**Not established, and it needs production to establish:**

* **Whether the app must be stopped.** Every rehearsal restored a file
  nothing was serving. On the live container, `cp` over `site_dd.db`
  while Flask holds connections is not covered by anything tested here.
* **What happens to a request in flight.** A connection open across the
  replacement would be reading a file that has been swapped underneath
  it. SQLite tolerates a lot, and "tolerates" is not "verified".

**So the conservative order is: restart the service, then restore, then
restart again.** That is advice from the shape of the problem, not from a
measurement, and it is recorded that way deliberately. Confirming it
means restoring on production, which is not something to try for practice.

---

## §5 — What is not covered

* **The other eleven databases.** This runbook is Site DD. The same
  `VACUUM INTO` approach works for any of them — **verified on all twelve
  on 2026-08-31, content-identical, 16 ms for the set** — and none has a
  snapshot taken by anything today. What is missing is a trigger, not a
  mechanism: see HANDOFF, *The other eleven*.

  **If you are about to do something risky, take one by hand first.**
  There is no command for this yet; the shape is one `VACUUM INTO` per
  file, exactly as §0 does for Site DD, into `/data/backups` with a
  `keep-` name so the pruner cannot reach it.
* **Uploaded files** under `/data/uploads` — no snapshot, no backup.
  *(52 files, 2.15 MB on 2026-08-31; `du -sh /data/uploads` answers it
  and this line will not be maintained.)*
* **`users.json`** — the account store. Same.

**Those are real gaps.** They are not this runbook's job to fix, and they
are the argument for known-issue 3 being resolved at the plan level rather
than worked around one database at a time.

# Restore runbook — Site DD

**For someone who is worried and in a hurry. Read §0, then go to the
section that matches.**

**There is no platform backup.** The workspace is on Railway's Hobby plan
and `maxBackupsCount` is `0` — see known-issues entry 3. Everything below
is application-level and is the whole of the recovery story.

**Rehearsed 2026-08-30**, in `tests/test_snapshot_restore_rehearsal.py`
and once against a copy of real production content. It is not a plan; it
has been done.

---

## §0 — Before you touch anything

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

`/data/backups/site_dd.<label>.<timestamp>.db` on the volume. The
pre-write snapshot taken by the seeding run is named for its batch id.
As of 2026-08-31 there are three, all 90,112 bytes: one taken by hand
before the first real seed (`site_dd.before-first-seed.20260831-033837.db`)
and one taken by `apply_seed` itself before each of the two writes into
assessment 21.

    ls -la /data/backups/

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
  `VACUUM INTO` approach works for any of them; none has a snapshot taken
  by anything today.
* **Uploaded files** under `/data/uploads` — 51 files, 1.9 MB, no
  snapshot, no backup.
* **`users.json`** — the account store. Same.

**Those are real gaps.** They are not this runbook's job to fix, and they
are the argument for known-issue 3 being resolved at the plan level rather
than worked around one database at a time.

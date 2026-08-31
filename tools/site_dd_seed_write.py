"""Applying a seed plan — the only module here that writes.

`site_dd_seeding.py` plans and is asserted by test to call nothing that
writes. This module is the other half, kept separate so that assertion
stays meaningful rather than becoming a comment.

WHAT MAKES THIS DIFFERENT FROM EVERY OTHER WRITE IN THE PLATFORM

One Oxford Pointe seed is **152 areas and 894 rooms**. Every area in Site
DD, across all assessments, ever, is currently **2**; every room is **1**.
This is roughly 350x and 900x anything that has been written, into the
database holding Michelle's live walk.

And there is **no platform backup**: the workspace is on Railway's Hobby
plan with `maxBackupsCount: 0` (known-issues entry 3). The pre-write
snapshot below is not a precaution on top of infrastructure recovery. It
is the whole of it.

THE THREE PROPERTIES, IN THE ORDER THEY MATTER

1. **Partial success is impossible.** Not "failure is unlikely" -- a seed
   that dies after 80 units leaves 80 areas that the NEXT upload's
   reconcile would correctly treat as existing work to preserve. The rule
   protecting an inspector's rooms would entrench the damage. One
   transaction, one commit, `rollback()` on anything.
2. **The snapshot is taken by this code, not by an operator remembering.**
   A rollback that depends on somebody having thought of it beforehand is
   not a rollback.
3. **A completed-but-unacknowledged write is visible on retry.** If the
   commit lands and the response never reaches the browser, the user
   retries; without the batch id that second run reports "152 reused, 0
   created", which is correct and reads exactly like nothing happened.

── WIRED 2026-08-30. IT WAS A WAITING HALF FOR EXACTLY ONE MERGE. ─────

**`site_dd.seed_apply` calls `apply_seed`; `site_dd.seed_undo` calls
`undo_seed`.** The apply is the panel at the bottom of the seed preview,
which names the counts on the button itself; the undo sits beside the
batch id on the assessment page. The comment that stood here — nothing
calls this, no sweep can see it, and one press writes 1,046 rows — is
kept in the history rather than in the file, because a waiting-half
notice that outlives its wiring is worse than none: it tells the next
reader the feature is unreachable when it is reachable.

**What has NOT changed, and it is the part to carry forward:** neither
sweep covers this module. `tests/test_dead_readers.py` globs
`tools/*_db.py` and gates on `READER_PREFIXES`; `apply_seed` matches
neither. The route sweep sees routes, and the routes above are POST-only.
So if the apply panel is ever removed from the template, nothing
automated will notice this module has gone dark again —
`tests/test_sitedd_seed_route.py` is what would fail, because it
harvests the form out of the rendered page rather than posting to a URL
it typed.

**THE THREE GATES IN FRONT OF THE WRITE** live in the route, not here,
and they answer different failures: the held upload (this preview is
still the file that was read), the rendered-state token checked below
(the world has not moved under the reconcile), and a comparison of the
figures the person approved against the figures re-derived at write time
(the plan still means what the screen said). `apply_seed` refuses on the
second of those; the route refuses on the other two, and writes nothing
in either case.
────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import datetime
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from tools import rendered_state
from tools import site_dd_db as sdb

SNAPSHOT_DIR = "backups"

# ── Retention ────────────────────────────────────────────────────────────
#
# Every seed takes a snapshot and nothing ever deleted one, so the
# directory grew without bound. **The problem this bounds is legibility,
# not space** -- 5 GB against a snapshot the size of the database is not
# a capacity question for years, but fifty near-identical files named for
# batch ids is where somebody restores the wrong one at the worst
# possible moment. The runbook's "verify the snapshot before relying on
# it" step is exactly what gets skipped when there are fifty candidates.
#
# BOTH RULES, NOT EITHER. Ten seeds in one afternoon must not evict a
# month of history, and a quiet year must not leave a single file.
SNAPSHOT_KEEP_DAYS = 30
SNAPSHOT_KEEP_COUNT = 10

# ONLY FILES THIS CODE WROTE ARE EVER CONSIDERED FOR DELETION.
#
# `take_snapshot` names its files `site_dd.<batch>.db`, and a batch id
# always begins `seed-`. So a snapshot somebody took by hand cannot match
# this pattern, and is therefore exempt **by construction rather than by
# an exclusion list somebody has to maintain** -- an exclusion list is a
# thing to forget, and the file it protects is the one that matters most.
# `site_dd.before-first-seed.20260831-033837.db` is the state before the
# largest write this platform has made, and there is no platform backup
# behind it (known-issues 3).
SNAPSHOT_PRUNE_GLOB = "site_dd.seed-*.db"

# THE CONVENTION FOR A DELIBERATE KEEP: name it `site_dd.keep-<what>.db`.
# It does not match the glob above either -- nothing does except this
# code's own output -- but a name that says "keep" puts the intent in the
# filename instead of in somebody's memory, which is the same move as
# `seed_batch` itself.
SNAPSHOT_KEEP_PREFIX = "site_dd.keep-"


class SeedRefused(Exception):
    """The seed did not run, and nothing was written."""


def new_batch_id() -> str:
    """One id per import. Timestamped so a directory listing of snapshots
    reads chronologically, and random-suffixed so two seeds in the same
    second cannot collide."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"seed-{stamp}-{secrets.token_hex(3)}"


def snapshot_path(batch: str, db_path: Path | None = None) -> Path:
    base = Path(db_path or sdb.get_db_path())
    return base.parent / SNAPSHOT_DIR / f"site_dd.{batch}.db"


def take_snapshot(batch: str, db_path: Path | None = None) -> Path:
    """A point-in-time copy, before anything is written.

    `VACUUM INTO`, not a file copy. It is transaction-consistent by
    construction; a copy of a live SQLite file can catch it mid-write.
    Every database here is `journal=delete` + `synchronous=FULL`, which
    makes such a copy *recoverable* -- and "recoverable" is a weaker
    promise than "consistent", and this is the one place not to take the
    weaker one.

    Rehearsed in tests/test_snapshot_restore_rehearsal.py, including
    against a copy of real production content.
    """
    source = Path(db_path or sdb.get_db_path())
    dest = snapshot_path(batch, source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()
    return dest



def prune_snapshots(db_path: Path | None = None,
                    now: float | None = None) -> list[str]:
    """Delete seed snapshots that are both old and surplus. Returns the
    names it removed, oldest first.

    THE THREE GUARANTEES, in the order they are enforced:

    1. **Only `site_dd.seed-*.db` is a candidate.** Anything else in the
       directory -- a hand-taken snapshot, a `keep-` file, a stray copy
       of another database -- is never looked at again after the glob.
    2. **The newest survives whatever its age.** A retention rule that
       can empty the directory is not a retention rule, and a single
       ancient snapshot is precisely the case where it would.
    3. **A file must be BOTH older than the window AND outside the count
       to go.** Either alone keeps it.

    Housekeeping never fails a seed: a file that cannot be removed is
    left where it is and simply not reported, because losing the write
    to tidy up would invert the priorities completely.
    """
    base = Path(db_path or sdb.get_db_path())
    folder = base.parent / SNAPSHOT_DIR
    if not folder.is_dir():
        return []

    now = time.time() if now is None else now
    cutoff = now - SNAPSHOT_KEEP_DAYS * 86400

    # Newest first. mtime is the fact; the name is the tie-break so two
    # snapshots written in the same second still order deterministically.
    candidates = sorted(
        (p for p in folder.glob(SNAPSHOT_PRUNE_GLOB) if p.is_file()),
        key=lambda p: (p.stat().st_mtime, p.name), reverse=True)

    removed: list[str] = []
    for index, path in enumerate(candidates):
        if index < max(SNAPSHOT_KEEP_COUNT, 1):      # rule 2 rides on the 1
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path.name)
    return sorted(removed)


def already_seeded(conn, assessment_id: int) -> list[str]:
    """Batch ids that have already written into this assessment.

    THE ANSWER TO A LOST RESPONSE. A commit whose reply never arrived
    looks, on retry, exactly like a no-op: the reconcile matches all 152
    areas and appends nothing. This is what lets the screen say "this has
    already been seeded" instead of showing a silent success.
    """
    rows = conn.execute(
        "SELECT DISTINCT seed_batch FROM site_dd_areas "
        "WHERE assessment_id = ? AND seed_batch IS NOT NULL "
        "ORDER BY seed_batch", (assessment_id,)).fetchall()
    return [r[0] for r in rows]


def apply_seed(assessment_id: int, plan: dict[str, Any],
               reconcile: dict[str, Any], *, form=None,
               batch: str | None = None) -> dict[str, Any]:
    """Write the plan. All of it, or none of it.

    `form` carries the rendered-state token from the preview. Two people
    previewing the same assessment and both submitting would otherwise
    both apply -- the second one's reconcile having been computed against
    a world that no longer exists. That is the Part 67 problem exactly,
    so it uses the Part 67 helper rather than a second mechanism.
    """
    batch = batch or new_batch_id()
    snapshot = take_snapshot(batch)
    # Immediately after, and before anything is written: the seed is the
    # only thing that creates snapshots, so it is the honest place to
    # bound them. There is no scheduler in this platform and adding one
    # for a directory listing would be a worse trade than the problem.
    pruned = prune_snapshots()

    created_areas = created_rooms = 0
    with sdb.get_connection() as conn:
        # Checked INSIDE the connection and before any write, so the
        # world cannot change between the check and the transaction.
        if form is not None:
            areas_now = sdb.list_areas(conn, assessment_id)
            if not rendered_state.matches(form, areas_now):
                raise SeedRefused(rendered_state.STALE_MESSAGE)

        prior = already_seeded(conn, assessment_id)

        try:
            for area_plan in reconcile["areas"]:
                unit = area_plan.unit
                if area_plan.existing_area_id is None:
                    area_id = _insert_area(conn, assessment_id, unit, batch)
                    created_areas += 1
                    wanted = list(unit.layout.rooms)
                    have: dict[str, int] = {}
                else:
                    area_id = area_plan.existing_area_id
                    wanted = list(unit.layout.rooms)
                    have = _room_counts(conn, area_id)
                created_rooms += _append_rooms(conn, area_id, wanted, have, batch)
            conn.commit()
        except Exception:
            # A half-seeded assessment is worse than a failed one.
            conn.rollback()
            raise

    return {
        "batch": batch,
        "snapshot": str(snapshot),
        # Reported, not silent. A deletion nobody sees is how the next
        # restore finds a gap it cannot explain.
        "pruned_snapshots": pruned,
        "created_areas": created_areas,
        "created_rooms": created_rooms,
        "reused_areas": reconcile["reuse_count"],
        "previously_seeded": prior,
    }


def _insert_area(conn, assessment_id: int, unit, batch: str) -> int:
    """One area, carrying its batch id and the notes the status collapse
    would otherwise lose."""
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM site_dd_areas "
        "WHERE assessment_id = ?", (assessment_id,)).fetchone()
    notes = "; ".join(unit.notes) or None
    cur = conn.execute(
        """INSERT INTO site_dd_areas
           (assessment_id, kind, label, status, sort_order, notes,
            created_at, seed_batch)
           VALUES (?, 'unit', ?, ?, ?, ?, ?, ?)""",
        (assessment_id, unit.label[:sdb.MAX_LABEL_LEN], unit.status.mapped,
         row["n"], notes, sdb._now(), batch))
    return cur.lastrowid


def _room_counts(conn, area_id: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in conn.execute(
            "SELECT room_type FROM site_dd_rooms WHERE area_id = ?", (area_id,)):
        out[r[0]] = out.get(r[0], 0) + 1
    return out


def _append_rooms(conn, area_id: int, wanted, have: dict[str, int],
                  batch: str) -> int:
    """Only the shortfall. Never a deletion, never a finding.

    A rent roll can say a room is missing. It cannot say a room an
    inspector recorded does not exist -- so a surplus is left exactly
    where it is, and nothing here issues a DELETE at all.

    `executemany` rather than `create_room` per room: 894 calls would each
    run their own `SELECT MAX(sort_order)`, and the walk order is already
    known from the layout.
    """
    start = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM site_dd_rooms "
        "WHERE area_id = ?", (area_id,)).fetchone()["n"]
    remaining = dict(have)
    rows = []
    for spec in wanted:
        if remaining.get(spec.room_type, 0) > 0:
            remaining[spec.room_type] -= 1        # reuse what is there
            continue
        rows.append((area_id, spec.room_type, spec.label,
                     start + len(rows), sdb._now(), batch))
    if rows:
        conn.executemany(
            """INSERT INTO site_dd_rooms
               (area_id, room_type, label, sort_order, created_at, seed_batch)
               VALUES (?, ?, ?, ?, ?, ?)""", rows)
    return len(rows)


# ── The undo ─────────────────────────────────────────────────────────────

class UndoRefused(Exception):
    """The undo did not run, and nothing was deleted."""


def undo_seed(assessment_id: int, batch: str) -> dict[str, Any]:
    """Remove exactly what one seed created. Nothing else, ever.

    WHAT IT CANNOT REACH, AND THAT IS CORRECT.

    An area the reconcile REUSED carries no batch id, because this seed
    did not create it. If a seed matched the wrong area and overwrote its
    label or status, that row is indistinguishable from one an inspector
    edited by hand -- and an undo that guessed would delete real work.
    That case is the snapshot's, and the runbook routes it there.

    IT REFUSES WHEN SOMEBODY HAS WALKED THE SEEDED ROOMS.

    An undo that destroys an inspector's findings to correct our own
    mistake is not an undo. It names the rooms rather than reporting a
    count, so the person deciding can see what they would lose.
    """
    with sdb.get_connection() as conn:
        blocking = conn.execute(
            """SELECT r.id, r.room_type, r.label, COUNT(f.id) AS findings
                 FROM site_dd_rooms r
                 JOIN site_dd_findings f ON f.room_id = r.id
                WHERE r.seed_batch = ?
             GROUP BY r.id HAVING COUNT(f.id) > 0""", (batch,)).fetchall()
        if blocking:
            named = ", ".join(
                f"room {b['id']} ({b['label'] or b['room_type']}): "
                f"{b['findings']} finding{'s' if b['findings'] != 1 else ''}"
                for b in blocking)
            raise UndoRefused(
                f"This import cannot be undone: somebody has recorded "
                f"findings in rooms it created. {named}. Undoing would "
                f"delete that work. Use the snapshot instead — see "
                f"docs/site-dd-restore-runbook.md.")

        rooms = conn.execute(
            "DELETE FROM site_dd_rooms WHERE seed_batch = ?", (batch,)).rowcount
        areas = conn.execute(
            "DELETE FROM site_dd_areas WHERE seed_batch = ? AND assessment_id = ?",
            (batch, assessment_id)).rowcount
        conn.commit()
    return {"batch": batch, "deleted_areas": areas, "deleted_rooms": rooms}

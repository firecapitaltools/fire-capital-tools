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

── A HALF THAT SHIPPED ALONE. IT IS FINISHED; IT IS NOT WIRED. ─────────

**NOTHING CALLS `apply_seed()` OR `undo_seed()`.** That is deliberate and
it is not "unfinished": both are built, tested and merged, and the write
was merged on purpose without a way to reach it, so that the first real
seed is a decision somebody makes rather than a button that already
exists. See HANDOFF, *Decision: the first real seed goes into a FRESH
assessment*.

**The other half is a route.** `site_dd.seed_preview` renders what a seed
would do and writes nothing; what is missing is the POST that applies the
previewed plan, and a path that reaches `undo_seed()` for an assessment
that carries a batch. The preview already computes the plan and the
reconcile the write needs, so wiring it is a route and a template, not a
redesign.

**NO SWEEP COVERS THIS MODULE, so nothing will remind anybody.**
`tests/test_dead_readers.py` walks `tools/*_db.py` only, and gates on
`READER_PREFIXES` — `apply_seed` and `undo_seed` match neither the glob
nor the prefixes. `tests/test_route_reachability.py` sees routes, and
there is no route here to see. This is the sixth instance of the dead-path
shape and the first found in a module whose consequence is a 1,046-row
write, which is why it is written here rather than only in a document.

**IS IT SAFE TO WIRE AS IT STANDS? Yes — and know what wiring means.**
Unlike `site_dd_costs.to_capex_lines()`, this has not drifted behind
anything: it is current, it is the only implementation, and its tests run
against the same reconcile the preview renders. What it does NOT need is a
correctness fix before use. What it DOES need is that whoever connects it
understands the button they are creating: **one press writes 152 areas
and 894 rooms**, roughly 350x and 900x anything this platform has held,
into the database carrying Michelle's live walk, with no platform backup
behind it (known-issues 3). The confirmation step is therefore part of
the wiring, not a nicety — it must name the figures, and the write must
stay gated on the rendered-state token this module already checks.
────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import datetime
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from tools import rendered_state
from tools import site_dd_db as sdb

SNAPSHOT_DIR = "backups"


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

"""Copy everything on the volume, once, because you are about to do
something you are not sure about.

WHAT THIS IS

    python -m tools.snapshot_all

One command that writes a point-in-time copy of all twelve databases,
`users.json` and the uploads directory into `/data/backups/keep-set-<when>/`,
verifies every copy against its source, and prints what it wrote.

WHAT THIS IS NOT, AND THE DISTINCTION IS THE WHOLE POINT

**It is not cover. It is not a backup regime. It is not a substitute for
the platform backups Michelle has been asked about.** Nothing runs it.
There is no scheduler in this platform — no cron, no timer, no background
job that is not a person clicking something — so this protects exactly
the moments somebody remembers to type it and no others.

A snapshot mechanism nobody triggers reads as cover in a runbook while
covering nothing, and this project has already found a partial defence
being cited as a whole one. So: **run this before a migration, before a
bulk write, before deleting anything, before a deploy you are unsure
about.** Then say in the report that you did.

WHY IT EXISTS AT ALL

Three times in two weeks somebody improvised exactly this — a bespoke
`VACUUM INTO` before the first real seed, ad-hoc reads before deleting
158 branches, and again before moving six snapshot files. That is an
observed need rather than a predicted one, and **each improvisation was a
fresh chance to get `mode=ro` wrong** on a live database. This module
gets it right once.

THE THREE PROPERTIES THAT MATTER

1. **Read-only at every source.** Every database is opened
   `file:...?mode=ro`, which fails CLOSED — a write attempt raises rather
   than succeeding quietly. That is the specific thing three improvised
   scripts each risked.
2. **A partial set cannot appear.** The whole set is built in a hidden
   directory and renamed into place only when every file is written AND
   every fingerprint matches. A set missing three databases is the
   partial-defence problem again, and it must not be possible to end up
   with one silently.
3. **It verifies before you rely on it, not after you need it.** Each
   database's content fingerprint is computed from the SOURCE and from
   the COPY and compared, and both go in the manifest so `verify_set()`
   can check the set again later without the source.

WHERE IT WRITES, AND WHY THE NAME MATTERS

`/data/backups/keep-set-<timestamp>/`. The `keep-` prefix is the existing
convention for "a person made this deliberately", and the seed pruner
only ever considers files matching `site_dd.seed-*.db` — so a set is
exempt by construction rather than by an exclusion list, the same
guarantee `site_dd.before-first-seed…` relies on.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import time
from pathlib import Path
from typing import Any

BACKUP_DIR = "backups"
SET_PREFIX = "keep-set-"
MANIFEST = "MANIFEST.json"

# Everything on the volume that is not itself a snapshot.
UPLOADS_DIR = "uploads"
USER_STORE = "users.json"


class SnapshotRefused(Exception):
    """Nothing usable was written. The partial set has been removed."""


def data_dir() -> Path:
    """The volume, taken from the Site DD path rather than hardcoded.

    Every database resolves its own `*_DB_PATH` and they all land in the
    same directory; borrowing one keeps this module honest in a test that
    redirects them, and stops `/data` being written into a fourth place.
    """
    from tools import site_dd_db as sdb

    return Path(sdb.get_db_path()).parent


def content_fingerprint(path: Path | str) -> str:
    """A hash of what a database CONTAINS, not of its bytes.

    THE ALGORITHM IS STATED BECAUSE AN UNREPRODUCIBLE FINGERPRINT IS NOT
    A CHECK. Every table except SQLite's own, every row, each row
    serialised as sorted key/value JSON, **the serialised rows sorted**,
    then sha256, first 16 hex characters.

    Rows are sorted rather than taken in natural order on purpose:
    `VACUUM INTO` rewrites the file in rowid order, so a source whose
    physical order differs would produce a false mismatch and send
    somebody hunting a corruption that is not there. Sorting compares
    content and nothing else.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        blob: dict[str, list[str]] = {}
        for table in tables:
            rows = [json.dumps(dict(r), sort_keys=True, default=str)
                    for r in conn.execute(f"SELECT * FROM {table}")]
            blob[table] = sorted(rows)
    finally:
        conn.close()
    return hashlib.sha256(
        json.dumps(blob, sort_keys=True).encode()).hexdigest()[:16]


def _databases(source: Path) -> list[Path]:
    """The volume's databases: top level only, snapshots excluded.

    `/data/backups` holds copies of these same files, and a snapshot of
    the snapshots is both useless and unbounded.
    """
    return sorted(p for p in source.glob("*.db") if p.is_file())


def snapshot_all(source: Path | str | None = None,
                 label: str | None = None) -> dict[str, Any]:
    """Write and verify one complete set. Returns what it wrote.

    Raises `SnapshotRefused` and leaves nothing behind if any database
    cannot be copied or any copy disagrees with its source.
    """
    started = time.time()
    source = Path(source) if source else data_dir()
    backups = source / BACKUP_DIR
    backups.mkdir(parents=True, exist_ok=True)

    stamp = label or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    final = backups / f"{SET_PREFIX}{stamp}"
    if final.exists():
        raise SnapshotRefused(f"{final} already exists; nothing was written.")

    # Built hidden, renamed on success. The rename is the commit: a
    # reader listing /data/backups never sees a half-written set under a
    # name that looks complete.
    staging = backups / f".partial-{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    entries: list[dict[str, Any]] = []
    try:
        for db in _databases(source):
            out = staging / db.name
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                conn.execute("VACUUM INTO ?", (str(out),))
            finally:
                conn.close()
            before, after = content_fingerprint(db), content_fingerprint(out)
            if before != after:
                raise SnapshotRefused(
                    f"{db.name}: the copy does not match its source "
                    f"({before} vs {after}). Nothing was kept.")
            entries.append({"name": db.name, "kind": "database",
                            "bytes": out.stat().st_size,
                            "fingerprint": after})

        store = source / USER_STORE
        if store.exists():
            shutil.copy2(store, staging / USER_STORE)
            entries.append({"name": USER_STORE, "kind": "file",
                            "bytes": (staging / USER_STORE).stat().st_size,
                            "fingerprint": hashlib.sha256(
                                store.read_bytes()).hexdigest()[:16]})

        uploads = source / UPLOADS_DIR
        if uploads.is_dir():
            tar_path = staging / "uploads.tar.gz"
            count = 0
            with tarfile.open(tar_path, "w:gz") as tar:
                for path in sorted(uploads.rglob("*")):
                    if path.is_file():
                        tar.add(path, arcname=str(path.relative_to(uploads)))
                        count += 1
            entries.append({"name": "uploads.tar.gz", "kind": "archive",
                            "bytes": tar_path.stat().st_size, "files": count,
                            "fingerprint": hashlib.sha256(
                                tar_path.read_bytes()).hexdigest()[:16]})

        if not any(e["kind"] == "database" for e in entries):
            raise SnapshotRefused(
                f"No databases found under {source}; a set with no database "
                f"in it is not a snapshot. Nothing was kept.")

        manifest = {
            "taken_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "source": str(source),
            "databases": sum(1 for e in entries if e["kind"] == "database"),
            "bytes": sum(e["bytes"] for e in entries),
            "entries": entries,
            # Stated in the set itself, so somebody restoring in a year
            # can check a fingerprint without reading this module.
            "fingerprint_algorithm":
                "sha256 of {table: sorted([json(row, sort_keys)])}, first 16 hex",
        }
        (staging / MANIFEST).write_text(
            json.dumps(manifest, indent=1), encoding="utf-8")
        os.replace(staging, final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    manifest["path"] = str(final)
    manifest["seconds"] = round(time.time() - started, 2)
    return manifest


def verify_set(path: Path | str) -> dict[str, Any]:
    """Re-check a set against its own manifest, without its source.

    A snapshot nobody checked is the same belief in a different file.
    This is what the runbook means by "verify before relying on it": it
    recomputes every database's fingerprint from the copy and compares it
    with what was recorded when the set was written.
    """
    path = Path(path)
    manifest_file = path / MANIFEST
    if not manifest_file.exists():
        raise SnapshotRefused(
            f"{path} has no {MANIFEST}; it is not a set this wrote, and "
            f"nothing here can vouch for it.")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    checked, bad, missing = [], [], []
    for entry in manifest["entries"]:
        target = path / entry["name"]
        if not target.exists():
            missing.append(entry["name"])
            continue
        if entry["kind"] == "database":
            now = content_fingerprint(target)
        else:
            now = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
        (checked if now == entry["fingerprint"] else bad).append(entry["name"])
    return {"path": str(path), "taken_at": manifest.get("taken_at"),
            "ok": checked, "mismatched": bad, "missing": missing,
            "sound": not bad and not missing}


def _report(manifest: dict[str, Any]) -> str:
    lines = [f"snapshot set: {manifest['path']}",
             f"taken       : {manifest['taken_at']}",
             f"databases   : {manifest['databases']}",
             f"total       : {manifest['bytes'] / 1e6:.2f} MB in "
             f"{manifest['seconds']}s",
             "",
             f"{'file':<28} {'bytes':>10}  fingerprint"]
    for entry in manifest["entries"]:
        lines.append(f"{entry['name']:<28} {entry['bytes']:>10}  "
                     f"{entry['fingerprint']}")
    lines += ["",
              "Verify it before relying on it:",
              f"  python -c \"from tools.snapshot_all import verify_set; "
              f"print(verify_set(r'{manifest['path']}'))\"",
              "",
              "This is not a backup regime. Nothing runs it but you."]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(_report(snapshot_all()))

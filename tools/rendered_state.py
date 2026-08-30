"""Was this form rendered against the data it is about to overwrite?

Three routes rewrite a whole collection: `underwriting.save_loans`,
`underwriting.save_capex` and `investor_report.save_gp_partners`. Each
does DELETE-then-INSERT, so **a row that is not in the post is destroyed**.
That is correct when the post is current -- it is how a user deletes a row
-- and it is data loss when the post is stale.

THE CASE THIS EXISTS FOR

Two sessions on one scenario. The first adds a fourth loan and saves. The
second, rendered when there were three, edits a rate and saves. Its post
carries three loans, the DELETE removes four, and the fourth is gone. No
error, no trace, and the person who added it finds out later or never.

WHY NOT A LIST OF ROW IDS

Considered in Part 49 and shown impossible in Part 52, for two reasons
that are still true:

* **The forms carry no row identity.** Loans and partners post parallel
  `getlist` arrays; capex posts a loop index. There is no id to list.
* **The ids churn.** All three tables are DELETE-then-INSERT on every
  save, so every row is reassigned an id each time. A manifest of ids
  would be stale the moment anything was written.

So this hashes the collection's CONTENT as it stood at render, embeds
that in the form, and recomputes it from the database at save. It needs no
row identity, it is immune to id churn, and it treats a deliberate
deletion exactly like any other unchanged-since-render post: allowed.

WHAT IT DOES NOT PROTECT AGAINST

Two people editing the same collection concurrently still cannot both
win. This turns a silent loss into a refusal, which is the whole claim --
not into a merge. Nobody has asked for a merge and merging two capex
budgets without row identity is not possible anyway.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

# The form field every guarded form posts back.
FIELD = "_rendered_state"

# `id` CHURNS AND MUST NOT BE HASHED.
#
# Every one of these tables is rewritten by DELETE-then-INSERT, so saving a
# collection unchanged still reassigns every row a new id. Hashing the id
# would make the token differ from itself across a save that changed
# nothing, and every second save would be refused.
#
# Nothing else is excluded, deliberately. Listing the fields to hash would
# be a second place to update when a column is added, and the failure mode
# of forgetting is silent: the token stops noticing changes to the new
# column and the guard quietly weakens. Hashing everything-but-id has the
# opposite failure mode -- a new column makes the token stricter, never
# looser.
EXCLUDED = ("id",)


def _normalise(value: Any) -> Any:
    """One representation per value, so the same row hashes the same way.

    SQLite hands back `1`/`0` for a boolean column and `1.0` for a REAL
    that holds a whole number. Both sides of this comparison read from the
    same database through the same accessor, so they already agree -- but
    they agree by circumstance rather than by construction, and a caller
    that one day builds rows in Python would break that quietly. Floats
    that are whole numbers collapse to int for the same reason.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def token(rows: Iterable[dict[str, Any]] | None) -> str:
    """A short hash of a collection as it stands.

    Order matters and is not sorted away: these collections are ordered by
    `sort_order`, the forms render them in that order, and two rows
    swapping places is a real change a user would want to keep.
    """
    payload = []
    for row in rows or ():
        item = {k: _normalise(v) for k, v in dict(row).items()
                if k not in EXCLUDED}
        # Keys sorted; the ROWS are not. See the docstring.
        payload.append([[k, item[k]] for k in sorted(item)])
    return hashlib.sha256(
        json.dumps(payload, default=str).encode("utf-8")).hexdigest()[:16]


def matches(form: Any, rows: Iterable[dict[str, Any]] | None) -> bool:
    """True when this form was rendered against exactly these rows.

    ABSENT IS A MISMATCH, NOT A PASS.

    A post with no token did not come from a page this code rendered --
    either it predates the guard, or it is not our form. Treating that as
    "cannot verify, proceed" would leave the hazard open on precisely the
    stale page the guard exists for: one rendered before the deploy is
    exactly a page that is out of date, and telling its owner to reload is
    the true answer rather than a workaround.

    The cost is one refusal, once, for a tab left open across a deploy.
    The message it produces is accurate for that case.
    """
    posted = (form.get(FIELD) or "").strip() if form is not None else ""
    return bool(posted) and posted == token(rows)


# What the user is told. One sentence of what happened, one of what to do,
# and no speculation about who else was editing -- the code knows the
# collection changed, not why or by whom.
STALE_MESSAGE = (
    "This page was showing an older version of this list, so saving it "
    "would have removed changes made since you opened it. Nothing was "
    "saved. Reload the page and reapply your edits."
)

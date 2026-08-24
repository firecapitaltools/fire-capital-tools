# The Site DD blanking hazard: what can actually produce it

**Investigated 2026-08-24 (Part 48). Nothing built. Production never
written to; every demonstration below ran against a temporary database.**

Standing rule 2 says full-collection-rewrite routes silently blank
anything a POST omits, and `save_area` was shown in Part 47 to do exactly
that. Site DD is the module whose design note says it works "in a basement
with no signal", so the question is whether a real inspector on a bad
connection can trigger it.

**Short answer: not by losing signal, and not by form size. Only by
submitting a page that predates the data — a stale render.**

---

## 1. What cannot produce it

| mechanism | verdict | evidence |
|---|---|---|
| dropped connection mid-submit | **no** | the body is length-delimited; a truncated request never reaches the route, and there is no background sync to replay a partial one |
| browser/server truncating a large form | **no** | 5,000 urlencoded fields arrive intact through Flask 3.1.3 / Werkzeug 3.1.8 — `max_form_parts` (1000) does not apply to urlencoded bodies |
| oversized body | **no** | exceeding `max_form_memory_size` (500 KB) returns **413**, a visible error, not a silent partial write |
| service worker serving a stale cached form | **no** | it bypasses `/tools/` explicitly and caches no authenticated route, and never handles POST |

**The PWA does not make this worse — it makes it better.** The service
worker's `BYPASS_PREFIXES` includes `/tools/`, so Site DD pages are never
served from cache. With no signal the inspector gets a failed navigation
or the offline page, not a stale form. "Works in a basement" turns out to
mean the shell installs, not that the forms work offline.

**Form size is not a factor.** The largest single page is a kitchen (18
checklist items) or a unit form (10 items plus up to 20 added bank items),
at roughly seven submitted fields per item — a few hundred fields against
a limit that tolerates thousands.

## 2. What can produce it

**A well-formed POST from a page rendered before an item existed.** Not a
network failure — an ordinary submission that is simply out of date.

Reachable paths, most to least likely:

1. **Back button.** No application route sets `Cache-Control: no-store` —
   the only cache header in the app is on the service worker itself — so
   the browser's back/forward cache may restore a form rendered earlier in
   the session. Change one field, save, and every item added since is
   blanked.
2. **Two tabs, or two devices.** Michelle reviewing an assessment while MJ
   walks it is the exact shape. The tab that loaded first wins, silently.
3. **A second writer of any kind** — the bank picker, "Add another", or
   `copy_layout` adding items while another page is open.

Within a single tab the inspector's own flow is safe: `add_room`,
`add_instance` and the picker are POST-redirect-GET, so the page re-renders
before the next save.

## 3. What is actually lost

Demonstrated end to end against a temp database: a complete save, then a
stale save that never mentioned the item.

```
condition        LOST: 'repair' -> None
note             LOST: 'cracked tile by the door' -> None
detail           lost the same way when set
quantity         lost the same way when set
est_unit_cost    kept: 450.0
est_cost_source  kept: 'manual'
instance_label   kept
bank_item_key    kept
finding row      NOT deleted -- 10 rows before, 10 after
photos           untouched (separate table, separate route)
```

**The money survives and the judgement does not.** `_kept_cost()`,
`_kept_label()` and `_kept_measure()` already implement "absent means
unchanged", and `bank_item_key` is `COALESCE`d in the upsert with a comment
naming this exact hazard. `condition`, `detail`, `note` and `quantity` are
plain assignments and are not defended.

**The downstream effect is worse than the row suggests.** A finding with a
null condition fails `needs_work()`, so it **drops out of the capital
budget entirely while keeping its $450 estimate**. The line does not appear
as unpriced or as a gap; it simply is not there.

## 4. Would anyone notice

**No.** There is no version check, no diff, no warning, and the redirect
lands on a page that renders the blanked item as merely unanswered —
identical to an item never filled in. The inspector's own note is gone
with nothing to say it existed.

Same shape as the Part 21 export bug and the `$5.75` capex total: not a
wrong number on screen, but a silent absence that reads as normal.

## 5. Proposed fixes, smallest first — none built

**Fix 1 — "absent means unchanged", mirroring what is already here.**
In `_collect()`, when an item's field is **not present in the form at
all**, keep the stored value instead of writing `None`.

This is safe because absent and empty are cleanly distinguishable: the
condition radio group renders an explicit blank option (`value=""`,
checked when there is no current answer), so **a rendered item always
submits its field**. Field present and empty is a deliberate clear; field
absent means the page never rendered the item. `_collect()` currently
collapses the two with `(form.get(...) or "").strip()`, which is the whole
defect.

Precedent in this codebase, twice: `_kept_cost()` does exactly this
("Absent means unchanged … a save from a page that predates them must not
silently downgrade a table figure"), and `save_expenses` carries
acquisition lines through because reading them from that request "would
find nothing and silently blank every amount". **Smallest change, matches
established shape, no schema or UI work.**

**Fix 2 — the form declares what it rendered.** A hidden field listing the
item keys on the page; the route touches only those. Stronger than Fix 1
because it also covers an item that was rendered but whose group went
missing, and it makes the contract explicit rather than inferred from
field presence. Costs a hidden field and a parse.

**Fix 3 — `Cache-Control: no-store` on tool pages.** Reduces the
back-button path specifically. Cheap, partial, and worth doing regardless
of 1 or 2, but it is a mitigation rather than a fix: it does nothing about
two tabs or two devices.

**Recommendation: Fix 1, with Fix 3 alongside.** Fix 2 only if a real
second-writer conflict is observed, since it adds a contract to every
form for a case Fix 1 already covers.

**Not proposed: optimistic locking or a conflict UI.** One inspector per
walk is the normal case, the data is per-item rather than per-document,
and a merge prompt in a basement is worse than the bug.

# The original handoff's eleven standing rules

**This file exists so the next rewrite of `HANDOFF.md` can be audited
against something.**

The document that opened this project carried eleven numbered standing
rules. `HANDOFF.md` replaced it in Part 11 — correctly, because it had
gone badly stale — and the replacement was created fresh rather than
edited, so **the original was never committed and there is nothing in git
to diff against**. Four of the eleven were dropped and nothing noticed for
thirty-six runs.

They survive here only because the person who wrote them still had them.
That is not a reliable archive, so this is one.

**Do not treat this as current.** It is a historical record, verbatim in
substance, kept for comparison. Where a rule has been superseded or
narrowed, the live statement is in `HANDOFF.md` and that one wins. The
Part 47 audit in `HANDOFF.md` records the disposition of each.

---

1. **Every persistent DB path**: env-var-with-fallback, verified via live
   in-process code, never trust the Railway dashboard. Any new
   `*_DB_PATH` must demonstrate both failure states (unset → visible red
   banner naming the var) and success, not just the good one.

2. **Full-collection-rewrite routes are dangerous.** Several routes this
   session (`save_area`, `save_expenses`, `save_capex`,
   `replace_expense_lines`) silently blank anything not included in a
   POST. Always post complete forms. Always snapshot before any real
   production write. Multiple real incidents happened and were recovered
   this session because of this pattern — **assume it applies to any route
   not yet audited.**

3. **Merge discipline, no exceptions**: fetch → confirm master hasn't
   moved (rebase + byte-hash-verify if it has) → merge → push → confirm
   deploy live via container code check → full suite pass → report before
   merging → never chain merges without a checkpoint.

4. **`deal_analyzer_math.py` is sacred.** Byte-hash-verify it untouched
   after every single Underwriting-adjacent change.

5. **No fabricated authority.** Any number/threshold not confirmed by
   Michelle or a real cited source ships with an explicit, test-enforced
   "not confirmed" disclaimer (established pattern:
   `deal_readiness_defaults.py`, reused in Quick Deal Analyzer's grading
   and Site DD's cost table).

6. **No scraping, ever.** Investigated and explicitly rejected for Home
   Depot/Lowe's/city-data.com — no public APIs exist, both are
   ToS-prohibited and actively block bots. Always look for a legitimate
   licensed source first (RSMeans flagged as the real paid alternative if
   repair-cost accuracy ever needs to go further).

7. **OpenAI spend discipline**: shared $60/month account cap exists; the
   in-app `openai_usage.py` counter tracks per-feature and must be used by
   any new AI feature, tagged correctly, with a real confirm-before-spend
   gate and caching.

8. **One prompt at a time**, easiest to hardest, report before merging
   each part separately — Jasper's explicit standing instruction. **Never
   combine build-and-merge into one silent action.**

9. **When investigation reveals the literal instruction was wrong or
   stale, say so and propose the correct thing** rather than building
   exactly what was asked. This happened repeatedly and productively this
   session — it is the expected, correct behavior, not a deviation to
   avoid.

10. **Reachability ≠ correctness.** Check that new features are actually
    linked/navigable by a real user, not just that they work when hit
    directly by URL.

11. **Census and BLS have no paid tiers at all** — free registration is
    the ceiling for both, not a starting point for an upgrade
    conversation.

---

## Disposition, as of Part 47

| # | disposition |
|---|---|
| 1 | **restored** to `HANDOFF.md`, widened to cover test redirection |
| 2 | **restored** to full weight; hazard re-verified live against the code |
| 3 | present throughout, intact |
| 4 | **superseded on purpose** by the two-signal behavioural fingerprint. Do not reinstate the byte-hash form. |
| 5 | **restored** |
| 6 | present, narrowed in Part 41 to its actual domain |
| 7 | present, generalised beyond OpenAI to every metered third-party call |
| 8 | half present. One-at-a-time and report-before-merging are enforced; the easiest-to-hardest ordering lapsed and was not restored, because work runs in the order the prompt sets. |
| 9 | **restored** |
| 10 | substance was present, the framing was restored |
| 11 | **not restored to `HANDOFF.md` — it lives in `tools/service_costs.py`**, which is better: structured, user-facing and carrying a `last_verified` date. The code is also more honest than the rule was, recording that the Census free tier "is near-certain but has not been formally confirmed" where the rule asserted it flatly. |

`tests/test_handoff_standing_rules.py` asserts that every rule marked
restored or present is still traceable in `HANDOFF.md`, so the next
rewrite drops one loudly instead of silently.

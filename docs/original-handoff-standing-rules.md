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

1. **Every persistent DB path** — env-var-with-fallback, verified via live
   in-process code, never trust the Railway dashboard. Any new
   `*_DB_PATH` must demonstrate both failure states (unset → visible red
   banner naming the var) and success, not just the good one.

2. **Full-collection-rewrite routes are dangerous.** `save_area`,
   `save_expenses`, `save_capex`, `replace_expense_lines` silently blank
   anything not included in a POST. Always post complete forms; always
   snapshot before a real production write. Multiple real incidents were
   recovered because of this.

3. **Merge discipline** — fetch, confirm master, merge, push, confirm
   deploy live, full suite, report before merging, never chain.

4. **`deal_analyzer_math.py` is sacred.**

5. **No fabricated authority.**

6. **No scraping.**

7. **OpenAI spend discipline** — shared cap, per-feature counter,
   confirm-before-spend, caching.

8. **One prompt at a time**, easiest to hardest, report before merging
   each part.

9. **When investigation shows the instruction was wrong or stale**, say so
   and propose the correct thing rather than building what was asked.

10. **Reachability is not correctness.**

11. **Census and BLS have no paid tiers at all.**

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

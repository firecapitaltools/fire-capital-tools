# Original handoff, 2026-08-16 — HISTORICAL, SUPERSEDED

> **`HANDOFF.md` is the current source of truth. This is not.**
>
> Preserved verbatim below the line. This is the document `HANDOFF.md`
> replaced in Part 11, and the one whose eleven standing rules were
> recovered in Part 47 — four of them had been dropped by the rewrite and
> nothing noticed for thirty-six runs, because **this document was never
> in the repo**. It could not be diffed, grepped or tested against. It is
> here now so the next rewrite can be.
>
> **Do not act on anything in it.** It records a moment, and much of it is
> now false.
>
> **Known false, listed rather than resolved:**
>
> * *"Paresh — confirmed he cannot provide the script/form … no reference
>   implementation ever existed"* — **false**. On being asked again he sent
>   four mature KoboToolbox instruments, v7 and v5, in production use. That
>   entry was load-bearing: it is why Site DD was rebuilt from scratch.
> * *"Cash-out refinance — confirmed, ready to build, not yet started"* —
>   built, merged, and the fee-base question it flagged was answered by
>   Michelle and resolved.
> * *"Repo transferred tonight … currently PUBLIC"* — the transfer is done
>   and settled; the repo is still public, and Michelle has since confirmed
>   Railway's GitHub app is granted on it explicitly.
> * *"Railway — NOT fully transferred, deliberately deferred"* — moved
>   since. The project now sits in Michelle Jeong's workspace.
> * *"Site DD Lite — whether this was implemented was never definitively
>   confirmed"* — confirmed twice since: designed only, never built.
> * *"Word export — build status unclear"* — built and merged (`9e8fdc5`).
> * *"`deal_analyzer_math.py` byte-hash-verified untouched"* — the
>   byte-hash rule was deliberately superseded by a two-signal behavioural
>   fingerprint. A branch that legitimately adds a function always fails a
>   byte-hash, and it proves nothing about behaviour.
> * *"Census and BLS — neither has a paid tier at all"* — stated flatly
>   here; `tools/service_costs.py` records the Census free tier as
>   "near-certain but has not been formally confirmed". **The code is the
>   more honest of the two.**
> * *"Rent Comps — Force Refresh confirm kept"* — still true, and a second
>   confirm was added in Part 45 for the subject-size override.
> * *"GSR handling check — status of completion unclear"* — still unclear.
>   Never revisited.
>
> **The eleven standing rules are audited separately** in
> `docs/original-handoff-standing-rules.md`, with the disposition of each.
> That file was originally written from a quotation of these rules rather
> than from this document; Part 50 diffed the two and corrected three
> transcription losses. See the audit in `HANDOFF.md`.
>
> Nothing below has been edited, reconciled or merged into `HANDOFF.md`.

---

# FIRE Capital Tools — Handoff Document
*Generated because the originating chat became too large to continue in. This is the complete state as of handoff.*

---

## ⚡ IMMEDIATE: WHAT'S RUNNING RIGHT NOW

**A prompt is currently executing in Codex/Claude Code as this handoff is being written.** It is Part 4 of a feedback-response queue:

- **Investigation only, no building yet**, covering two real feedback items from Michelle (found via the newly-built `/admin/feedback` page, entry from Aug 16 23:28, on Site DD assessment 11):
  1. Replace Site DD's condition summary with a property-header block (name, vintage, address, building count, sqft-optional)
  2. Rent-roll Excel upload into Site DD to auto-create unit records (deriving bedroom count from unit type, occupancy from Occupied/Vacant) — using a **real file**: `C:\Users\jaspe\Downloads\Jackson 0816 RR test.xlsx`
- Also confirms assessment 11 is real, current usage (new — prior reference point was assessment 6)

**First job in the new chat: receive and review this report when it comes back.** Do not re-send this prompt — check with the user whether it already completed before assuming it needs re-running (this session had recurring context-loss problems where completed work got mistaken for lost work).

---

## Who's who

- **Jasper Fredericks** — the user, intern building/maintaining this platform
- **Michelle Jeong** — client/owner (`5lments@gmail.com`, `415-794-8774`). Real estate GP running multiple properties (Eagle Rock, Jackson/1120 Jackson St, Oxford Pointe, Canyon, Maple Valley, Waterways, The View, River Oaks, Cannongate, Papania, plus "a few others")
- **Beckett Fredericks** — co-intern, works independently on FIRE Metrics + PWA installability. Has a pattern of pushing to master with failing/non-importing tests (flagged to him directly once this session — worth checking if it recurred)
- **Paresh** — external dev who built Michelle's *old* Site DD tool on KoboToolbox. **Confirmed he cannot provide the script/form** — Site DD was fully rebuilt from scratch based on Michelle's notes, no reference implementation ever existed

## Stack

Flask, Railway (auto-deploy from `master`), SQLite (many DBs on a persistent volume). Repo now at `github.com/firecapitaltools/fire-capital-tools` (transferred tonight, see below).

---

## 🔴 CRITICAL — Account/Ownership Transfer Status (very fresh, real live risk)

A live transfer session happened tonight. Current state:

| Service | Status |
|---|---|
| **GitHub** | ✅ Transferred to `firecapitaltools` (Michelle's account). Jasper + Beckett confirmed with write access. Local git remote updated to canonical URL. **Repo is currently PUBLIC** — flagged to Michelle twice (text + email with exact instructions), no confirmed reply yet. |
| **Railway** | ⚠️ **NOT fully transferred — deliberately deferred by Jasper ("I'll transfer it later").** Michelle added as project-level member with "Can Edit" only, not full workspace Owner/Admin. A literal ownership-transfer attempt failed earlier (Michelle wasn't yet on a paid plan) — she's since confirmed on Hobby, so a transfer would likely work now if attempted. Project renamed to "FIRE Capital Tools" (was "supportive-eagerness"). |
| **OpenAI** | ✅ Always Michelle's own account, no action needed. $60/month hard cap confirmed set. |
| **RentCast** | ✅ New key under Michelle's account, live in Railway, verified working. |
| **Google (Places+Maps)** | ✅ Michelle given Owner + billing moved on the **existing** project — no key rotation needed, both keys verified byte-identical and working. |
| **Census/BLS** | Untouched, deliberately low priority. Confirmed via research: **neither has a paid tier at all** — free registration is the ceiling for both. |

**⚠️ A real incident already happened once tonight**: the GitHub transfer broke Railway's deploy connection ("GitHub Repo not found") for roughly an hour before being caught and manually reconnected. **If picking this thread back up, check Railway's Settings → deploy source isn't broken again before assuming deploys are working.**

### The "ruvnet"/"claude" contributor scare — RESOLVED, no action needed
Michelle noticed unfamiliar GitHub contributors after the transfer made Insights visible. Fully investigated and resolved:
- **ruvnet** = 5 commits, all genuinely authored by Jasper, carrying a `Co-authored-by: RuFlo <ruv@ruv.net>` trailer from AI agent tooling he was using — zero actual repo access, purely cosmetic credit. Content verified safe (package splits + a diagnostic-only addition, no secrets introduced).
- **claude** = 97 commits, this and prior AI coding sessions' own commits (expected, benign — includes every commit made tonight).
- **Beckett was missing from the same Insights chart** for an unrelated reason: his commit email is an unmappable local hostname (`beckettfredericks@Becketts-MacBook-Air-2.local`), so GitHub shows his commits as Anonymous. Fix (not done): he should add that as a verified email or fix `git config user.email`.

---

## 🟡 Still Open — Needs Outside Input, Not Blocked on Building

- **Repo visibility** (public → private?) — asked Michelle twice, no confirmed reply
- **AWS Route 53 / `tools.investingwithfire.com` subdomain** — genuinely blocked. Domain registered at GoDaddy but DNS is delegated to Route 53; need Alex or Kate's AWS access to add the CNAME + TXT records Railway generates (Beckett confirmed Railway now requires **both**, not just a CNAME — this was a recent change from what was originally documented). Michelle asked to check with Alex/Kate, no confirmed answer. Beckett was given a full status-update email on this thread since it connects directly to his PWA install-experience work.
- **Deal Dive's original "hit enter, nothing happened" bug** — fixed (was the search/filter box, not the New Deal form), but **never confirmed which screen Michelle actually meant** — asked twice via email, no reply.

---

## 🟢 Confirmed by Michelle, Ready to Build (not yet started)

### Cash-out refinance ("Variant B") for Underwriting + Investor Report
**Full build prompt is written with all terms confirmed — just needs to be sent.** This is a coordinated two-tool change (Underwriting's cash-flow vector + Investor Report's invariant 10), same discipline as the fee-placement work earlier this session.

Confirmed terms:
- Real feature: excess refi proceeds ARE distributed to investors ("pay a % of the original investment back")
- 1% capital transaction fee to GP on the refi (standard practice)
- Payout order at the refi event: **loan balance repayment → fees → return of capital.** No pref paid at the refi event itself — pref just keeps accruing normally afterwards on the smaller unreturned-capital base.
- One flagged-but-unresolved detail in the prompt itself: exactly which base the 1% fee applies to (gross new loan amount vs. excess-proceeds-after-payoff) — the prompt explicitly asks Codex to propose the more coherent reading and flag it for confirmation rather than silently deciding.

### Word export for Investor Report's notetaker feature
**Design confirmed: fully togglable sections**, not a fixed list — Michelle's own real examples used different section sets each time (Market/CapEx/Legal/Financial/Next Steps in her real Jackson updates; a different five in her feedback text), so rather than guess a fourth time, she confirmed she wants to pick sections per-update from a superset: Property Update, Financial Update, Market Update, CapEx Update, Legal Update, Community Events, Next Steps.
**Build status unclear — needs checking whether this was actually started/merged, separate from the design confirmation.**

### GSR (Gross Scheduled Rent) handling check in Underwriting
Michelle confirmed gain-to-lease is rare, not worth modeling — but flagged GSR as more important, since 12-month leases can diverge from current market rent mid-lease. An investigation was queued asking whether Underwriting's income build-up already correctly uses each unit's actual in-place/contracted rent (effectively GSR) rather than assuming everyone pays current market. **Status of completion unclear — needs checking.**

### Site DD Lite toggle
Michelle resolved the design question herself months ago ("the normal tool should be fine if we make it toggleable enough" — vacant units + common areas only). **Whether this was actually implemented during the Site DD rebuild, or only designed, was never definitively confirmed. Needs checking.**

---

## ✅ Fully Shipped and Verified This Session (extensive — grouped by area)

### Underwriting / Investor Report / Waterfall engine (five-branch coordinated merge)
- **Multi-loan support**: per-loan amount/rate/amortization, combined + per-loan DSCR, LTV becomes computed output in multi-loan mode
- **Fees**: management fee + capital transaction fee, both deducted from cash flow before Investor Report ever sees it (property-level expenses, not GP distributions)
- **Per-year customizable assumptions**: vacancy/concessions/bad-debt/rent-growth per year up to 12 years, per-line expense growth schedules. Lived entirely in `underwriting_math.py` — `deal_analyzer_math.py` needed **zero** changes.
- **Multi-partner GP splitting**: `gp_partners` table, downstream-only allocation of the already-computed GP promote, new invariant 11. **70/30 GP/LP promote default** (was 80/20) per Michelle's real standard.
- **P&L export**, reusing the PdfPages/openpyxl pattern
- **Waterfall crash bug found and fixed**: any negative-year-1 operating cash flow crashed the whole waterfall with `WaterfallInvariantError` — a completely ordinary scenario for value-add deals. Fixed by separating "shortfall" from "undistributed" and strengthening (never weakening) the existing invariants.
- `deal_analyzer_math.py` byte-hash-verified untouched throughout every single one of these changes.

### Management fee basis — three attempts, now correct
Final, shipped, confirmed-correct basis: **% of Net Rental Income (NRI)** = Gross Potential Rent minus loss-to-lease/vacancy/concessions/bad-debt, **before** adding back other income. ("GI" = NRI. "GOI" = the separate Other Income line.) Verified against real Eagle Rock data at every step of all three attempts.

### Turnover/capex reclassification
Michelle confirmed turnover items (flooring, appliances, countertop/tub resurfacing) should be capex, not operating expenses. Fixed scoped **only** to Underwriting's T12 import (deliberately did not touch the shared classifier Scorecard Pro/Quick Analyzer also use). Eagle Rock's expense ratio: 68.58% → 60.60% (file's own figure: 59.79%). The $97,665.38 was then also manually entered on Eagle Rock's real Capex tab.

**Eagle Rock's current, final, accurate numbers**: NOI $482,120.76, equity $2,688,848.65, levered IRR 19.11%, DSCR 1.399, equity multiple 2.2645x. (Both the 8.11% morning figure and the later 20.12% figure are superseded and wrong for different reasons — Michelle was texted the full explanation.)

### Interest-only (IO) period support for Underwriting Loans
Per-loan `io_years`, keyword-only params, Deal Analyzer completely unaffected. Amortization after IO ends re-amortizes over the **remaining** term (keeps original maturity — real CRE convention, confirmed). DSCR **never shows a single misleading headline number** when IO exists — shows both the IO-period figure and post-IO figure separately, uses the worst-case (`dscr_min`) for any grading.

### Quick Deal Analyzer — full pivot + real regression found/fixed
Renamed from "Deal Analyzer," purpose reversed (NOI+cap rate → implied price, not price-in/IRR-out). Old leveraged model's UI removed but `deal_analyzer_math.py` kept 100% intact (still Underwriting's shared engine and its own cross-check target). Three NOI provenance paths with a falsification-proof label. Real T12 vacancy-loss bug found and fixed ($112,546 error) with a `reconcile()` gate that raises rather than silently returning wrong totals.

**Real regression found and fixed**: a later commit accidentally nested the grading-thresholds block inside `<select name="expenses_mode">`, which (per real HTML5 parsing behavior) caused THREE live bugs at once: dollar-mode expenses became unreachable, the grading Save button submitted a valuation instead of saving, and a Jinja `.values` collision left the threshold-editing screen permanently blank. All three found, fixed, verified. A standing structural test (`test_template_structure.py`) now checks all templates for illegal select-nesting via a real HTML5 parser's error stream — the naive "check the parsed tree" approach was proven to silently pass on broken markup, since browsers auto-repair the nesting before you can inspect it.

Grading thresholds are now fully **user-configurable** (not fixed), stored in a new namespaced `app_settings` table, red band deliberately not configurable (open-ended remainder by design).

### Underwriting overhaul (6 items, all shipped)
Property info card (unit count/occupancy overrides with visible-not-silent disagreement notes, parking, city/state) · Loan/debt-service promoted to headline stats · Rent-roll cross-check (4 comparisons, found a real 18.5%/$190,757 EGI gap on Eagle Rock, flagged to Michelle) · Capex budget with 5% contingency default · Market Context card pulling from FIRE Metrics via a proper alias-table join (not naive city matching, which was proven to silently miss San Francisco itself) · Scenario export.

### Site DD — complete rebuild from scratch (the largest body of work this session)
Three scopes (property/common-area, unit, room). 5-state condition scale (Excellent/Good/Satisfactory/Repair/Replace), deliberately never averaged into a single score. Repeatable items (multiple instances per item, e.g. 2 smoke detectors). Item bank (20 curated + freeform). Cost provenance (reference/manual/none, reference costs shown-not-prefilled to prevent silently converting "unpriced" into "priced at the average"). Real researched repair-cost table (36 items priced from averaged real sources, 46 honestly left unpriced — **scraping explicitly rejected** per Michelle's instruction and confirmed ToS/legal concerns). Mobile-first, real iOS/Android camera handling, video capped at 30s/720p/one-per-finding for storage reasons.

**Real bugs found and fixed**: a live NULL-identity duplication bug that had already corrupted one real assessment (fully recovered byte-for-byte before it could compound further) · a nested-form bug that would have silently misrouted saves · a freeform-item-name-erasure bug · capex-mapping gaps · the correct quantity-multiplication logic existed but was never wired to the live export path (found and fixed) · `category_key` conflation cleanup across all 34 checklist items.

**Portfolio onboarding**: all of Michelle's confirmed real properties now exist as records with correct aliases — Eagle Rock, Jackson, Oxford Pointe (OXPT/Oxford), The Canyon Apartments (Canyon), Maple Valley Apartments, Waterways (KYTX), The View (bare "View" alias removed after causing false-positive matches on ordinary conversation), River Oaks (ROMs), Cannongate, Papania (Mark 7). 11 properties, 9 aliases, all self-match-swept clean.

### Rent Comps
Split confirm() (dropped for first pull, kept for Force Refresh's real re-spend risk) · clearer status wording · bedroom filter (the actual fix for "DATA IS BAD," which was unfiltered mixed-bedroom data, not bad data) · recency filter · CSV export · a real bug where filters were silently hiding matching comps beyond the preview cutoff, found and fixed. **Rentometer explicitly rejected** — Michelle tried it, found it worse.

### Deal Dive
Fixed the "hit enter, nothing happens" bug (was the landing-page search/filter box — no Enter handler, silent empty state on zero matches). Zero-matches row, clearer labeling, sensible Enter behavior for 1-match/0-match/multi-match cases.

### Weekly Property Summary
SaaS-polish pass: section titles, feedback card, a real pre-existing gauge bug fixed (was rendering as an ellipse, not a circle).

### Scorecard Pro
Parsing notes moved to bottom, reworded (found "estimated" was factually wrong for an exact sum). Two items never live-browser-tested (Chrome extension never connected): the `<details>` toggle, the account-matching note.

### Investor Report Notetaker feature
**Upload-based, not live API integration** (Michelle confirmed this is simpler and sufficient — she exports from Fathom/Otter herself and uploads the file). Alias-based property matching, cheap substring scoring, ambiguous/no-match asks rather than guesses. Review-before-spend gate. Shared OpenAI usage counter built as prerequisite infrastructure (with a real self-caught near-miss: a test file was writing phantom calls to the live production counter under certain run conditions — found and fixed with a proper guard).

**Real navigation bug found and fixed**: the notetaker was **completely unreachable from anywhere in the UI** — zero links pointed to it, despite sharing a URL prefix with the waterfall tool. This was found via Michelle's own real feedback (she asked for two features that already existed, because she genuinely could not find them). Fixed with a nav entry + cross-link. **Important lesson now baked into practice**: a feature can be fully correct and fully verified and still not exist from a real user's perspective if verification only ever drove it by direct URL — reachability is a distinct check from correctness.

### Feedback system
**Critical finding**: `feedback_db.list_feedback()` existed but nothing ever called it — feedback was write-only and invisible since the feature was built. Built `/admin/feedback` (read-only by design, cards not tables to preserve multi-line formatting, a control test asserting something calls the reader so this can't silently regress). Found 3 real entries, acted on all actionable items.

---

## Standing Rules — Carry These Forward, Do Not Relitigate

1. **Every persistent DB path**: env-var-with-fallback, verified via live in-process code, never trust the Railway dashboard. Any new `*_DB_PATH` must demonstrate **both** failure states (unset → visible red banner naming the var) and success, not just the good one.
2. **Full-collection-rewrite routes are dangerous.** Several routes this session (`save_area`, `save_expenses`, `save_capex`, `replace_expense_lines`) silently blank anything not included in a POST. Always post complete forms. Always snapshot before any real production write. Multiple real incidents happened and were recovered this session because of this pattern — assume it applies to any route not yet audited.
3. **Merge discipline, no exceptions**: fetch → confirm master hasn't moved (rebase + byte-hash-verify if it has) → merge → push → confirm deploy live via container code check → full suite pass → **report before merging** → never chain merges without a checkpoint.
4. **`deal_analyzer_math.py` is sacred.** Byte-hash-verify it untouched after every single Underwriting-adjacent change.
5. **No fabricated authority.** Any number/threshold not confirmed by Michelle or a real cited source ships with an explicit, test-enforced "not confirmed" disclaimer (established pattern: `deal_readiness_defaults.py`, reused in Quick Deal Analyzer's grading and Site DD's cost table).
6. **No scraping, ever.** Investigated and explicitly rejected for Home Depot/Lowe's/city-data.com — no public APIs exist, both are ToS-prohibited and actively block bots. Always look for a legitimate licensed source first (RSMeans flagged as the real paid alternative if repair-cost accuracy ever needs to go further).
7. **OpenAI spend discipline**: shared $60/month account cap exists; the in-app `openai_usage.py` counter tracks per-feature and must be used by any new AI feature, tagged correctly, with a real confirm-before-spend gate and caching.
8. **One prompt at a time, easiest to hardest, report before merging each part separately** — Jasper's explicit standing instruction. Never combine build-and-merge into one silent action.
9. **When investigation reveals the literal instruction was wrong or stale, say so and propose the correct thing** rather than building exactly what was asked. This happened repeatedly and productively this session — it is the expected, correct behavior, not a deviation to avoid.
10. **Reachability ≠ correctness.** Check that new features are actually linked/navigable by a real user, not just that they work when hit directly by URL.
11. **Census and BLS have no paid tiers at all** — free registration is the ceiling for both, not a starting point for an upgrade conversation.

---

## Reference: other artifacts from this session

An earlier, now partially-stale backlog document (`meeting-notes-backlog.md`) exists from earlier in the session, organizing Michelle's original meeting-notes feedback. Most of what it tracked has since been resolved or superseded by the real, ongoing feedback loop (the `/admin/feedback` page + direct email/text exchanges) documented above — treat *this* handoff as the current source of truth, and the backlog doc as historical context only if needed.

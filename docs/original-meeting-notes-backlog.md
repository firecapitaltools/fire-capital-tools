# Post-meeting backlog — HISTORICAL, SUPERSEDED

> **`HANDOFF.md` is the current source of truth. This is not.**
>
> Preserved verbatim below the line, under the Part 47 rule that a
> predecessor must be **committed, not quoted**: a document that lives
> only in a chat window is invisible to every instrument this project
> has, and four standing rules were lost that way.
>
> **Do not act on anything in it.** It records what was wanted at one
> moment, and it has largely been overtaken by the feedback loop with
> Michelle — several items were built differently, several were answered
> by her directly, and at least three are now known to be wrong.
>
> **Known contradictions with current behaviour**, listed rather than
> resolved:
>
> * *"Scrape for repair costs from home-improvement retailers"* — ruled
>   out. Michelle asked for no scraping; the 36 reference costs are a
>   one-time manual research pass and `site_dd_reference_costs.py` is
>   built to make scraping structurally impossible.
> * *"Look at citydata.com's API for market context"* — city-data.com
>   publishes **no developer API**, and its terms exclude data mining and
>   robots for commercial use. FIRE Metrics covers the same ground from
>   government sources.
> * *"Rent Comps: auto-search, no confirmation popup"* — the confirmation
>   was **kept** for Force Refresh and a second one was **added** for the
>   size override. The document flags the tradeoff itself; the tradeoff
>   was resolved the other way.
> * *"Deal Analyzer is a different tool wearing the same name"* — acted
>   on. Quick Deal Analyzer exists and is a separate module.
> * *"Deal Dive: hit enter, nothing happened"* — fixed in `ae19794` and
>   closed **unconfirmed**; nobody matched the fix to the original report.
> * *"Site DD Lite"* — still unbuilt. `status` exists and is displayed;
>   nothing consumes it as a filter.
> * *"Data should be per-account"* — still unbuilt, still un-scoped, and
>   still the largest single item here.
>
> Nothing below has been edited, reconciled or merged into `HANDOFF.md`.

---

# Fire Capital Tools — Post-Meeting Backlog
*Source: Michelle's meeting notes, [date]. Organized by what's safe to start now vs. what's blocked.*

---

## STOP — Confirm before touching anything else

Two things from tonight need to be nailed down before new work starts, because
building on top of an unconfirmed assumption is exactly how rework happens.

1. **OpenAI key status.** Notes say "now we have an OpenAI key for anything
   absolutely necessary" — confirm `OPENAI_API_KEY` is actually set in
   production, and that a spend cap was set in OpenAI's own dashboard
   *before* it went in. `FIRE_METRICS_AI_SUMMARIES_ENABLED` defaults to
   `true` with zero cost tracking in code — if the key is live, money is
   already being spent with no ceiling.
2. **Management fee basis: GI or GOI?** Phase 4 (merged tonight) implemented
   this against EGI based on her verbal "percentage of gross income" answer.
   Tonight's written notes say "x% of GI not GOI." Need her precise
   definition of GI here — this already shipped and is affecting real IRR
   numbers, so a second wrong guess compounds instead of just delaying.

---

## Send to Michelle — need her answer, not a build decision

- [ ] GI vs. GOI, exact definition (see above)
- [ ] Rentometer: her note says "data should be combined in one list" — this
      reads as answering the earlier open question (merged, not side-by-side).
      Worth a one-line confirm before building, since it's a real design commitment.
- [ ] Rent Comps: removing the Force-Refresh confirmation popup removes a
      safety feature built specifically to prevent accidental API quota
      burn. Confirm she's accepting that tradeoff, not just wanting less
      friction without knowing what it costs.
- [ ] Investor Report AI notetaker: which service — Otter, Fireflies,
      Fathom, manual transcript paste? Cannot design ingestion without this.
- [ ] Multi-account/sharing (see architecture section below) — this needs
      a real conversation about who "accounts" are, not a feature request
      answered in a UI wishlist.

---

## ⚠️ Direct contradiction with what's live right now

**Deal Analyzer isn't a tweak — it's a different tool wearing the same name.**
What's built: purchase price in → IRR/CoC/DSCR out. What she's describing
(and the "2-Minute Analysis" screenshot): NOI + target cap rate → purchase
price out, with a ±5/10/20% toggle range. The existing IRR engine doesn't
need to be thrown away, but the primary UI and purpose need to flip.
Also: rename to "Quick Deal Analyzer."

---

## 🏗️ Architecture decision — needs its own scoping conversation, not a Phase 1

**"Data should be per-account, not site-wide, with a way to link accounts
and share specific deals."**

This is bigger than any single tool. Right now there's basic login but zero
data partitioning — every logged-in user sees everything. Building real
multi-tenancy means:
- Every table in every tool needs an owner/account column
- Every route needs a permission check
- A new invite/link/sharing mechanism, with per-deal granularity
- Careful migration of all existing data to *someone's* account

This should not be scoped via a bullet point. Recommend a dedicated
conversation with Michelle: who are "accounts" — other people at her
company, outside partners, both? Does sharing mean full deal access or
read-only? Before any Phase 1 investigation starts, since Phase 1 needs
to know the actual model to investigate against.

---

## 🐛 Urgent — usability bug, not a feature request

**Deal Dive**: "she put her address, hit enter, nothing happened — even I
don't understand exactly what to do." This is blocking basic use of the
flagship tool, not a wishlist item. Investigate before most feature work
below — a tool nobody can operate is worse than one missing nice-to-haves.

Also in Deal Dive: "does the supporting document do anything — if stored,
does it auto-fill other tools?" — a real, answerable question about
current behavior, worth checking before deciding whether to build that
auto-fill or just document that it doesn't exist yet.

---

## Connected items — build once, not twice

These appear in multiple sections as separate asks but are the same feature:

- **Site DD's "scrape for repair costs → construction budget"** +
  **Underwriting's "capex budget, exterior + interior, total + per-unit +
  5% contingency"** → one pipeline: Site DD produces the itemized repair
  list, Underwriting's capex section consumes it.
- **Site-wide "contingency/WTF fund"** = the same 5% contingency pattern
  from Underwriting's capex ask — build the pattern once, reuse everywhere
  it's requested.
- **Site DD Lite** — her own note resolves this: "the normal tool should
  be fine if we make it toggleable enough." Don't build a second tool;
  build the Site DD rebuild with a lite mode (vacant units + common areas
  only, lighter output).

---

## Per-tool backlog (raw notes retained, my read added)

### Weekly Property Summary
- More SaaS-looking, cleaner/polished visual pass. *Small, visual only, no logic risk.*

### Scorecard Pro
- Parsing notes need to be clearer and moved to the bottom of the page.
  *Small, contained.*

### Deal Analyzer → "Quick Deal Analyzer"
- See contradiction section above — this is a rebuild of purpose, not a tweak.
- Enter loan balance directly, add an IO (interest-only) period
- "NOI Growth per month" flagged by her as currently wrong/confusing
- Upload a T12 directly (currently manual-entry only)
- Core output: purchase price from NOI/exit cap, ± toggle range (5/10/20%)
- Color grading (red/orange/yellow/green) on whether a deal looks good

### Underwriting
- Match Intellcre's presentation style as the reference example
- Property info: unit count, occupancy, parking
- Upload an OM (offering memorandum), auto-extract useful phrases/overview
- Look at citydata.com's API for market context
- Rent roll cross-check against uploaded data
- Loan amount + debt service shown clearly
- Capex budget: exterior + interior, itemized, total + per-unit, feeds
  "cash to close"
- Unit-level terms
- Management fee: **GI, not GOI** — see confirm-first section above
- Exportable in the Intellcre-style format

### Investor Report
- Ingest AI notetaker transcripts + uploaded reports → auto-draft on
  operations, capital improvements, financials, market update, community
  events — **blocked on which notetaker service, see above**
- Manually overridable template
- Photo upload
- Word doc export

### Deal Dive
- **Fix the broken hit-enter flow — urgent, see above**
- Needs headers/structure, more intuitive overall
- Supporting-document auto-fill question — investigate current behavior first
- Should assemble into a presentation-style output

### Rent Comps
- Address autocomplete/suggestions while typing
- Auto-search on hit search, no confirmation popup — **tradeoff flag above**
- "Active/Inactive" status labeling isn't intuitive — needs clearer wording
- Data quality complaint — she prefers Rentometer's info; **pair with the
  Rentometer merge work**, combined into one list per her note
- Add property type + distance-from-subject fields
- Filter for more current/recent listings
- "Why does it say saved if I can't access them" — **sounds like a real
  bug, verify before assuming it's a UX complaint**
- Flag outlier comps that look too cheap or too expensive

### Site DD — full rebuild, her explicit words: "wants to be created from scratch"
- Configurable room order (click which room is "first" so the flow matches
  the actual floor plan, starting at the front door)
- Photos + notes on everything broken, itemized
- End-of-inspection summary of all issues
- Pull repair costs from home-improvement retailers → total repair cost
  (may use AI) — **see the connected capex pipeline above; also revisit
  the scraper-fragility concern flagged earlier this session before
  committing to a specific data source**
- Condition dropdown: Excellent / Good / Satisfactory / Repair / Replace
- Example granularity: flooring type per room (vinyl/carpet/hardwood),
  GFCI outlets, etc. — essentially every physical system, itemized
- Output feeds one consolidated property spreadsheet for analysis
- Lite mode via toggle, not a separate tool (see above)

### Site-wide
- Contingency/buffer pattern, reusable across relevant sections (tie to
  Underwriting's 5% capex contingency)
- Data should be per-account with deal-level sharing — **architecture
  decision, see above, do not build ad hoc**
- General intuitiveness pass across all tools
- FIRE branding consistency pass across UI

---

## Suggested sequencing

Given tonight already shipped five real branches of financial-engine
changes, I would NOT start fresh feature work immediately after this —
let what's live settle, and let real usage (scenario 5, deal 2 already
appeared organically) continue before adding more surface area.

When work does resume, in this order:

1. Confirm the two STOP items (OpenAI cap, GI/GOI)
2. Send the clarifying questions to Michelle, get answers before building
   anything that depends on them
3. Investigate the Deal Dive "hit enter, nothing happens" bug — real,
   blocking, and cheap to diagnose
4. Deal Analyzer's reversal — contained, high-clarity spec, good next
   build once the bug is fixed
5. Rent Comps fixes + Rentometer merge together, since they're related
6. Scorecard Pro parsing-notes cleanup + Weekly Property Summary visual
   pass — both small, can slot in anywhere
7. The Site DD rebuild + Underwriting capex pipeline — large, connected,
   deserves real Phase 1 investigation time
8. Investor Report AI notetaker — blocked on her service choice
9. Multi-account architecture — its own dedicated planning conversation
   before any code, likely the largest single piece of work in this
   entire document

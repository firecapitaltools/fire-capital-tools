# Friday call — Michelle, after 2pm

**For Jasper to read live. Written 2026-08-29 against master `7ddbe6b`.
Every number is from production, read-only, on the day.**

Michelle: *"Let's chat regarding your account data questions… I'm honestly
a bit fuzzy since I can't remember what I was referring to."*

She will not reconstruct a months-old note cold. **Don't ask her what she
meant — show her three things and let her point.** §2 is the call.

| | minutes |
|---|---|
| §1 Where things stand — read the four bold lines aloud | 2 |
| **§2 The three sketches — the actual decision** | **10** |
| §3 Properties, if there is room | 2 |
| §4 One-liners, only if she has time | 1 |

---

## §1 Where things stand — four sentences

**Two people can log in. They see identical screens.** Michelle's own
admin login, and one account created through the signup form on **27
August by Beckett** (`beckettfredericks@gmail.com`). There is no third
kind of user and no "my stuff" anywhere.

**Everything is one shared workspace.** If Kaia signed up tomorrow, she
would immediately see: both deals, all ten underwriting scenarios, all
four site inspections including the Nabob Hill walk, all 51 uploaded
files, every rent comp search, and the whole notetaker property list. Not
because anyone granted it — because there is nothing to grant. She would
also be able to edit or delete any of it.

**Nothing anywhere records who anything belongs to.** Twelve separate
databases were checked column by column: **no owner, no account, no
created-by, on any table.** This is not a setting that is switched off.
The information was never captured, so "show me only mine" cannot be
answered for a single existing row.

**There is less data than it sounds.** About **400 rows** of real work —
the rest is the reference table of 343 US cities behind FIRE Metrics.
Whatever gets decided, there is not much to migrate.

<details><summary>The full picture, if she asks for specifics</summary>

| | |
|---|---|
| Deals (Deal Dive) | 2 — 19 Bay Vista Drive, 1120 Jackson Street |
| Underwriting scenarios | 10, of which **8 are empty placeholders** — only the two Eagle Rock ones have numbers, and those two are duplicates of each other |
| Site inspections | 4 — two at 19 Bay Vista, two at Nabob Hill |
| Uploaded files | 51 (1.9 MB) |
| Rent comp searches | 3 |
| Scorecard history | 36 monthly rows |
| Investors | 1 |
| Properties in the notetaker list | 12 shown, **11 actual** — see §3 |
| RentCast lookups used | 19 of 50 *(re-read 2026-08-31; resets 09-01)* |

</details>

---

## §2 THE DECISION — three readings of what she asked for

Her note was: *per-account, not site-wide, with a way to link accounts and
share specific deals.*

**Say this first:** *"I can't tell which of these you meant, and all three
are reasonable. Which one sounds like the problem you were having?"*

Then read the three. **Do not recommend one.** The "you might not expect"
line under each is the part that usually decides it — read those.

---

### Sketch 1 — Mark individual things private

Nothing changes by default. Every deal, scenario and inspection gets a
switch: *visible to everyone* (the default, as today) or *just me*. A
private item disappears from everyone else's lists.

**What she could do that she can't today:** work up a deal nobody else
sees until she is ready to show it.

**Rough cost:** the smallest of the three. Roughly one working session.

> **What she might not expect:** *just me* means **just her**. Jasper
> could not see it either, so "can you look at what I've done on this
> one?" stops working until she un-hides it. Every support question about
> a private deal becomes "share it with me first".

---

### Sketch 2 — Each person's work is their own, and can be shared

Everything created from now on belongs to whoever created it. Your home
screen shows your deals. Sharing is per item and deliberate: *share this
deal with Jasper.* Shared means both can see and edit.

**What she could do that she can't today:** have her own workspace that
does not fill up with other people's placeholder scenarios, and hand over
one specific deal without handing over everything.

**Rough cost:** the middle. Several sessions — every screen that lists
anything has to learn to filter, and every tool has a list screen.

> **What she might not expect:** **the 400 rows that already exist have no
> owner**, and somebody has to decide, once, who gets them. If the answer
> is "the admin account", then Michelle owns Beckett's site inspections
> and every placeholder scenario. If the answer is "everyone keeps seeing
> the old stuff", then there are two rules running at once — old data
> shared, new data private — and that is the version people find
> confusing six months later.

---

### Sketch 3 — Real accounts, roles and permissions

Named accounts, invitations, and a difference between *can look* and *can
change*. Someone can be given read-only access to one deal. There is an
admin view of who has access to what, and access can be withdrawn.

**What she could do that she can't today:** give a lender, an investor or
a junior analyst access to exactly one property, read-only, and take it
away afterwards without changing anyone else's access.

**Rough cost:** the largest by a wide margin — closer to a project than a
change. It touches every tool, and it is the only one of the three that
needs its own screens for managing people.

> **What she might not expect, and this one costs money:** RentCast
> lookups are **paid, capped at 50 a month, and 18 are used.** Today they
> are cached once and reused by everyone. Once data is per-account, there
> is a real question nobody would think to ask up front: if two people
> look up the same address, does the second one re-buy the lookup, or read
> the first person's cached copy — which means seeing something from
> someone else's deal? **Either answer is defensible and they cannot both
> be true.** The same question applies to the shared property list and the
> market data cache.

---

### One consequence has already happened, whatever she decides

**Not a question for her — an us item, noted so it is not presented as
conditional.** Three screens (the loan list, the capex list and the GP
split) were left with a known weakness on a written condition: fix it the
moment *either* per-account data ships *or* a second person can log in.

**The second one happened on 27 August**, when the signup account was
created. **That work is now done** — those three lists refuse a save from
a page that was showing an older version, rather than silently deleting
the row somebody else added. It did not depend on Friday and did not wait
for it.

> **Worth saying out loud, and it is the point rather than a complaint:**
> Beckett created that account **himself**. Nobody decided he should have
> one, because **there is no step at which anyone decides.** The signup
> form is open, and an account created through it sees every deal, every
> scenario, every inspection and every uploaded file. That is not a story
> about Beckett — it is what "site-wide" means, demonstrated. It also
> means the question in §2 is a live one about who can see her data
> today, not an architectural preference about how the tool should be
> built.

### If she has no view at all

**That is a usable answer.** Nothing is currently broken by the absence,
and the honest recording is "considered, not wanted yet" rather than
leaving it on a blocked list for another three months. **Sketch 1 is also
a legitimate "not now, but a bit"** — it is small, it changes nothing by
default, and it does not commit to anything larger.

---

## §3 Properties — one answer would unblock two things

Only if there is time. **It is a smaller question than §2 and it is
blocking more.**

**There is no list of properties anywhere.** The 12 in the notetaker are
worked out fresh on every page load by scraping names out of the other
tools. Nothing stores that a property exists.

**What that costs today, in her own data:**

- **The same building is on the list twice, and we can prove why.** Her
  Nabob Hill inspection on **16 August** was linked to the 1120 Jackson
  Street deal. The **next one, on 18 August**, was not linked to anything.
  So the tool now shows *1120 Jackson Street* and *Nabob Hill* as two
  separate properties — one building, two entries, two days apart, because
  one screen asked for the link and the other did not.
- Names drift by tool: `19 Bay Vista Drive` in one place, `19 bay vista
  drive` in another.
- Anything true about a building — year built, unit count, address — has
  to be retyped on every inspection, and two inspections of the same
  property can quietly disagree about the year it was built.

**And it now blocks her own request.** She asked for the tool to know
whether a property is leased **by unit or by bed** — *"in student housing,
we need per bed occupancy."* That is a fact about a **property**: it does
not change between inspections. There is nowhere to put it. **Her per-bed
answer did not unblock that work; it moved it behind this question.**

> **Worth putting to her as one question, not two:** properties and
> per-account data are the same shape of question — *what does a record
> belong to, and who may see it.* Deciding properties first and accounts
> later risks designing the property record twice.

---

## §4 One-liners — only if she is still on the call

- **Can one bedroom be let to two people** at any by-the-bed property she
  owns? One word, and it decides the entire shape of the per-bed work.
- **A rent roll from The View** (or any by-the-bed property she owns) —
  one file answers four open questions at once.
- **Does she own a by-the-bed property at all?** Never actually confirmed;
  the evidence so far is Paresh's file for somebody else's building.
- **Do inspectors measure anything on the walk** — tape measure, or just
  eyes? The most expensive items in a repair budget cannot be priced
  without it.
- **A 2-bedroom rent roll**, from anywhere. Every file we have is 1-bed
  units, so the bedroom feature has never been tested on real data.
- **Rent roll upload**: her document says *"upload rent roll to know
  number of units"*; her in-app note asked for bedroom derivation and
  occupancy mapping. Those are very different sizes of job — which did she
  mean?
- **Notetaker headings** — renaming Operations and Capital Improvements,
  adding Legal Update and Next Steps. Costs a little OpenAI spend against
  the $60/month budget, so worth one sentence of confirmation.
- `/fire-metrics/` — Beckett added a second, chrome-less FIRE Metrics page
  that nothing links to. His call, but she may have a view on whether it
  should be reachable.

---

## Afterwards

Whatever she says, write it down verbatim in HANDOFF the same day —
including *"I don't know"*, which is a real answer and stops the question
being re-asked in November.

<details><summary>One thing that quietly resolved itself, if it comes up</summary>

Accounts created through the signup form were flagged as untested — nobody
had confirmed one survives a deploy. **Beckett's account has now survived
16 deployments since 27 August.** That question is settled by ordinary
use, and needs nothing from her.

</details>

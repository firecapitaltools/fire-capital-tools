# Known issues

Things that are believed to be true but have not been demonstrated, and
things that are wrong but are not being fixed yet. One entry per issue.

This file exists because "nobody has checked" and "checked and fine" look
identical six months later, and this project has been wrong about which
was which more than once. An entry here is not a bug report — it is a
claim with a stated confidence and a written-down way to settle it.

## The format

Every entry carries all six headings. An entry without **How to close it**
is a worry, not an issue, and does not belong here.

```
## <short title>

**Opened** YYYY-MM-DD · **Severity** low | medium | high · **Status** open | closed YYYY-MM-DD

**What is believed.**   The claim, stated so it could be falsified.
**What is actually known.**  The evidence, and its kind — direct, indirect, or none.
**Why it is not settled.**   What the evidence does not cover.
**Cost if wrong.**      What breaks, and who notices.
**How to close it.**    Numbered steps. Someone with no context runs them.
```

Closing an entry means editing it in place — set **Status** to `closed`
with the date, and add a line saying what was run and what it showed.
Entries are not deleted. A closed entry is the record that the check
happened, which is the whole point.

---

## 1. Volume persistence for the user store is unverified

**Opened** 2026-08-25 · **Severity** medium · **Status** open

**What is believed.** `USER_STORE_PATH=/data/users.json` puts signup
accounts on the Railway volume, where they survive a redeploy. This is
the property the Part 51 change exists for.

**What is actually known.** All of this is confirmed on the deployed
container as of 2026-08-25:

* `USER_STORE_PATH` is set in the environment and reads `/data/users.json`.
* `User.user_store_is_configured()` returns `True` and
  `user_store_warning()` returns `None`, so signup no longer refuses.
* `/data` is a **real filesystem mount**, not a directory on the container
  image: `/proc/mounts` carries
  `/dev/zd3360 /data ext4 rw,relatime,discard,stripe=8192`, and `/data`
  contains a `lost+found`, which only a genuine ext4 filesystem root has.
* Twelve `*_DB_PATH` variables point into `/data` and their data has
  survived many deploys — `site_dd.db` still holds assessment 11.

**Why it is not settled.** Every item above is **indirect**. Together they
make it very likely, and the `/proc/mounts` line is much better evidence
than "the path was accepted" — but none of it is the thing itself. Setting
a path proves the code accepts it. A mounted device proves `/data` is not
the image. Neither proves that *an account written through the signup form
is still there after the next deploy*, which is the only claim that
matters.

Two specifics the indirect evidence does not reach:

* ~~**The signup write path has never run in production.**~~
  **Settled 2026-08-25, by accident.** A verification script for the login
  guard posted the signup form while the store was configured, which is
  not a probe but a real account creation. It worked: `zz-signup-probe`
  was written to `/data/users.json` and the file appeared where the
  variable points. The account was removed immediately, confirmed unable
  to log in, and the file — left empty — was deleted, returning production
  to its previous state. So the write path is now known to work and to
  write to the right place. **The redeploy half is still untested**, which
  is the part that matters and the reason this entry stays open.
* Volume identity across deploys is a Railway service property, not
  something the container can observe about its own future.

**Cost if wrong.** A client creates an account, uses it, and it vanishes at
the next push — surfacing days later as *"my password stopped working"*,
with nothing in the logs connecting it to a deploy. That is the exact
failure mode Part 51 was written to prevent, and it would be discovered by
the client rather than by us.

**How to close it.**

1. On the deployed app, sign up a throwaway account through the real form
   (suggested: `zz-persistence-check`, with a password you record). This
   half is known to work — see above — so expect it to succeed.
2. Confirm it can log in, and confirm `/data/users.json` now exists on the
   container and contains that username.
3. Push any trivial commit — a comment, a line in this file.
4. Wait for the redeploy to go live. Confirm it is the new container, not
   a cached response.
5. Log in as the throwaway account again.
   * **Still works** → the volume persists. Close this entry.
   * **Fails, or the file is gone** → `/data` is not durable for this
     service. Reopen at high severity, and stop offering signup until it
     is.
6. Remove the throwaway account from `/data/users.json` and confirm it can
   no longer log in.

Step 6 is not optional. A live account with a known password left on a
production system is a worse problem than the one being investigated.

---

## 2. The deployed suite carries two failures that are not the code's fault

**Opened** 2026-08-25 · **Severity** low · **Status** open

**What is believed.** The two errors in the deployed test run are
environmental, not defects, so a run showing exactly two is a pass.

**What is actually known.** The deployed suite runs 1918 tests and errors
on exactly two, both in
`tests.test_fire_metrics_ai_summary.FireMetricsAISummaryTests`:
`test_frontend_cre_runtime_success_payload_and_stale_overlap_do_not_fallback_to_failure`
and `test_frontend_overview_and_cre_are_single_authority_runtime_matrix`.
Both exercise frontend runtime behaviour and need `node`, which is not
installed in the production image. The count has been stable across
Parts 55 and 57.

**Why it is not settled.** "Needs node" is the standing explanation and
it fits, but the assertion has been taken on trust rather than
demonstrated — nobody has installed `node` and watched them pass.

**Cost if wrong.** Low, but corrosive: two permanently red tests train
everyone to read `FAILED (errors=2)` as success, and a third genuine
failure would arrive inside a number nobody reads closely any more.

**How to close it.**

1. Run those two tests in an environment where `node` is on the PATH.
2. **They pass** → the explanation is confirmed. Make them skip rather
   than error when `node` is absent, so the deployed suite reads green and
   a third failure is visible the moment it appears. Close this entry.
3. **They fail** → they are real defects wearing an environmental
   excuse. Open an entry per defect and fix them.
4. Either way, record here what was run and what it showed.

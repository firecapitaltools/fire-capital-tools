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

**Opened** 2026-08-25 · **Severity** medium · **Status** closed 2026-08-29

> **CLOSED BY ORDINARY USE, not by running the procedure below.**
>
> Beckett created an account through the real signup form on
> **2026-08-27**. It is in `/data/users.json`, and **16 merges have
> been deployed since**. The account is still there and still logs
> in.
>
> That is the claim this entry was about — an account written by a
> person through the form, surviving redeploys — and it is now
> evidenced by a real account rather than a throwaway one. The
> six-step check below was never run and does not need to be; it is
> kept because a closed entry is the record that the question was
> settled, and because the procedure is still the right one if
> persistence is ever doubted again.
>
> Note what settled it: **nobody tested this.** Somebody used it.
> Worth remembering when the next entry here looks like it needs a
> deliberate experiment.

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

**What is actually known.** The deployed suite errors on **exactly two**
tests, both in
`tests.test_fire_metrics_ai_summary.FireMetricsAISummaryTests`:
`test_frontend_cre_runtime_success_payload_and_stale_overlap_do_not_fallback_to_failure`
and `test_frontend_overview_and_cre_are_single_authority_runtime_matrix`.
Both exercise frontend runtime behaviour and need `node`, which is not
installed in the production image. **The two have been stable from Part
55 to Part 84**; the suite TOTAL is not, and is not recorded here on
purpose — it was "1918" in this entry while the real figure passed 2,400,
and the total is bookkeeping where the two is the invariant. Run
`railway ssh "python -m unittest discover -s tests -t ."` and read the
error count, not the total.

**Why it is not settled.** ~~"Needs node" is the standing explanation and
it fits, but the assertion has been taken on trust rather than
demonstrated — nobody has installed `node` and watched them pass.~~

> **THIS ENTRY IS NOW A TASK, NOT A CLAIM, AND THAT IS WORTH SAYING OUT
> LOUD.** The uncertainty is gone; what is left is one line in Beckett's
> tests. **It closes when he answers, whichever way he answers** — the
> three cases and what to do in each are decided in advance in HANDOFF,
> *A file of claims accumulates tasks*, so the decision does not have to
> be rediscovered on the day. He was asked directly in
> `docs/beckett-2026-08-31.md` §1.

> **DEMONSTRATED 2026-08-31. Step 1 of the procedure below was run and
> both tests PASS** on a machine with `node v24.13.1`, in 0.118s. So the
> explanation is confirmed: they are environmental, not defects.
>
> **What remains is step 2, and it is not ours to take.** Making them
> skip rather than error is one line in each test, in Beckett's module,
> and it is what turns the deployed suite green so a third failure is
> visible immediately. The alternative — adding node to the image — needs
> a `nixpacks.toml` this repo does not have, costs ~50–90 MB and slower
> builds forever, and buys running a JavaScript harness on a Python
> container. Both options and their costs are in HANDOFF, *The two node
> failures*.
>
> The entry stays **open** because the thing it asks for has not been
> done; what changed is that the uncertainty in it is gone.

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

---

## 3. Volume backups: available since the Pro upgrade, restore not yet rehearsed

**Opened** 2026-08-30 · **Severity** high · **Status** open — *narrowed
2026-09-01*

> **STATUS CHANGED 2026-09-01: from "not possible" to "possible, running,
> and unproven where it matters."** Michelle upgraded the workspace from
> Hobby to Pro on 2026-08-31. Backups now work; they are taken on a
> schedule; **nothing has ever been restored from one.** That last clause
> is why this entry stays open, and it is the same standard that kept
> entry 1 open until a real account settled it.

**What is believed.** If production data were lost or corrupted, it could
be restored from a platform backup.

**What is actually known.** Established by exercise on 2026-09-01:

    project.subscriptionType                  pro          (was hobby)
    subscriptionPlanLimit.volumes:
        maxBackupsCount                       10           (was 0)
        maxBackupsUsagePercent                0.5          (was 0)
        maxSizeMB                             1000000      (was 5000)
        defaultSizeMB                         50000
        maxPerProject                         20

    volumeInstanceBackupCreate(/data)         ACCEPTED     (was Not Authorized)
      -> workflowId createVolumeInstanceBackup/5d1c9be7-...
      -> verified BY LISTING, not by the return value

    volumeInstanceBackupList(/data)           1 backup
        id              b8384e68-6ddf-46a8-af2c-cb86baf350d1
        name            first-pro-backup-2026-08-31
        createdAt       2026-09-01T05:05:03.550Z
        referencedMB    150
        expiresAt       null
        scheduleId      null      (manual, not from a schedule)

    volumeInstanceBackupScheduleList(/data)   2 schedules
        DAILY    cron "5 6 * * *"      retentionSeconds  518400  =  6 days
        MONTHLY  cron "48 20 1 * *"    retentionSeconds 7689600  = 89 days

**The entitlement was settled by exercise, not by reading a limit.** The
identical `volumeInstanceBackupCreate` call was refused on 2026-08-30 and
accepted after the upgrade. That ordering is the evidence; the limit
fields only agree with it. Reading `maxBackupsCount: 10` and stopping
there would have been the Part 74 error again — a capability read off a
catalogue.

**The retention numbers are the ones the platform actually set**, not the
round numbers they resemble: **6 days, not 7; 89 days, not 90.** Part 72
declined to guess this value because no schedule existed to read it from.
Anyone quoting "a week" or "three months" to Michelle would be rounding
in the direction that flatters us.

### The lock was accepted and CANNOT be confirmed by reading

`volumeInstanceBackupLock` on `b8384e68` returned `true`. **The listing is
unchanged by it**, and that is not a failure — `VolumeInstanceBackup`
exposes `createdAt, creatorId, expiresAt, externalId, id, name,
referencedMB, scheduleId, usedMB, volumeInstanceSizeMB` and **no lock
field at all**. There is no query anywhere in the schema that reports lock
state.

> **So the honest claim is "the lock mutation was accepted", not "the
> backup is locked".** The only test that would settle it is asking the
> API to delete or expire the backup and watching it refuse — which risks
> the one known-good copy this project has, to confirm a flag. **Not
> worth it.**
>
> **A mutation whose effect no query reports is not verifiable without
> destroying the thing it protects.** So this is recorded as
> accepted-not-verified **with a scheduled observation**, which costs
> nothing and runs itself:
>
> * **~2026-09-08**, when the first daily reaches its 6-day retention. If
>   dailies expire and `b8384e68` is still listed, retention is at least
>   not sweeping unscheduled backups. **Weak evidence** — one with no
>   expiry may never have been a candidate.
> * **When the set approaches `maxBackupsCount: 10`** and something must
>   be evicted. **That is the observation that tests the lock**, and it is
>   reachable within about a week of dailies.
>
> Read the answer off the listing on the day rather than reconstructing
> it. If `b8384e68` is gone when the cap binds, the lock did nothing.

**Capacity is not a concern.** Ten backups permitted; daily retention of 6
days plus monthly means the set stays well under that even with the
locked manual one held indefinitely. `referencedMB` is 150 against a
5,000 MB volume — Pro raises the size ceiling to 1 TB but resizes nothing,
and nothing here needs resizing.

### Two reading notes that have now cost time twice

1. **`workspace(workspaceId:)` denies for this account.** The project sits
   in *Michelle Jeong's Projects* and we are a project member, not a
   workspace member, so `me { workspaces }` does not list it and the
   workspace query returns `Not Authorized`. **Read limits through
   `project(id:) { subscriptionPlanLimit }`**, which works. The earlier
   `workspace.plan HOBBY` reading is not reproducible from this account
   and should not be retried that way.
2. **The CLI credential is `user.accessToken`.** `user.token` is `null` in
   `~/.railway/config.json`, and a request built from it sends
   `Bearer None`, which denies **identically to a stale token**. Check the
   input before believing the response.

**A third, from this run:** three separate `Not Authorized`-looking
failures were **GraphQL shape errors**, not authorization —
`subscriptionPlanLimit` is a scalar with no subfields,
`VolumeInstanceBackup` has no `status`, and `volumeInstanceBackupCreate`
returns `WorkflowId` whose only field is `workflowId`. Read the error
body rather than matching the shape of the failure to a remembered cause.

**Why it is not settled.** Nothing has ever been restored.

**Nothing has been restored, and the shape of a rehearsal changed on
2026-09-01 when the vendor's own description was finally read.**

* **A backup can only be restored into the same project AND environment.**
  So the second-environment rehearsal recorded here yesterday is not
  possible at any price — that question is closed, not deferred.
* **A restore is NOT in place.** It stages a change for review, creates a
  new volume from the backup at the same mount point, and leaves the
  original volume retained but unmounted. The old record here said "in
  place, no undo"; that was inferred from a mutation signature and was
  wrong in the direction of danger.
* It still redeploys the service, still destroys every backup newer than
  the one restored, and still has no single undo mutation.

See the HANDOFF entry for the correction and what it leaves us able to
claim.

**Cost if wrong.** The volume is lost or corrupted, somebody reaches for a
backup that exists, and the restore fails or restores something
unusable — at which point the fallback is whatever `snapshot_all` set was
taken by hand, and if none was taken recently the loss is Michelle's 31
findings, her grading bands, three rows of feedback typed once, and 14
paid RentCast lookups. **The backups make that scenario less likely and
do not make it impossible**, which is exactly the distinction this entry
now exists to hold open.

**How to close this entry.** A restore performed against a volume that is
not production, with the restored content compared against a known
fingerprint. Until then the claim is *"backups exist and are taken
automatically"*, which is true, and not *"we can recover"*, which is
untested.

**The `VACUUM INTO` snapshots stay regardless.** A platform restore prunes
the backup set, so the platform's copies cannot protect the moment before
a platform restore. `python -m tools.snapshot_all` is not superseded by
this and its runbook section stands.

**How to close it.**

1. ~~Decide whether to upgrade the workspace to `PRO`.~~ **DONE — Michelle
   upgraded on 2026-08-31 and did it herself.**
2. ~~Confirm the per-GB rate for `BACKUP_USAGE_GB`.~~ **DONE 2026-08-31:
   $0.15/GB-month on incremental size, under a cent a month for a 150 MB
   volume. The number that mattered was $15/month for the plan.**
3. ~~Enable a schedule, take one manual backup immediately, and lock it.~~
   **DONE 2026-09-01. DAILY + MONTHLY enabled; `first-pro-backup-2026-08-31`
   taken and lock-requested — with the caveat above that no API field
   reports lock state.**
4. **Rehearse a restore — onto a separate volume, never over production —
   and record who can perform one.** THE ONLY STEP LEFT, and it needs a
   second environment that does not exist. See the HANDOFF entry for what
   that costs and what we can claim until then.

**What does NOT depend on this.** The application-level rollback for the
seeding work — a `seed_batch` column and a pre-write `VACUUM INTO`
snapshot — is entirely within our control, costs nothing, and never
required the plan change. **Rehearsed 2026-08-30**, on a scratch database
and again on a copy of real production content, source opened `mode=ro`
and never written. The runbook is `docs/site-dd-restore-runbook.md`.

---

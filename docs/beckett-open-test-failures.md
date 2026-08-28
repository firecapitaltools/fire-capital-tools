# Three test failures from `72d6be1` and `2d537d5` — for Beckett

> ## ALL THREE ARE FIXED. Updated 2026-08-28, master `f7ee1e1`.
>
> **You do not need to do anything.** Master is green apart from the two
> known node-absent failures. **Your commits needed no changes** — one
> defect turned out to be ours, one was a missing entry in our own
> allowlist, and one was a test guard that ordinary local development
> could satisfy.
>
> | | what happened | commit |
> |---|---|---|
> | §1 reachability | allowlist entry added on your behalf — **object if the standalone view was meant to be linked** | `52df627` |
> | §2 login loader | **the bug was ours**, in `app.py`. Fixed. Your test passes as a consequence | `5d1f393` |
> | §3 self-poisoning guard | fixed in your test file — the guard, not the assertion | `f6b39d6` |
>
> The diagnosis below is kept in full, because the method is worth more
> than the outcome — including **two places where I asserted a mechanism
> instead of running one and had to correct myself.** Both are marked.
> The `343` question in §3 is still yours and is untouched.

**Originally written against master `d548c59`.** Everything below was
reproduced; every fix was run, not guessed.

Two failures came from **`72d6be1` "Add standalone FIRE Metrics view"**.
The third relates to **`2d537d5` "Fix FIRE Metrics city search coverage"**
and appeared only on a machine where the app had been opened locally —
see §3, which is the one most likely to waste your time.

---

## 1. `test_no_get_route_is_unreachable` — `/fire-metrics/` is linked from nothing

**Where:** `tests/test_route_reachability.EveryGetRouteIsLinkedTests`

**What it asserts.** Every GET route is reachable by clicking — it appears
in some template, either via `url_for('endpoint')` or as a literal path.
Anything that legitimately is not gets an `ALLOWLIST` entry **with a
written reason**. The test's own docstring says *"nobody has linked it yet
is not a reason; that is the bug."*

**Output:**

```
These GET routes are linked from no template, so a person can reach them
only by typing the URL:
  fire_metrics_standalone  (/fire-metrics/)
```

**Why your change trips it.** `app.py` gained:

```python
@app.route("/fire-metrics/", methods=["GET", "POST"])
@login_required
def fire_metrics_standalone():
    return fire_metrics_index.__wrapped__(standalone_mode=True)
```

and no template links to it. The test is doing exactly its job.

### DONE — entry added in `52df627`, and my first reason was wrong

I originally proposed the entry on the grounds that *"the iOS shell
addresses it directly by URL."* **Checked before writing it, and that is
not supported.** `capacitor.config.json` sets `server.url` to the site
**root**, and nothing in the repo — no template, no JS, no config — names
`/fire-metrics/` at all. I nearly wrote a justification I had just
disproved into the one file whose entire value is that its justifications
are true.

**The entry still belongs, for a reason that does hold**, and this is what
went in:

* `fire_metrics.index` **is** linked, from the sidebar at
  `/tools/fire-metrics/` (`templates/base.html:108`).
* `fire_metrics_standalone` calls the **same view** with
  `standalone_mode=True`, which `base.html` uses to suppress the sidebar,
  the mobile nav and the backdrop.
* So it is a chrome-less alternate rendering of an already-reachable page.
  **Linking a chrome-less page from the chrome is the one thing that must
  not happen** — it drops a person into a view with no navigation and no
  way back, which is worse than the bug this sweep catches.

**Two things for you.**

1. **Object if that is wrong.** If the standalone view is meant to be
   reachable from the web app, the allowlist entry is the wrong call and
   it should be linked instead. Say so and it comes out.
2. **`capacitor.config.json` may need a look.** Its `server.url` is the
   site root, so the shell currently loads the full app *with* the
   sidebar. If you intend it to open the chrome-less view, nothing points
   it there yet. That is your call and I have not touched it.

Positive control on the entry: with it in place, a newly added unlinked
route is still caught. An allowlist entry must silence one route, not
blunt the instrument.

<details><summary>The original reasoning, kept</summary>

**This looked like the allowlist case, not the link case.** The route
renders with `standalone_mode=True`, which `base.html` uses to suppress
the entire sidebar, and it landed alongside `capacitor.config.json` and
*"safe area handling for iOS native shell"*. A chrome-less view whose
consumer is a native shell is genuinely URL-only by design — that is a
legitimate entry, and the allowlist exists for precisely this. The
conclusion held; the stated reason did not survive being checked.

</details>

**Smallest fix — add to `ALLOWLIST` in `tests/test_route_reachability.py`.**
Draft, edit the reason to match your intent:

```python
    "fire_metrics_standalone":
        "The chrome-less FIRE Metrics view loaded by the iOS native shell. "
        "It renders with standalone_mode=True, which suppresses the "
        "sidebar in base.html, so linking it from inside the web app "
        "would drop a person out of the navigation with no way back. The "
        "shell addresses it directly by URL.",
```

**If instead it is meant to be reachable from the web app**, link it from
wherever a person would look — the FIRE Metrics page or the dashboard —
and the test passes with no allowlist entry. Pick whichever matches the
intent; both are one small edit.

---

## 2. `test_the_notetaker_is_reachable_from_every_page` — a shared `LoginManager` gets re-pointed

**Where:** `tests/test_investors_nav.InvestorsNavTests`

**It passes alone and fails in the suite**, so this is shared state. Here
is the specific mechanism, proven by running it — not "test pollution".

**What it asserts.** That `/tools/investor-report/notes` appears on every
page, including `/dashboard`. It exists because the notetaker was once
reachable only by typing the URL, which is why Michelle asked for two
features that already existed.

**What actually happens.** After `tests/test_fire_metrics_standalone.py`
runs, every page in this test renders the **login page** — the test's
session user no longer authenticates, so it never sees an app page at all.
The nav is fine; the login is not.

**The mechanism, in four steps.**

1. `app.py` holds a **module-level singleton**: `login_manager = LoginManager()`.
2. `create_app()` registers the loader as a **closure over that call's app**:

   ```python
   @login_manager.user_loader
   def load_user(user_id: str) -> User | None:
       return User.get_by_id(user_id, app.config)   # <- captures THIS app
   ```

3. `tests/test_fire_metrics_standalone.py` calls `create_app(TestConfig)`
   in **`setUp`** — once per test — where `TestConfig.ADMIN_USERNAME =
   "test-admin"`. Each call **replaces** `login_manager._user_callback`
   with a loader closed over the TestConfig app.
4. `tearDown` restores `FIRE_METRICS_DB_PATH` and deletes the temp DB.
   **Nothing restores the user loader.** The module-level `app` still
   shares that same `login_manager`, so from then on it resolves users
   against `TestConfig`, not its own config.

Measured directly:

```
original app ADMIN_USERNAME: '<the real one>'
after create_app(TestConfig):
  user_loader replaced   : True
  closure captures app   : ADMIN_USERNAME = 'test-admin'
  loading the real admin through the shared loader : None
  loading 'test-admin'                             : <models.User object>
```

`None` is the whole failure. `test_investors_nav` sets `_user_id` to the
real app's admin, the loader says no such user, `@login_required`
redirects, and the assertion reads a login page.

**Note this is latent, not yours alone.** Any second `create_app()` call
anywhere does the same thing; your test is the first to make it. The
ordering is alphabetical, so `test_fire_metrics_standalone` happens to run
before `test_investors_nav` — any test after it that relies on being
logged in is exposed.

### DONE — fixed in `app.py`, `5d1f393`. Option A was taken.

**The defect was ours, not yours.** Your test is what made it visible;
it needed no change and passes as a consequence of the fix. `app.py` now
reads:

```python
@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return User.get_by_id(user_id, current_app.config)
```

Verified on the deployed container, because this touches the login path
and that path has already caused one client-facing outage this session:
the real admin still loads and reaches the dashboard, a bogus user is
still refused, a signed-out visitor is still redirected to `/login`, a bad
password still says so — and a second `create_app()` no longer disturbs
any of it.

The new tests pin the **property**, not the symptom. Asserting "the
notetaker link is on `/dashboard`" would let the same bug return through
any other page; `tests/test_login_manager_binding.py` asserts that two
applications authenticate their own users simultaneously and neither
accepts the other's.

### The three fixes that were on the table, cheapest last

**A. Fix the latent bug in `app.py` — one line, recommended.** Have the
loader read the *current* app rather than the captured one:

```python
from flask import current_app

@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return User.get_by_id(user_id, current_app.config)
```

`current_app` is bound inside a request context, which is the only place a
user loader runs. **Verified:** with this in place, the original app's
dashboard renders with the notetaker link *and* the second app still
authenticates `test-admin` — both work at once, which is the property that
is actually wanted. This is our file, so say the word and it is ours to
change, but it is your call whether you want it in the same PR.

**B. Don't build a second app.** Most tests in this suite use the shared
`from app import app` with `app.test_client()`. If `TestConfig` is only
there for `ADMIN_USERNAME` and CSRF, overriding `app.config` in `setUp`
and restoring in `tearDown` avoids the whole class.

**C. Restore the loader in `tearDown`.** Save `login_manager._user_callback`
in `setUp` and put it back. Cheapest, and it works, but it reaches into a
private attribute and leaves the trap armed for the next person.

---

## 3. `test_indexed_count_is_343` — a guard that ordinary local work can satisfy

**Where:** `tests/test_city_search.TestFullCoverageAudit` (from `2d537d5`)

**This one is invisible on a clean checkout and on CI, and appears on any
machine where somebody has opened the app locally** — which is why it is
worth reading even though it looks trivial.

```
AssertionError: 0 != 343
```

### DONE — the guard is fixed in `f6b39d6`. Your `343` assertion is untouched.

**And my first explanation of this was wrong, which is worth reading
because the wrong version is the more obvious one.**

I originally wrote that the class's own `setUpClass` created the file via
`get_connection()`. It does call that, and `get_connection` does
`mkdir` + `sqlite3.connect`, which would create it — so the story fitted.
**It is still wrong.** With the old guard, the class *skips* when the file
is absent, so `setUpClass` never runs and cannot be the creator.
Demonstrated by restoring the old guard on a clean tree: the file was not
recreated and the second run passed. That killed my own explanation.

**The real chain, measured rather than inferred:**

1. `get_db_path()` falls back to `fire_metrics/output/fire_metrics.db`
   when `FIRE_METRICS_DB_PATH` is unset.
2. So **opening the FIRE Metrics page on a dev machine creates it**,
   empty. Verified: `GET /tools/fire-metrics/` with the variable unset
   leaves a zero-row database behind. **Nothing is wrong with that** — it
   is the app doing its job, and it is why the file appeared in my tree
   with no commit touching it.
   (Inside the suite this does not happen: `test_investors_nav` and
   `test_route_reachability` set `FIRE_METRICS_DB_PATH` to a sandbox at
   import time, and env vars are process-global.)
3. The file is **gitignored and untracked** (`.gitignore:28`), so a fresh
   clone and CI never have it and always look green.
4. Once it exists, `skipUnless(DB_PATH.exists())` admits the class and the
   audit runs against a schema with no rows: `0 != 343`.

Green on a clean checkout, red forever after on the same machine, with no
change to any code — and the thing that changed is invisible to git.

**The fix: the guard asks the wrong question.** It asks about a *file*
where the class needs *data*. Running the audit against a temp database
was the other option and is wrong here — this class audits **real** Census
coverage, so a temp database has nothing to audit and the test would pass
by being empty.

`_has_indexed_cities()` now opens the database `mode=ro`, which
**cannot create a missing file**, and counts rows. Behaviour is now
identical across runs: absent, present-but-empty, and present-with-an-
empty-schema all skip; populated runs the audit. Four tests pin it,
including a positive control — every other assertion would pass on a
guard rewritten to `return False`.

**What shipped**, close to this sketch:

```python
def _has_indexed_cities() -> bool:
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM cities WHERE include_flag=1").fetchone()[0] > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()

@unittest.skipUnless(_has_indexed_cities(), "fire_metrics.db has no indexed cities")
```

Read-only (`mode=ro`), so it cannot create the file it is asking about.

**Still yours, and deliberately not touched:** `343` is a hard-coded count
of live Census data. It will fail the day the index legitimately changes, and the
failure will not say why. A lower bound (`assertGreater(len(...), 300)`)
tests the same property — coverage is broad — without pinning a number
that has no reason to stay fixed.

---

## Where this leaves things

Master is green apart from the two known node-absent failures in
`tests.test_fire_metrics_ai_summary`, which need `node` in the image and
are unrelated to any of this.

**Nothing is waiting on you.** Two things you may want to look at when
convenient, neither urgent:

* whether `/fire-metrics/` was meant to be linked after all (§1), and
  whether `capacitor.config.json` should point at it rather than the site
  root;
* whether `343` should be a lower bound rather than an exact count (§3).

**One note on method, since it cost me twice here.** I asserted a
mechanism instead of running one on both the capacitor claim and the
file-creation chain, and both were wrong in the same way: a story that
fitted the evidence, believed because it fitted. The handoff already
carries this rule — *before claiming what a mechanism does, run it* — and
it earned itself again. Everything above that survived is what a command
returned, not what I reasoned.

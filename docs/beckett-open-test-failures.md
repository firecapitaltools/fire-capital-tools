# Three test failures from `72d6be1` and `2d537d5` — for Beckett

**Written 2026-08-28 against master `d548c59`. Not fixed — these are your
changes and the calls are yours.** Everything below was reproduced and the
proposed fixes were run, not guessed. Nothing here is a style objection.

Reproduce all three:

```
python -m unittest discover -s tests -t .
```

Two were introduced by **`72d6be1` "Add standalone FIRE Metrics view"**.
The third comes from **`2d537d5` "Fix FIRE Metrics city search coverage"**
and only appears on the *second* run on a given machine — see §3, which is
the one most likely to waste your time.

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

**This is almost certainly the allowlist case, not the link case.** The
route renders with `standalone_mode=True`, which `base.html` uses to
suppress the entire sidebar, and it landed alongside `capacitor.config.json`
and *"safe area handling for iOS native shell"*. A chrome-less view whose
consumer is a native shell is genuinely URL-only by design — that is a
legitimate entry, and the allowlist exists for precisely this.

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

### Three fixes, cheapest last

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

## 3. `test_indexed_count_is_343` — the test creates the database that makes it run

**Where:** `tests/test_city_search.TestFullCoverageAudit` (from `2d537d5`)

**This one is invisible on a clean checkout and appears on the second
run**, which is why it is worth reading even though it looks trivial.

```
AssertionError: 0 != 343
```

**The chain:**

1. The class is guarded by
   `@unittest.skipUnless(DB_PATH.exists(), "fire_metrics.db not present")`,
   where `DB_PATH` is `fire_metrics/output/fire_metrics.db`. That file is
   **gitignored and untracked** (`.gitignore:28`), so on a fresh clone it
   is absent and the class skips. That is why CI and a clean worktree look
   green.
2. `setUpClass` calls `db_module.get_connection(DB_PATH)`, and that
   function does:

   ```python
   path.parent.mkdir(parents=True, exist_ok=True)
   conn = sqlite3.connect(str(path))
   init_schema(conn)
   ```

   `sqlite3.connect` **creates** the file. So the guard's own setup
   manufactures the condition the guard tests for.
3. On the next run the file exists, the class no longer skips, and it
   asserts 343 cities against an empty schema. `0 != 343`.

So the suite is green once and red forever after, on the same machine,
with no change to any code. I hit exactly this: a 49KB, zero-city
`fire_metrics.db` appeared in my working tree with no commit touching it.

**Smallest fix.** Make the guard test what the class actually needs —
populated data, not a file:

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

**Worth considering separately:** `343` is a hard-coded count of live
Census data. It will fail the day the index legitimately changes, and the
failure will not say why. A lower bound (`assertGreater(len(...), 300)`)
tests the same property — coverage is broad — without pinning a number
that has no reason to stay fixed.

---

## Nothing here blocks anything of ours

Site DD work is merged and green around these. This is only so you have
the diagnosis without re-deriving it. If you would rather any of the three
were fixed on our side — particularly the `current_app` one-liner in §2A,
which is our file and a latent bug regardless of your change — say so and
it will be done.

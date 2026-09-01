"""Regression tests for FIRE Metrics city search and index-building normalization.

Covers:
- Census suffix stripping in _clean_display_city (including "(balance)" variants)
- Canonical alias generation for compound/prefixed Census names
- find_city_match behavior for previously-broken cities
- Startup migration: old pre-fix DB gets corrected automatically via get_connection
- Full >=100k coverage: every indexed city must be findable by canonical name+state
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

# Ensure project root is importable.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fire_metrics.fire_metrics_updater.city_search import (
    build_city_aliases,
    find_city_match,
    normalize_city_tokens,
)
from fire_metrics.fire_metrics_updater.index_builder import (
    _canonical_city_aliases,
    _clean_display_city,
    _identity_row,
)
from fire_metrics.fire_metrics_updater import db as db_module

# Resolved the way the APPLICATION resolves it, which is the whole fix.
# This was hardcoded to the repo-relative fallback while production sets
# FIRE_METRICS_DB_PATH=/data/fire_metrics.db -- so the file was empty
# here, absent there, and the guard below skipped in BOTH environments.
# Three tests asserting the 343-city index had never run anywhere.
# get_db_path() returns this same path when the variable is unset, so
# local behaviour is unchanged; on the container the audit now runs.
DB_PATH = db_module.get_db_path()


def _make_index(*city_state_pairs):
    """Build a minimal city_index dict from raw Census names for unit testing."""
    return {"cities": [_identity_row(c, s) for c, s in city_state_pairs]}


class TestCleanDisplayCity(unittest.TestCase):

    def test_strips_plain_city_suffix(self):
        self.assertEqual(_clean_display_city("Akron city"), "Akron")

    def test_strips_city_balance_suffix(self):
        # Indianapolis was the primary bug: "(balance)" after "city" wasn't stripped
        self.assertEqual(_clean_display_city("Indianapolis city (balance)"), "Indianapolis")

    def test_strips_town_balance_suffix(self):
        self.assertEqual(_clean_display_city("Springfield town (balance)"), "Springfield")

    def test_strips_metro_government_balance(self):
        result = _clean_display_city("Nashville-Davidson metropolitan government (balance)")
        self.assertEqual(result, "Nashville-Davidson")

    def test_strips_metro_government_balance_louisville(self):
        result = _clean_display_city("Louisville/Jefferson County metro government (balance)")
        self.assertEqual(result, "Louisville/Jefferson County")

    def test_strips_urban_county(self):
        result = _clean_display_city("Lexington-Fayette urban county")
        self.assertEqual(result, "Lexington-Fayette")

    def test_strips_consolidated_government_balance(self):
        result = _clean_display_city("Augusta-Richmond County consolidated government (balance)")
        self.assertEqual(result, "Augusta-Richmond County")

    def test_strips_cdp(self):
        result = _clean_display_city("Urban Honolulu CDP")
        self.assertEqual(result, "Urban Honolulu")

    def test_preserves_city_proper_noun(self):
        # "Boise City city" → strip lowercase suffix → "Boise City"
        self.assertEqual(_clean_display_city("Boise City city"), "Boise City")

    def test_preserves_kansas_city(self):
        # "Kansas City" should NOT be stripped further (it's a real city name)
        self.assertEqual(_clean_display_city("Kansas City city"), "Kansas City")


class TestCanonicalCityAliases(unittest.TestCase):

    def test_slash_form(self):
        keys = _canonical_city_aliases("Louisville/Jefferson County", "KY")
        self.assertIn("louisville", keys)
        self.assertIn("louisville ky", keys)

    def test_hyphen_form_nashville(self):
        keys = _canonical_city_aliases("Nashville-Davidson", "TN")
        self.assertIn("nashville", keys)
        self.assertIn("nashville tn", keys)

    def test_hyphen_form_lexington(self):
        keys = _canonical_city_aliases("Lexington-Fayette", "KY")
        self.assertIn("lexington", keys)
        self.assertIn("lexington ky", keys)

    def test_hyphen_form_augusta(self):
        keys = _canonical_city_aliases("Augusta-Richmond County", "GA")
        self.assertIn("augusta", keys)
        self.assertIn("augusta ga", keys)

    def test_urban_prefix(self):
        keys = _canonical_city_aliases("Urban Honolulu", "HI")
        self.assertIn("honolulu", keys)
        self.assertIn("honolulu hi", keys)

    def test_city_suffix(self):
        keys = _canonical_city_aliases("Boise City", "ID")
        self.assertIn("boise", keys)
        self.assertIn("boise id", keys)

    def test_simple_name_no_extra_aliases(self):
        # A simple already-clean name should not generate bad extra aliases
        keys = _canonical_city_aliases("Akron", "OH")
        self.assertEqual(keys, set())

    def test_no_aliases_for_empty_part(self):
        # Guard: if stripping left nothing, return empty
        keys = _canonical_city_aliases("City", "OH")
        # "City".endswith(" City") is False (no space before City), so no aliases
        self.assertNotIn("", keys)


class TestFindCityMatch(unittest.TestCase):
    """End-to-end search tests using in-memory indexes built from _identity_row."""

    def _search(self, query, city_index, excluded_index=None):
        return find_city_match(query, city_index, excluded_index or {"excluded": []})

    # --- Indianapolis (city balance) ---

    def test_indianapolis_bare(self):
        idx = _make_index(("Indianapolis city (balance)", "IN"))
        result = self._search("Indianapolis", idx)
        self.assertEqual(result["status"], "found")
        self.assertIn("Indianapolis", result["city"]["display_name"])

    def test_indianapolis_with_state(self):
        idx = _make_index(("Indianapolis city (balance)", "IN"))
        result = self._search("Indianapolis, IN", idx)
        self.assertEqual(result["status"], "found")

    # --- Louisville (slash consolidated government) ---

    def test_louisville_bare(self):
        idx = _make_index(("Louisville/Jefferson County metro government (balance)", "KY"))
        result = self._search("Louisville", idx)
        self.assertEqual(result["status"], "found")

    def test_louisville_with_state(self):
        idx = _make_index(("Louisville/Jefferson County metro government (balance)", "KY"))
        result = self._search("Louisville, KY", idx)
        self.assertEqual(result["status"], "found")

    # --- Ohio cities ---

    def test_akron_bare(self):
        idx = _make_index(("Akron city", "OH"))
        result = self._search("Akron", idx)
        self.assertEqual(result["status"], "found")

    def test_akron_with_state(self):
        idx = _make_index(("Akron city", "OH"))
        result = self._search("Akron, OH", idx)
        self.assertEqual(result["status"], "found")

    def test_dayton_bare(self):
        idx = _make_index(("Dayton city", "OH"))
        result = self._search("Dayton", idx)
        self.assertEqual(result["status"], "found")

    def test_toledo_bare(self):
        idx = _make_index(("Toledo city", "OH"))
        result = self._search("Toledo", idx)
        self.assertEqual(result["status"], "found")

    # --- San Francisco (existing city must still work) ---

    def test_san_francisco_bare(self):
        idx = _make_index(("San Francisco city", "CA"))
        result = self._search("San Francisco", idx)
        self.assertEqual(result["status"], "found")

    def test_san_francisco_with_state(self):
        idx = _make_index(("San Francisco city", "CA"))
        result = self._search("San Francisco, CA", idx)
        self.assertEqual(result["status"], "found")

    # --- City + state abbreviation disambiguation ---

    def test_state_disambiguates_columbus(self):
        idx = _make_index(("Columbus city", "OH"), ("Columbus city", "GA"))
        bare_result = self._search("Columbus", idx)
        # Bare search: two cities → suggestions
        self.assertEqual(bare_result["status"], "suggestions")
        # With state: unique match
        oh_result = self._search("Columbus, OH", idx)
        self.assertEqual(oh_result["status"], "found")
        self.assertIn("OH", oh_result["city"]["display_name"])
        ga_result = self._search("Columbus, GA", idx)
        self.assertEqual(ga_result["status"], "found")
        self.assertIn("GA", ga_result["city"]["display_name"])

    # --- Known query aliases ---

    def test_nyc_alias(self):
        idx = _make_index(("New York city", "NY"))
        result = self._search("NYC", idx)
        self.assertEqual(result["status"], "found")

    def test_la_alias(self):
        idx = _make_index(("Los Angeles city", "CA"))
        result = self._search("LA", idx)
        self.assertEqual(result["status"], "found")


class TestStartupMigration(unittest.TestCase):
    """Prove that an existing DB with pre-fix stale aliases is corrected automatically
    by get_connection (which calls init_schema → _migrate_search_aliases_v2).
    """

    def _build_old_db(self, tmp_path: str) -> None:
        """Populate a minimal pre-fix DB: cities present, aliases stale (no v2 sentinel)."""
        conn = sqlite3.connect(tmp_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cities (
                city TEXT NOT NULL, state TEXT NOT NULL,
                display_name TEXT NOT NULL, normalized_city TEXT NOT NULL,
                normalized_display_name TEXT NOT NULL, search_key TEXT NOT NULL,
                latitude REAL, longitude REAL,
                include_flag INTEGER NOT NULL DEFAULT 1, threshold_reason TEXT,
                population_rank REAL, population_current REAL,
                population_growth_2020_2025 REAL, population_growth_recent REAL,
                landlord_friendliness_score REAL, landlord_friendliness_label TEXT,
                population_updated_at TEXT, median_income_current REAL,
                median_income_growth_2021_2024 REAL, median_income_growth_recent REAL,
                income_updated_at TEXT, median_home_value_current REAL,
                median_home_value_growth_2021_2024 REAL, median_home_value_growth_recent REAL,
                home_value_updated_at TEXT, employment_current REAL,
                employment_growth_2021_2025 REAL, employment_growth_recent REAL,
                employment_updated_at TEXT, climate_risk_score REAL,
                climate_risk_rating TEXT, climate_updated_at TEXT,
                crime_index_score REAL, crime_rating TEXT, density_adjusted_crime_score REAL,
                density_adjusted_crime_rating TEXT, crime_manual_review TEXT,
                crime_updated_at TEXT, PRIMARY KEY (city, state)
            );
            CREATE TABLE IF NOT EXISTS search_aliases (
                search_key TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY (search_key, city, state)
            );
            CREATE TABLE IF NOT EXISTS excluded_cities (
                city TEXT NOT NULL, state TEXT NOT NULL, normalized_city TEXT,
                normalized_key TEXT, latest_population REAL, threshold_reason TEXT,
                PRIMARY KEY (city, state)
            );
            CREATE TABLE IF NOT EXISTS refresh_metadata (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS fire_metrics_city_summaries (
                city TEXT NOT NULL, state TEXT NOT NULL, city_key TEXT NOT NULL,
                data_fingerprint TEXT NOT NULL, model_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL, summary_text TEXT NOT NULL,
                strength_sentence TEXT NOT NULL, weakness_sentence TEXT NOT NULL,
                comparison_sentence TEXT NOT NULL, generated_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (city, state, data_fingerprint, model_name, prompt_version)
            );
        """)
        # Insert the two problem cities with stale pre-fix display names and aliases
        stale_rows = [
            ("Indianapolis city (balance)", "IN",
             "Indianapolis city (balance), IN",
             "indianapolis city balance", "indianapolis city balance in",
             "indianapolis city balance in", 123456),
            ("Louisville/Jefferson County metro government (balance)", "KY",
             "Louisville/Jefferson County, KY",
             "louisville jefferson county", "louisville jefferson county ky",
             "louisville jefferson county ky", 654321),
        ]
        for city, state, disp, norm_city, norm_disp, skey, pop in stale_rows:
            conn.execute(
                """INSERT INTO cities (city, state, display_name, normalized_city,
                   normalized_display_name, search_key, include_flag, population_current)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (city, state, disp, norm_city, norm_disp, skey, pop),
            )
        # Insert ONLY the stale aliases (the ones that existed before the fix)
        stale_aliases = [
            ("indianapolis city balance", "Indianapolis city (balance)", "IN"),
            ("indianapolis city balance in", "Indianapolis city (balance)", "IN"),
            ("louisville jefferson county", "Louisville/Jefferson County metro government (balance)", "KY"),
            ("louisville jefferson county ky", "Louisville/Jefferson County metro government (balance)", "KY"),
        ]
        for key, city, state in stale_aliases:
            conn.execute(
                "INSERT OR IGNORE INTO search_aliases (search_key, city, state) VALUES (?, ?, ?)",
                (key, city, state),
            )
        conn.commit()
        conn.close()

    def test_migration_fixes_indianapolis_and_louisville(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            self._build_old_db(tmp_path)

            # Confirm stale state before migration
            pre = sqlite3.connect(tmp_path)
            pre.row_factory = sqlite3.Row
            pre_aliases = {r["search_key"] for r in pre.execute(
                "SELECT search_key FROM search_aliases WHERE city = ?",
                ("Indianapolis city (balance)",)
            ).fetchall()}
            self.assertNotIn("indianapolis", pre_aliases, "Pre-condition: 'indianapolis' should NOT exist yet")
            self.assertNotIn("louisville", {r["search_key"] for r in pre.execute(
                "SELECT search_key FROM search_aliases WHERE city = ?",
                ("Louisville/Jefferson County metro government (balance)",)
            ).fetchall()})
            pre.close()

            # Run migration via normal get_connection (the production startup path)
            from fire_metrics.fire_metrics_updater import db as db_module
            from fire_metrics.fire_metrics_updater.city_search import find_city_match

            with db_module.get_connection(Path(tmp_path)) as conn:
                city_index = db_module.build_city_index_payload(conn)
                excluded_index = db_module.build_excluded_index_payload(conn)

            # Confirm aliases are now correct
            post = sqlite3.connect(tmp_path)
            post.row_factory = sqlite3.Row
            indy_aliases = {r["search_key"] for r in post.execute(
                "SELECT search_key FROM search_aliases WHERE city = ?",
                ("Indianapolis city (balance)",)
            ).fetchall()}
            self.assertIn("indianapolis", indy_aliases)
            self.assertIn("indianapolis in", indy_aliases)

            lou_aliases = {r["search_key"] for r in post.execute(
                "SELECT search_key FROM search_aliases WHERE city = ?",
                ("Louisville/Jefferson County metro government (balance)",)
            ).fetchall()}
            self.assertIn("louisville", lou_aliases)
            self.assertIn("louisville ky", lou_aliases)
            post.close()

            # Confirm searches now work
            indy = find_city_match("Indianapolis", city_index, excluded_index)
            self.assertEqual(indy["status"], "found")
            self.assertIn("Indianapolis", indy["city"]["display_name"])

            lou = find_city_match("Louisville, KY", city_index, excluded_index)
            self.assertEqual(lou["status"], "found")
            self.assertIn("Louisville", lou["city"]["display_name"])

        finally:
            import os
            os.unlink(tmp_path)

    def test_migration_is_idempotent(self):
        """Running get_connection twice does not corrupt aliases or fail."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name
        try:
            self._build_old_db(tmp_path)
            from fire_metrics.fire_metrics_updater import db as db_module
            with db_module.get_connection(Path(tmp_path)) as conn:
                count_after_first = conn.execute(
                    "SELECT COUNT(*) FROM search_aliases WHERE city = ?",
                    ("Indianapolis city (balance)",)
                ).fetchone()[0]
            with db_module.get_connection(Path(tmp_path)) as conn:
                count_after_second = conn.execute(
                    "SELECT COUNT(*) FROM search_aliases WHERE city = ?",
                    ("Indianapolis city (balance)",)
                ).fetchone()[0]
            self.assertEqual(count_after_first, count_after_second)
        finally:
            import os
            os.unlink(tmp_path)

    def test_sentinel_is_set_after_migration(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name
        try:
            self._build_old_db(tmp_path)
            from fire_metrics.fire_metrics_updater import db as db_module
            with db_module.get_connection(Path(tmp_path)) as conn:
                meta = db_module.get_metadata(conn)
            self.assertEqual(meta.get("search_alias_version"), "2")
        finally:
            import os
            os.unlink(tmp_path)


def _has_indexed_cities() -> bool:
    """Whether there is real data here to audit. READ ONLY, and that is
    the entire point of this function.

    THE GUARD ASKED THE WRONG QUESTION, AND ORDINARY WORK ANSWERED IT.

    It was `skipUnless(DB_PATH.exists())` -- a question about a FILE,
    where the class needs DATA. `get_db_path()` falls back to this exact
    path when FIRE_METRICS_DB_PATH is unset, so **opening the FIRE
    Metrics page on a dev machine creates it**, empty. Verified:
    `GET /tools/fire-metrics/` with the variable unset leaves a
    zero-row database behind, and there is nothing wrong with that --
    it is the app doing its job.

    From then on the file exists, the old guard admits the class, and
    the audit runs against a schema with no rows: `0 != 343`. Green on a
    clean checkout, red forever after on the same machine, with no
    commit in between -- and the thing that changed is untracked and
    gitignored, so it is invisible to git.

    (An earlier write-up of this blamed the class's own setUpClass for
    creating the file. That was wrong and is corrected here: with the
    old guard the class SKIPS when the file is absent, so setUpClass
    never runs and cannot be the creator. The mechanism above was
    measured rather than inferred.)

    Two ways to fix that were available: run the audit against a
    temporary database, or make the guard test something the setup
    cannot manufacture. The first is wrong here -- this class audits
    REAL Census coverage, and a temp database has nothing to audit, so
    the test would pass by being empty. So the guard is what changes.

    `mode=ro` on the URI is what makes it true rather than merely
    intended: a read-only connection cannot create a missing file, so
    this function is incapable of manufacturing its own precondition.
    """
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM cities WHERE include_flag=1").fetchone()[0] > 0
    except sqlite3.Error:
        # No `cities` table: an empty database left behind by the old
        # guard, or one that predates the schema. Nothing to audit.
        return False
    finally:
        conn.close()


class TestTheGuardCannotManufactureItsOwnPrecondition(unittest.TestCase):
    """The regression for the self-poisoning skip.

    A skip condition that CREATES the file it is testing for makes a
    suite green once and red forever after on the same machine, with no
    commit in between. That is worse than a plain failure, because the
    thing that changed is invisible to git.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "nested" / "fire_metrics.db"

    def test_asking_about_a_missing_file_does_not_create_it(self):
        """THE ONE THAT MATTERS."""
        import tests.test_city_search as mod
        real, mod.DB_PATH = mod.DB_PATH, self.tmp
        try:
            self.assertFalse(mod._has_indexed_cities())
        finally:
            mod.DB_PATH = real
        self.assertFalse(self.tmp.exists(), "the guard created the database")
        self.assertFalse(self.tmp.parent.exists(),
                         "the guard created the directory")

    def test_an_empty_database_reads_as_nothing_to_audit(self):
        """What every machine that ran the old guard is left holding."""
        import tests.test_city_search as mod
        self.tmp.parent.mkdir(parents=True, exist_ok=True)
        sqlite3.connect(self.tmp).close()
        real, mod.DB_PATH = mod.DB_PATH, self.tmp
        try:
            self.assertFalse(mod._has_indexed_cities())
        finally:
            mod.DB_PATH = real

    def test_a_schema_with_no_rows_reads_as_nothing_to_audit(self):
        import tests.test_city_search as mod
        self.tmp.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.tmp)
        conn.execute("CREATE TABLE cities (city TEXT, state TEXT, "
                     "population_current INT, include_flag INT)")
        conn.commit()
        conn.close()
        real, mod.DB_PATH = mod.DB_PATH, self.tmp
        try:
            self.assertFalse(mod._has_indexed_cities())
        finally:
            mod.DB_PATH = real

    def test_positive_control_real_rows_read_as_something_to_audit(self):
        """Without this, every assertion above would pass on a guard that
        had simply been changed to `return False`."""
        import tests.test_city_search as mod
        self.tmp.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.tmp)
        conn.execute("CREATE TABLE cities (city TEXT, state TEXT, "
                     "population_current INT, include_flag INT)")
        conn.execute("INSERT INTO cities VALUES ('Akron city','OH',190000,1)")
        conn.commit()
        conn.close()
        real, mod.DB_PATH = mod.DB_PATH, self.tmp
        try:
            self.assertTrue(mod._has_indexed_cities())
        finally:
            mod.DB_PATH = real


@unittest.skipUnless(_has_indexed_cities(),
                     "fire_metrics.db has no indexed cities to audit")
class TestFullCoverageAudit(unittest.TestCase):
    """Verify every >=100k city in the DB is findable by canonical-name + state search."""

    @classmethod
    def setUpClass(cls):
        with db_module.get_connection(DB_PATH) as conn:
            cls.city_index = db_module.build_city_index_payload(conn)
            cls.excluded_index = db_module.build_excluded_index_payload(conn)
        raw_conn = sqlite3.connect(DB_PATH)
        raw_conn.row_factory = sqlite3.Row
        cls.all_cities = raw_conn.execute(
            "SELECT city, state, population_current FROM cities WHERE include_flag=1"
        ).fetchall()
        raw_conn.close()

    def _canonical_name(self, raw_city):
        clean = _clean_display_city(raw_city)
        if "/" in clean:
            return clean.split("/")[0].strip()
        if "-" in clean:
            return clean.split("-")[0].strip()
        if clean.lower().startswith("urban "):
            return clean[6:].strip()
        if clean.endswith(" City") and len(clean) > 5:
            return clean[:-5].strip()
        return clean

    def test_all_cities_have_population(self):
        missing = [(r["city"], r["state"]) for r in self.all_cities if r["population_current"] is None]
        self.assertEqual(missing, [], f"Cities missing population: {missing}")

    def test_all_cities_searchable_by_canonical_name_and_state(self):
        failures = []
        for r in self.all_cities:
            canonical = self._canonical_name(r["city"])
            query = f"{canonical}, {r['state']}"
            result = find_city_match(query, self.city_index, self.excluded_index)
            if result["status"] != "found":
                failures.append((r["city"], r["state"], query, result["status"]))
            elif result["city"]["city"] != r["city"] or result["city"]["state"] != r["state"]:
                wrong = result["city"].get("display_name")
                failures.append((r["city"], r["state"], query, f"WRONG: {wrong}"))
        self.assertEqual(
            failures, [],
            f"{len(failures)} cities not searchable by canonical name:\n" +
            "\n".join(f"  {c} ({s}) query={q!r} → {e}" for c, s, q, e in failures),
        )

    def test_indexed_count_is_343(self):
        self.assertEqual(len(self.all_cities), 343)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Overriding the subject size re-asks RentCast, and says that it did.

THE PROBLEM

RentCast resolves a multi-unit address to ONE unit and matches the
comparables to that unit's size. A building whose 2-beds Michelle is
underwriting can come back as a studio, and the estimate is then correct
about the wrong apartment. The page already disclosed which unit it
picked; this lets her correct it.

THE PREMISE THAT WAS WRONG

A Part 21 note held that `/avm/rent/long-term` takes no bedrooms
parameter, and Part 45's brief restated it as settled. It is false.
RentCast documents `propertyType`, `bedrooms`, `bathrooms` and
`squareFootage` as query parameters and is explicit: "if provided, these
values will override any attributes that are looked up automatically."
`lookupSubjectAttributes` defaults to true, which is why an address
resolves to a unit at all.

Corroboration that those docs describe the endpoint we actually call:
they give `compCount` a default of 15, and every cached row in production
carries exactly 15 comparables.

WHAT THIS FILE PINS

  * the override is sent as a parameter, and ONLY when supplied
  * it spends once, then caches -- re-opening the page must not re-spend
  * the result is a different artifact and carries provenance saying so
  * a typo cannot buy a lookup
  * the existing disclosure composes with it instead of contradicting it
"""

import re
import unittest
from pathlib import Path
from unittest import mock

from tools import market_data_cache as cache
from tools import market_data_service as svc

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "templates" / "tools" / "rent_comps.html"


class TheOverrideGetsItsOwnCacheRowTests(unittest.TestCase):
    """It answers a different question, so it must not overwrite the other."""

    BASE = "24 steiner san francisco ca 94117"

    def test_no_override_leaves_the_key_alone(self):
        self.assertEqual(cache.override_address_key(self.BASE, None), self.BASE)

    def test_an_override_makes_a_distinct_key(self):
        keyed = cache.override_address_key(self.BASE, 2)
        self.assertNotEqual(keyed, self.BASE)
        self.assertTrue(cache.is_override_key(keyed))
        self.assertFalse(cache.is_override_key(self.BASE))

    def test_different_sizes_do_not_collide(self):
        self.assertNotEqual(cache.override_address_key(self.BASE, 1),
                            cache.override_address_key(self.BASE, 2))

    def test_a_studio_override_is_kept_not_dropped(self):
        """0 is a real answer, and the falsy-zero trap started on this field."""
        keyed = cache.override_address_key(self.BASE, 0)
        self.assertTrue(cache.is_override_key(keyed))
        self.assertTrue(keyed.endswith("0"))

    def test_the_key_is_stable_across_int_and_float(self):
        self.assertEqual(cache.override_address_key(self.BASE, 2),
                         cache.override_address_key(self.BASE, 2.0))

    def test_no_real_address_can_forge_the_marker(self):
        """The marker must not be producible by the key function itself.

        normalize_address_key only lowercases and collapses whitespace, so
        anything a user types survives into the key. The marker carries a
        vertical bar, which no postal address supplies -- asserted here
        rather than assumed, including against an address that tries.
        """
        hostile = cache.normalize_address_key(
            "24 Steiner |subject-beds=2", "San Francisco", "CA", "94117")
        # The guarantee is NOT "the text cannot be typed" -- it plainly
        # can, and is_override_key() sees it, which this asserts rather
        # than hides. The guarantee is positional: the marker is appended
        # after the zip, and a street field cannot reach that position, so
        # a typed marker never produces the key an override produces.
        self.assertTrue(cache.is_override_key(hostile))
        self.assertFalse(hostile.endswith("|subject-beds=2"))
        self.assertNotEqual(hostile, cache.override_address_key(
            cache.normalize_address_key("24 Steiner", "San Francisco", "CA", "94117"), 2))
        self.assertTrue(cache.override_address_key(hostile, 2)
                        .endswith("|subject-beds=2"))


class TheParameterIsSentOnlyWhenSuppliedTests(unittest.TestCase):
    """An ordinary lookup must be the request it always was."""

    def call_with(self, bedrooms):
        captured = {}

        class Resp:
            status_code = 200
            ok = True

            @staticmethod
            def json():
                return {"rent": 3000, "rentRangeLow": 2500,
                        "rentRangeHigh": 3500, "comparables": []}

        def fake_get(url, headers=None, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return Resp()

        with mock.patch.object(svc, "_rentcast_api_key", return_value="k"), \
             mock.patch.object(svc, "_rentcast_usage_gate", return_value=None), \
             mock.patch.object(svc, "_record_rentcast_call"), \
             mock.patch.object(svc.requests, "get", fake_get):
            data = svc.get_rentcast_data("24 Steiner", "San Francisco", "CA",
                                         "94117", bedrooms=bedrooms)
        return captured, data

    def test_an_ordinary_lookup_sends_only_the_address(self):
        captured, data = self.call_with(None)
        self.assertEqual(list(captured["params"]), ["address"])
        self.assertIsNone(data["subject_override"])

    def test_an_override_sends_bedrooms(self):
        captured, data = self.call_with(2)
        self.assertEqual(captured["params"]["bedrooms"], 2)
        self.assertIn("24 Steiner", captured["params"]["address"])

    def test_a_studio_override_is_sent_not_swallowed(self):
        captured, _ = self.call_with(0)
        self.assertEqual(captured["params"]["bedrooms"], 0)

    def test_the_provenance_travels_with_the_payload(self):
        """A cached row read months later must say which artifact it is."""
        _, data = self.call_with(2)
        self.assertEqual(data["subject_override"], {"bedrooms": 2})


class ReopeningThePageDoesNotRespendTests(unittest.TestCase):
    """The caching requirement, checked by counting real calls.

    THE CACHE IS REDIRECTED BY PATCHING get_db_path, NOT THE ENV VAR

    The first version of these tests set MARKET_CACHE_DB_PATH, which is
    not the name of anything -- the real variable is MARKET_DATA_DB_PATH.
    The redirect silently did nothing and the test wrote two rows into the
    developer's own cache database. Nothing was spent, because the network
    layer was mocked, but a misspelled environment variable fails OPEN:
    it does not error, it just uses the default.

    Patching the function is closed by construction. A typo there is an
    AttributeError, not a silent write to the real file.
    """

    def redirect_cache(self):
        import tempfile
        db = Path(tempfile.mkdtemp()) / "cache.db"
        return mock.patch.object(cache, "get_db_path", lambda: db)

    def test_a_cached_override_costs_nothing(self):
        calls = []

        def fake_rentcast(address, city, state, zip_code=None, bedrooms=None):
            calls.append(bedrooms)
            return {"available": True, "comparables": [],
                    "subject_override": ({"bedrooms": bedrooms}
                                         if bedrooms is not None else None)}

        with self.redirect_cache(), \
             mock.patch.object(svc, "get_rentcast_data", fake_rentcast), \
             mock.patch.object(svc, "get_google_place_rating",
                               return_value={"available": False}):
            first = svc.get_market_data("24 Steiner", "San Francisco", "CA",
                                        "94117", bedrooms_override=2)
            second = svc.get_market_data("24 Steiner", "San Francisco", "CA",
                                         "94117", bedrooms_override=2)

        self.assertEqual(calls, [2], "the second view must not spend")
        self.assertFalse(first["from_cache"])
        self.assertTrue(second["from_cache"])

    def test_the_override_does_not_overwrite_the_automatic_answer(self):
        calls = []

        def fake_rentcast(address, city, state, zip_code=None, bedrooms=None):
            calls.append(bedrooms)
            return {"available": True, "rent_estimate": 9000 if bedrooms else 3000,
                    "comparables": [],
                    "subject_override": ({"bedrooms": bedrooms}
                                         if bedrooms is not None else None)}

        with self.redirect_cache(), \
             mock.patch.object(svc, "get_rentcast_data", fake_rentcast), \
             mock.patch.object(svc, "get_google_place_rating",
                               return_value={"available": False}):
            auto = svc.get_market_data("24 Steiner", "San Francisco", "CA", "94117")
            svc.get_market_data("24 Steiner", "San Francisco", "CA", "94117",
                                bedrooms_override=2)
            auto_again = svc.get_market_data("24 Steiner", "San Francisco",
                                             "CA", "94117")

        self.assertEqual(calls, [None, 2], "each artifact is fetched once")
        self.assertTrue(auto_again["from_cache"])
        self.assertEqual(auto_again["rentcast"]["rent_estimate"],
                         auto["rentcast"]["rent_estimate"])
        self.assertIsNone(auto_again["rentcast"]["subject_override"])


class ATypoCannotBuyALookupTests(unittest.TestCase):
    """The one path that spends on caller-supplied input."""

    def parse(self, raw):
        """Driven through a real request context, not a mocked proxy.

        `request` is a LocalProxy; patching it tests the patch rather than
        the parsing. A test request context runs the same lookup Flask
        would, including the form/args fallback.
        """
        from app import app
        from tools import rent_comps
        with app.test_request_context(f"/?override_beds={raw}"):
            return rent_comps._override_beds()

    def test_a_real_size_is_accepted(self):
        self.assertEqual(self.parse("2"), 2)

    def test_a_studio_is_accepted(self):
        self.assertEqual(self.parse("0"), 0)

    def test_junk_is_refused(self):
        for raw in ("", "   ", "two", "2.5", "-1", "999", "1e3"):
            with self.subTest(raw=raw):
                self.assertIsNone(self.parse(raw))

    def test_the_ceiling_is_a_real_building(self):
        from tools.rent_comps import MAX_OVERRIDE_BEDS
        self.assertEqual(self.parse(str(MAX_OVERRIDE_BEDS)), MAX_OVERRIDE_BEDS)
        self.assertIsNone(self.parse(str(MAX_OVERRIDE_BEDS + 1)))


class ThePageAsksBeforeItSpendsTests(unittest.TestCase):
    def setUp(self):
        self.src = TPL.read_text(encoding="utf-8")
        start = self.src.index("rent_comps.override_subject")
        self.form = self.src[start - 400:start + 1600]

    def test_the_override_is_a_post_not_a_live_dropdown(self):
        self.assertIn('method="POST"', self.form)
        for live in ("onchange=", "fetch(", "XMLHttpRequest"):
            self.assertNotIn(live, self.form)

    def test_it_confirms_and_names_the_cost(self):
        self.assertIn("onsubmit=", self.form)
        self.assertIn("confirm(", self.form)
        self.assertIn("1 RentCast API call", self.form)
        self.assertIn("rentcast_quota.used", self.form)

    def test_it_is_disabled_at_cap(self):
        self.assertIn("rentcast_quota.at_cap", self.form)

    def test_the_route_refuses_at_cap_too(self):
        """A disabled button is a convenience, not a guarantee."""
        src = (ROOT / "tools" / "rent_comps.py").read_text(encoding="utf-8")
        route = src[src.index("def override_subject"):]
        route = route[:route.index("@rent_comps_bp.route", 10)]
        self.assertIn('rentcast_quota()["at_cap"]', route)
        self.assertIn("get_cached", route)


class TheDisclosureComposesTests(unittest.TestCase):
    """Once she overrides, the old sentence describes the wrong thing."""

    def setUp(self):
        self.src = TPL.read_text(encoding="utf-8")
        start = self.src.index("{% if override_beds is not none %}",
                               self.src.index("she asked for."))
        self.block = self.src[start:start + 1800]

    def test_it_says_the_estimate_answers_her_correction(self):
        self.assertIn("You asked for this estimate as", self.block)
        self.assertIn("not RentCast's own reading", self.block)

    def test_the_original_resolution_is_kept_as_history(self):
        self.assertIn("Left to itself it resolved this address to", self.block)
        self.assertIn("still on file", self.block)

    def test_the_automatic_sentence_became_the_elif(self):
        """It must not render above a corrected estimate."""
        self.assertIn("{% elif rentcast.property and rentcast.property.bedrooms is not none %}",
                      self.src)
        # Search only the rendered template, not the {# #} commentary --
        # the comment above this block quotes the old sentence verbatim,
        # so a raw index() finds the explanation rather than the markup.
        # Third instance of that collision this session.
        body = re.sub(r"\{#.*?#\}", " ", self.src, flags=re.S)
        auto = body.index("RentCast matched this address to")
        override = body.index("You asked for this estimate as")
        self.assertLess(override, auto, "the override arm comes first")


if __name__ == "__main__":
    unittest.main()

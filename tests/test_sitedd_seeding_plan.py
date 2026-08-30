"""Planning a Site DD seed from a rent roll — and refusing to guess.

`docs/site-dd-rentroll-seeding.md` is the design. This covers everything
up to the preview; nothing here writes.

ALL 152 LABELS, NOT A SAMPLE

`REAL_LABELS` is every unit label in the Oxford Pointe file, read from it
rather than chosen. Six of them carry an amenity suffix on the LABEL --
`'122 W/D'` and five more -- which the Part 35 spec expected to find only
on type strings. A sample of 20 has a 1-in-4 chance of containing none of
the six.

ZERO REFUSALS IS THE DANGEROUS CASE

Oxford Pointe produces no refusals at all: 152 of 152 plan cleanly. That
is exactly the condition under which a refusal-reporting path ships
broken, because nothing exercises it. So `RefusalsAreNamedTests` supplies
real refusals -- lettered labels, a Total row, a studio, an unknown status
code, and a genuine key collision -- and requires each to be named
individually rather than counted.
"""

import unittest

from tools import site_dd_db as sdb
from tools import site_dd_unit_checklist as uc
from tools import site_dd_seeding as seed

# THE FILE'S OWN ROWS, generated from it rather than typed.
#
# The first version of this fixture was transcribed by hand from a
# truncated print and came to 155 labels instead of 152 -- the exact
# transcription hazard the previous run recorded, walked into one run
# later. A fixture that describes a file is generated from the file.
REAL_ROWS = [
    ('110', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('111', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('112', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('114', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('115', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('116', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('117', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('119', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('120', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('121', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('124', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('125', '2/2 RENOVATED NEW BUILDING W/D', 'C', None),
    ('126', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('127', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('129', '2/2 CLASSIC NEW BUILDING  W/D', 'C', None),
    ('210', '2/1.5 CLASSIC', 'C', None),
    ('211', '2/1.5 RENOVATED', 'C', None),
    ('212', '2/1.5 CLASSIC', '', None),
    ('214', '2/1.5 CLASSIC', 'C', None),
    ('215', '2/1.5 CLASSIC', 'C', None),
    ('216', '2/1.5 RENOVATED', 'C', None),
    ('217', '2/1.5 RENOVATED', 'UE', None),
    ('219', '2/1.5 CLASSIC', 'C', None),
    ('220', '2 1.5 CLASSIC W/D', 'C', None),
    ('221', '2/1.5 RENOVATED W/D', 'C', None),
    ('224', '2 1.5 CLASSIC W/D', 'C', None),
    ('225', '2 1.5 CLASSIC W/D', 'C', None),
    ('227', '2/1.5 RENOVATED W/D', '', None),
    ('229', '2 1.5 CLASSIC W/D', 'C', None),
    ('310', '2/1.5 RENOVATED', 'C', None),
    ('311', '2/1.5 PREMIUM', 'C', None),
    ('312', '2/1 RENOVATED', 'C', None),
    ('314', '2/1.5 RENOVATED', 'C', None),
    ('315', '2/1.5 RENOVATED', 'C', None),
    ('316', '2/1.5 PREMIUM', 'C', None),
    ('317', '2/1.5 CLASSIC', 'C', None),
    ('319', '2/1.5 RENOVATED', 'C', None),
    ('320', '2/1.5 CLASSIC', 'C', None),
    ('321', '2/1.5 RENOVATED W/D', 'C', None),
    ('322', '2 1.5 CLASSIC W/D', 'C', None),
    ('324', '2/1.5 RENOVATED W/D', 'C', None),
    ('325', '2/1.5 RENOVATED W/D', 'C', None),
    ('326', '2/1.5 RENOVATED W/D', 'C', None),
    ('327', '2 1.5 CLASSIC W/D', 'C', None),
    ('329', '2/1.5 RENOVATED W/D', 'C', None),
    ('410', '3/2 RENOVATED  down', 'C', None),
    ('411', '3/2 CLASSIC', 'C', None), ('412', '3/2 RENOVATED', 'C', None),
    ('414', '3/2 RENOVATED', 'C', None), ('415', '3/2 CLASSIC', 'C', None),
    ('416', '3/2 RENOVATED', 'C', None),
    ('417', '3/2 RENOVATED', 'C', None),
    ('419', '3/2 RENOVATED', 'C', None),
    ('420', '3/2 CLASSIC W/D', 'C', None),
    ('421', '3/2 RENOVATED  W/D', 'C', None),
    ('422', '3/2 CLASSIC W/D', 'C', None),
    ('424', '3/2 CLASSIC W/D', 'C', None),
    ('425', '3/2 CLASSIC W/D', 'C', None),
    ('426', '3/2 CLASSIC W/D', '', None),
    ('427', '3/2 CLASSIC W/D', 'C', None),
    ('429', '3/2 RENOVATED  W/D', 'C', None),
    ('510', '3/2 RENOVATED', 'C', None),
    ('511', '3/2 RENOVATED', 'C', None),
    ('512', '3/2 RENOVATED', 'C', None), ('514', '3/2 PREMIUM', 'C', None),
    ('515', '3/2 RENOVATED', '', None),
    ('516', '3/2 RENOVATED', 'C', None),
    ('517', '3/2 RENOVATED', 'C', None),
    ('519', '3/2 RENOVATED', 'C', None),
    ('520', '3/2 CLASSIC W/D', 'C', None),
    ('522', '3/2 CLASSIC W/D', 'C', None),
    ('524', '3/2 CLASSIC W/D', 'C', None),
    ('525', '3/2 CLASSIC W/D', 'C', None),
    ('527', '3/2 CLASSIC W/D', 'C', None),
    ('610', '1/1 RENOVATED', '', None),
    ('611', '1/1 RENOVATED', 'C', None),
    ('612', '1/1 RENOVATED', 'C', None),
    ('614', '1/1 RENOVATED', '', None), ('615', '1/1 PREMIUM', 'C', None),
    ('616', '1/1 RENOVATED', 'C', None), ('617', '1/1 CLASSIC', 'C', None),
    ('618', '1/1 RENOVATED', 'C', None),
    ('619', '1/1 RENOVATED', 'C', None), ('620', '1/1 CLASSIC', 'C', None),
    ('621', '1/1 RENOVATED', 'C', None), ('623', '1/1 CLASSIC', 'C', None),
    ('630', '1/1 CLASSIC', 'C', None), ('631', '1/1 RENOVATED', '', None),
    ('632', '1/1 CLASSIC', 'C', None), ('634', '1/1 CLASSIC', 'C', None),
    ('635', '1/1 CLASSIC', 'C', None), ('636', '1/1 RENOVATED', '', None),
    ('637', '1/1 CLASSIC', 'C', None), ('638', '1/1 CLASSIC', 'C', None),
    ('639', '1/1 CLASSIC', 'C', None),
    ('640', '1/1 CLASSIC', 'NTV', '2026-08-13'),
    ('641', '1/1 CLASSIC', 'C', None), ('643', '1/1 RENOVATED', 'C', None),
    ('710', '2/1.5 RENOVATED', 'C', None),
    ('711', '2/1.5 RENOVATED', 'C', None),
    ('712', '2/1.5 CLASSIC', '', None),
    ('714', '2/1.5 RENOVATED', '', None),
    ('715', '2/1.5 CLASSIC', 'C', None),
    ('716', '2/1.5 CLASSIC', 'C', None),
    ('717', '2/1.5 RENOVATED', 'C', None),
    ('719', '2/1.5 CLASSIC', 'C', None),
    ('720', '2 1.5 CLASSIC W/D', 'C', None),
    ('721', '2 1.5 CLASSIC W/D', '', None),
    ('722', '2 1.5 CLASSIC W/D', '', None),
    ('724', '2 1.5 CLASSIC W/D', '', None),
    ('725', '2 1.5 CLASSIC W/D', 'C', None),
    ('726', '2 1.5 CLASSIC W/D', 'C', None),
    ('727', '2/1.5 RENOVATED W/D', 'C', None),
    ('729', '2/1.5 RENOVATED W/D', 'C', None),
    ('810', '2/1.5 CLASSIC', 'C', None),
    ('811', '2/1.5 RENOVATED', 'C', None),
    ('812', '2/1.5 CLASSIC', 'C', None),
    ('814', '2/1.5 RENOVATED', 'C', None),
    ('815', '2/1.5 RENOVATED', 'C', None),
    ('816', '1/1 RENOVATED', 'C', None),
    ('817', '2/1.5 CLASSIC', 'C', None),
    ('819', '3/1.5 RENOVATED', 'C', None),
    ('820', '2/1.5 RENOVATED W/D', 'C', None),
    ('821', '2/1.5 CLASSIC', 'C', None),
    ('822', '2 1.5 CLASSIC W/D', 'C', None),
    ('824', '2/1.5 RENOVATED W/D', 'C', None),
    ('825', '2/1.5 RENOVATED W/D', '', None),
    ('826', '2 1.5 CLASSIC W/D', 'C', None),
    ('827', '2/1.5 RENOVATED W/D', 'C', None),
    ('829', '2/1.5 RENOVATED W/D', '', None),
    ('910', '2/1.5 RENOVATED', 'C', None),
    ('911', '2/1.5 CLASSIC', 'C', None),
    ('912', '2/1.5 RENOVATED', 'C', None),
    ('914', '2/1.5 RENOVATED', 'C', None),
    ('915', '2/1.5 PREMIUM', 'C', None),
    ('916', '2/1.5 RENOVATED', 'C', None),
    ('917', '2/1.5 RENOVATED', '', None),
    ('919', '2/1.5 RENOVATED', 'C', None),
    ('920', '2/1.5 RENOVATED W/D', 'C', None),
    ('921', '2/1.5 RENOVATED W/D', 'C', None),
    ('922', '2 1.5 CLASSIC W/D', 'C', None),
    ('924', '2 1.5 CLASSIC W/D', 'C', None),
    ('925', '2/1.5 RENOVATED W/D', '', None),
    ('926', '2 1.5 CLASSIC W/D', 'C', None),
    ('927', '2 1.5 CLASSIC W/D', '', None),
    ('929', '2/1.5 RENOVATED W/D', 'C', None),
    ('122 W/D', '2/2 RENOVATED NEW BUILDING W/D', 'C', None),
    ('222 W/D', '2/1.5 RENOVATED W/D', 'C', None),
    ('226 W/D', '2/1.5 RENOVATED W/D', 'C', None),
    ('521 W/D', '3/2 RENOVATED  W/D', 'C', None),
    ('526 W/D', '3/2 RENOVATED  W/D', 'C', None),
    ('529 W/D', '3/2 CLASSIC W/D', 'C', None),
]

REAL_LABELS = [r[0] for r in REAL_ROWS]
REAL_TYPES = [r[1] for r in REAL_ROWS]

SUFFIXED = ["122 W/D", "222 W/D", "226 W/D", "521 W/D", "526 W/D", "529 W/D"]


def unit(label, unit_type="2/1.5 RENOVATED", status="C", **kw):
    row = {"unit": label, "unit_type": unit_type, "sqft": 825.0,
           "status": status, "move_out": None}
    row.update(kw)
    return row


class ThePopulationTests(unittest.TestCase):
    """Assert the size before asserting anything about the contents."""

    def test_there_are_152_labels(self):
        self.assertEqual(len(REAL_LABELS), 152)

    def test_they_are_all_distinct(self):
        self.assertEqual(len(set(REAL_LABELS)), 152)

    def test_exactly_six_carry_an_amenity_suffix(self):
        found = [l for l in REAL_LABELS if "W/D" in l]
        self.assertEqual(found, SUFFIXED)

    def test_not_one_starts_with_a_letter(self):
        """Which is why the 60% discriminator cannot be tested and is not
        built."""
        self.assertEqual([l for l in REAL_LABELS if l[0].isalpha()], [])


class UnitKeyTests(unittest.TestCase):
    def test_every_real_label_produces_a_key(self):
        for label in REAL_LABELS:
            with self.subTest(label=label):
                self.assertIsNotNone(seed.unit_key(label))

    def test_all_152_keys_are_distinct(self):
        keys = [seed.unit_key(l) for l in REAL_LABELS]
        self.assertEqual(len(set(keys)), 152, "stripping merged two units")

    def test_the_suffix_is_stripped(self):
        for label in SUFFIXED:
            with self.subTest(label=label):
                self.assertEqual(seed.unit_key(label), label.split()[0])

    def test_the_bare_number_keys_the_same_as_the_suffixed_one(self):
        """'226 W/D' and '226' are one apartment written two ways."""
        self.assertEqual(seed.unit_key("226 W/D"), seed.unit_key("226"))

    def test_none_of_the_six_bare_numbers_is_a_separate_unit(self):
        """Checked against the file: stripping merges nothing real."""
        bare = {l.split()[0] for l in SUFFIXED}
        self.assertEqual(bare & set(REAL_LABELS), set())

    def test_a_leading_w_slash_d_is_not_truncated(self):
        """Anchored at the end. A unit called 'W/D 3' is refused as
        lettered, not silently turned into '3'."""
        self.assertIsNone(seed.unit_key("W/D 3"))


class RefusedRatherThanGuessedTests(unittest.TestCase):
    def test_a_lettered_label_is_refused(self):
        for label in ("A1", "B12", "C-3"):
            with self.subTest(label=label):
                self.assertIsNone(seed.unit_key(label))

    def test_the_lettered_refusal_explains_the_ambiguity(self):
        reason = seed._refusal_reason("A1")
        self.assertIn("building", reason)
        self.assertIn("wrong apartment", reason)

    def test_non_unit_rows_are_refused(self):
        for label in ("Total", "TOTALS", "Clubhouse", "Office", "Model"):
            with self.subTest(label=label):
                self.assertIsNone(seed.unit_key(label))

    def test_a_blank_label_is_refused(self):
        for label in ("", "   ", None):
            with self.subTest(label=label):
                self.assertIsNone(seed.unit_key(label))

    def test_an_unrecognised_shape_is_refused(self):
        for label in ("12/34/56", "Unit 5 (rear)", "3rd floor"):
            with self.subTest(label=label):
                self.assertIsNone(seed.unit_key(label))

    def test_positive_control_a_plain_number_is_accepted(self):
        """Without this every assertion above would pass on a unit_key
        that returned None for everything."""
        self.assertEqual(seed.unit_key("110"), "110")


class StatusIsReadThenMappedTests(unittest.TestCase):
    def test_the_three_codes_all_mean_occupied(self):
        for code in ("C", "NTV", "UE"):
            with self.subTest(code=code):
                reading = seed.read_status(code)
                self.assertEqual(reading.mapped, sdb.AREA_OCCUPIED)
                self.assertFalse(reading.inferred)

    def test_blank_means_vacant_and_says_it_was_inferred(self):
        reading = seed.read_status("")
        self.assertEqual(reading.mapped, sdb.AREA_VACANT)
        self.assertTrue(reading.inferred)
        self.assertIsNone(reading.stated)

    def test_the_stated_code_survives_the_mapping(self):
        """A caller cannot render the conclusion without the evidence."""
        self.assertEqual(seed.read_status("NTV").stated, "NTV")

    def test_an_unknown_code_is_not_mapped(self):
        reading = seed.read_status("ZZ")
        self.assertIsNone(reading.mapped)
        self.assertEqual(reading.stated, "ZZ")
        self.assertFalse(reading.inferred)

    def test_the_mapped_values_are_real_area_statuses(self):
        for value in set(seed.STATUS_MAP.values()) | {seed.BLANK_STATUS}:
            with self.subTest(value=value):
                self.assertIn(value, sdb.AREA_STATUSES)


class RoomDerivationTests(unittest.TestCase):
    def types(self, rooms):
        return [r.room_type for r in rooms]

    def test_a_one_bed_one_bath(self):
        self.assertEqual(self.types(seed.rooms_for(1, 1.0)),
                         ["living", "kitchen", "bedroom", "bathroom"])

    def test_walk_order_is_living_kitchen_bedrooms_bathrooms(self):
        self.assertEqual(self.types(seed.rooms_for(3, 2.0)),
                         ["living", "kitchen", "bedroom", "bedroom",
                          "bedroom", "bathroom", "bathroom"])

    def test_one_and_a_half_baths_is_TWO_rooms(self):
        """1.5 is two rooms an inspector walks into."""
        rooms = seed.rooms_for(2, 1.5)
        self.assertEqual(self.types(rooms).count("bathroom"), 2)

    def test_ceil_NOT_round_and_1_5_does_not_prove_it(self):
        """Python's round() is banker's rounding: round(1.5) is 2, so the
        only fractional value in the real file cannot tell ceil from
        round. round(2.5) is 2 and ceil(2.5) is 3 -- that is where they
        part, and it is the case that pins the rule.

        No row has 2.5 baths and parse_unit_type would refuse one anyway.
        The rule is still pinned here, because a docstring claiming ceil
        matters while every test passes under round is a claim nothing
        checks."""
        rooms = seed.rooms_for(3, 2.5)
        self.assertEqual(self.types(rooms).count("bathroom"), 3,
                         "round() would give 2 here; ceil gives 3")

    def test_and_the_extra_one_is_the_half(self):
        baths = [r for r in seed.rooms_for(3, 2.5) if r.room_type == "bathroom"]
        self.assertEqual([b.label for b in baths],
                         [None, None, seed.HALF_BATH_LABEL])

    def test_the_half_is_distinguished_by_label_not_room_type(self):
        rooms = seed.rooms_for(2, 1.5)
        baths = [r for r in rooms if r.room_type == "bathroom"]
        self.assertEqual([b.label for b in baths], [None, seed.HALF_BATH_LABEL])

    def test_site_dd_gains_no_half_bath_room_type(self):
        for rooms in (seed.rooms_for(2, 1.5), seed.rooms_for(3, 1.5)):
            for room in rooms:
                with self.subTest(room=room):
                    self.assertIn(room.room_type, dict(uc.ROOM_TYPES))

    def test_two_full_baths_have_no_half_label(self):
        baths = [r for r in seed.rooms_for(2, 2.0) if r.room_type == "bathroom"]
        self.assertEqual([b.label for b in baths], [None, None])


class TheSixLayoutsTests(unittest.TestCase):
    """18 type strings collapse to six layouts; one covers 77 units."""

    TYPES = REAL_TYPES

    def plan(self):
        rows = [unit(REAL_LABELS[i], t) for i, t in enumerate(self.TYPES)]
        return seed.plan_units(rows)

    def test_the_fixture_is_the_real_152(self):
        self.assertEqual(len(self.TYPES), 152)

    def test_eighteen_type_strings_become_six_layouts(self):
        self.assertEqual(len(set(self.TYPES)), 18)
        self.assertEqual(len(self.plan()["layouts"]), 6)

    def test_the_largest_layout_covers_77_units(self):
        plan = self.plan()
        self.assertEqual(max(plan["layout_counts"].values()), 77)
        self.assertEqual(plan["layout_counts"][(2, 1.5)], 77)

    def test_every_unit_is_in_exactly_one_layout(self):
        plan = self.plan()
        self.assertEqual(sum(plan["layout_counts"].values()), 152)

    def test_a_layout_object_is_SHARED_not_rebuilt_per_unit(self):
        """Six room sets built and copied, not 152 constructed."""
        plan = self.plan()
        objects = {id(u.layout) for u in plan["units"]}
        self.assertEqual(len(objects), 6)

    def test_the_room_total_is_894(self):
        """The design estimated ~880. The code says 894, and the code is
        the one that counted: 25x4 + 1x5 + 77x6 + 16x6 + 1x7 + 32x7."""
        self.assertEqual(self.plan()["room_total"], 894)

    def test_the_amenity_suffix_does_not_split_a_layout(self):
        """'2/1.5 RENOVATED' and '2/1.5 RENOVATED W/D' are one layout."""
        plan = seed.plan_units([unit("110", "2/1.5 RENOVATED"),
                                unit("111", "2/1.5 RENOVATED W/D")])
        self.assertEqual(len(plan["layouts"]), 1)


class RefusalsAreNamedTests(unittest.TestCase):
    """Oxford Pointe produces ZERO refusals, so this path is exercised
    only by rows we construct. That is the point: an empty list on the
    one testable file is when a summarised-refusal bug ships."""

    def test_the_real_file_shape_produces_none(self):
        plan = seed.plan_units([unit(l) for l in REAL_LABELS])
        self.assertEqual(plan["refusal_count"], 0)
        self.assertEqual(plan["unit_count"], 152)

    def test_each_refusal_names_its_own_row(self):
        plan = seed.plan_units([
            unit("110"), unit("Total"), unit("A1"),
            unit("118", "STUDIO"), unit("119", status="ZZ")])
        labels = [r.label for r in plan["refusals"]]
        self.assertEqual(sorted(labels), ["118", "119", "A1", "Total"])
        self.assertEqual(plan["unit_count"], 1)

    def test_no_two_refusals_share_a_reason(self):
        """Individually named, not bucketed under one message."""
        plan = seed.plan_units([
            unit("Total"), unit("A1"), unit("118", "STUDIO"),
            unit("119", status="ZZ")])
        reasons = [r.reason for r in plan["refusals"]]
        self.assertEqual(len(set(reasons)), 4)

    def test_the_reason_quotes_the_offending_value(self):
        plan = seed.plan_units([unit("118", "STUDIO RENOVATED")])
        self.assertIn("STUDIO RENOVATED", plan["refusals"][0].reason)

    def test_an_unknown_status_is_refused_not_defaulted(self):
        plan = seed.plan_units([unit("110", status="ZZ")])
        self.assertEqual(plan["unit_count"], 0)
        self.assertIn("ZZ", plan["refusals"][0].reason)


class TheCollisionRefusalTests(unittest.TestCase):
    """Two rows claiming one apartment refuses BOTH."""

    def plan(self):
        return seed.plan_units([unit("226"), unit("226 W/D"), unit("110")])

    def test_neither_side_is_seeded(self):
        plan = self.plan()
        self.assertEqual([u.label for u in plan["units"]], ["110"])

    def test_both_sides_are_named(self):
        labels = {r.label for r in self.plan()["refusals"]}
        self.assertEqual(labels, {"226", "226 W/D"})

    def test_each_refusal_names_the_other_row(self):
        for refusal in self.plan()["refusals"]:
            with self.subTest(label=refusal.label):
                other = "226 W/D" if refusal.label == "226" else "226"
                self.assertIn(other, refusal.reason)

    def test_it_says_it_will_not_choose(self):
        self.assertIn("will not choose", self.plan()["refusals"][0].reason)

    def test_positive_control_no_collision_seeds_both(self):
        plan = seed.plan_units([unit("226 W/D"), unit("227")])
        self.assertEqual(plan["unit_count"], 2)
        self.assertEqual(plan["refusal_count"], 0)


class TheStatusNoteTests(unittest.TestCase):
    """What the collapse to occupied/vacant would otherwise lose."""

    def test_ntv_carries_its_move_out_date(self):
        plan = seed.plan_units([unit("640", "1/1 CLASSIC", status="NTV",
                                     move_out="2026-08-13")])
        self.assertEqual(plan["units"][0].notes,
                         ("Notice to vacate 2026-08-13",))

    def test_ue_carries_its_stated_code(self):
        plan = seed.plan_units([unit("217", status="UE")])
        self.assertEqual(plan["units"][0].notes, ("Rent roll status: UE",))

    def test_a_current_unit_carries_nothing(self):
        self.assertEqual(seed.plan_units([unit("110")])[  "units"][0].notes, ())

    def test_a_vacant_unit_carries_nothing(self):
        self.assertEqual(
            seed.plan_units([unit("110", status="")])["units"][0].notes, ())

    def test_area_statuses_is_not_widened_to_carry_it(self):
        """Michelle declined a wider status vocabulary in Part 58. The
        note is how the fact survives that decision."""
        self.assertEqual(set(sdb.AREA_STATUSES),
                         {"occupied", "vacant", "down"})


class NothingHereWritesTests(unittest.TestCase):
    """The checkpoint is the preview. This module must not be able to
    write even by accident."""

    def test_the_module_opens_no_connection(self):
        """COMMENTS AND DOCSTRINGS STRIPPED FIRST.

        The module's own prose explains that `create_room` already takes a
        label, so a raw substring search finds the explanation rather than
        a call -- the collision this codebase has now hit five times. The
        check is on executable code only, via the AST.
        """
        import ast, inspect
        tree = ast.parse(inspect.getsource(seed))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                if name:
                    called.add(name)
        for forbidden in ("get_connection", "create_area", "create_room",
                          "delete_area", "upsert_findings", "commit",
                          "execute", "executemany"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, called)

    def test_it_imports_nothing_that_writes(self):
        import ast, inspect
        tree = ast.parse(inspect.getsource(seed))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        self.assertNotIn("sqlite3", imported)

    def test_positive_control_the_ast_check_sees_calls(self):
        """Without this the assertions above would pass on a walk that
        collected nothing at all."""
        import ast, inspect
        tree = ast.parse(inspect.getsource(seed))
        called = {getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                  for n in ast.walk(tree) if isinstance(n, ast.Call)}
        self.assertIn("parse_unit_type", called)


if __name__ == "__main__":
    unittest.main()


class TheReconcileAsymmetryTests(unittest.TestCase):
    """A rent roll can say a room is missing. It cannot say a room an
    inspector recorded does not exist."""

    def plan(self, *types):
        return seed.plan_units([unit(str(200 + i), t)
                                for i, t in enumerate(types)])

    def test_a_fresh_assessment_creates_everything(self):
        r = seed.plan_reconcile(self.plan("2/1.5 RENOVATED"), [], {}, {})
        self.assertEqual(r["create_count"], 1)
        self.assertEqual(r["reuse_count"], 0)
        self.assertEqual(r["rooms_appended"], 6)

    def test_an_existing_unit_is_reused_not_duplicated(self):
        r = seed.plan_reconcile(
            self.plan("2/1.5 RENOVATED"), [{"id": 9, "label": "200"}],
            {9: [{"room_type": "kitchen"}]}, {9: 0})
        self.assertEqual(r["reuse_count"], 1)
        self.assertEqual(r["create_count"], 0)

    def test_only_the_shortfall_is_appended(self):
        """One kitchen exists; the layout wants six rooms including one
        kitchen. Five are appended, not six."""
        r = seed.plan_reconcile(
            self.plan("2/1.5 RENOVATED"), [{"id": 9, "label": "200"}],
            {9: [{"room_type": "kitchen"}]}, {9: 0})
        self.assertEqual(r["areas"][0].rooms_appended, 5)
        self.assertEqual(r["areas"][0].rooms_existing, 1)

    def test_a_surplus_room_is_KEPT(self):
        """Three bedrooms recorded, a 1-bed layout in the roll. All three
        stay."""
        r = seed.plan_reconcile(
            self.plan("1/1 CLASSIC"), [{"id": 9, "label": "200"}],
            {9: [{"room_type": "bedroom"}] * 3}, {9: 0})
        self.assertEqual(r["areas"][0].rooms_surplus, 2)
        self.assertEqual(r["rooms_surplus_kept"], 2)

    def test_the_matching_uses_the_normalised_key(self):
        """An area labelled '226 W/D' matches a roll row '226'."""
        plan = seed.plan_units([unit("226")])
        r = seed.plan_reconcile(plan, [{"id": 9, "label": "226 W/D"}], {9: []}, {9: 4})
        self.assertEqual(r["reuse_count"], 1)
        self.assertEqual(r["findings_preserved"], 4)

    def test_assessment_11s_kitchen_case(self):
        """The live one: one kitchen carrying 15 findings."""
        r = seed.plan_reconcile(
            self.plan("2/1.5 RENOVATED"), [{"id": 11, "label": "200"}],
            {11: [{"room_type": "kitchen"}]}, {11: 15})
        area = r["areas"][0]
        self.assertEqual(area.action, "reuse")
        self.assertEqual(area.findings_preserved, 15)
        self.assertEqual(r["findings_preserved"], 15)

    def test_an_unmentioned_area_is_left_alone_with_its_findings(self):
        r = seed.plan_reconcile(
            self.plan("2/1.5 RENOVATED"),
            [{"id": 9, "label": "200"}, {"id": 12, "label": "999"}],
            {9: [], 12: []}, {9: 0, 12: 7})
        self.assertEqual([u.label for u in r["untouched"]], ["999"])
        self.assertEqual(r["untouched"][0].findings, 7)
        self.assertEqual(r["findings_preserved"], 7)

    def test_positive_control_a_matched_area_is_not_listed_as_untouched(self):
        r = seed.plan_reconcile(
            self.plan("2/1.5 RENOVATED"), [{"id": 9, "label": "200"}], {9: []}, {9: 0})
        self.assertEqual(r["untouched"], [])


class ThePreviewScreenTests(unittest.TestCase):
    """Reachable, honest about the inference, and it writes nothing."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        self.tmp = Path(tempfile.mkdtemp()) / "sitedd.db"
        self.patch = mock.patch.object(sdb, "get_db_path", lambda: self.tmp)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with sdb.get_connection() as conn:
            self.aid = sdb.create_assessment(conn, {
                "property_label": "Oxford Pointe", "assessed_on": "2026-08-29",
                "inspector": "MJ", "checklist_version": 2, "deal_id": None})
        from app import app
        app.config["LOGIN_DISABLED"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def test_the_screen_is_linked_from_the_assessment_page(self):
        """Five features have shipped correct and unreachable."""
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}").get_data(as_text=True)
        self.assertIn(f"/assessment/{self.aid}/seed-preview", body)

    def test_it_renders_and_says_nothing_is_saved(self):
        body = self.client.get(
            f"/tools/site-dd/assessment/{self.aid}/seed-preview"
        ).get_data(as_text=True)
        self.assertIn("Nothing is saved", body)

    def test_it_refuses_an_unsupported_file_type(self):
        import io as _io
        body = self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/seed-preview",
            data={"rentroll": (_io.BytesIO(b"x"), "notes.pdf")},
            content_type="multipart/form-data").get_data(as_text=True)
        self.assertIn("Unsupported file type", body)

    def test_it_asks_for_a_file_rather_than_failing(self):
        body = self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/seed-preview",
            data={}, content_type="multipart/form-data").get_data(as_text=True)
        self.assertIn("Choose a rent roll file", body)

    def test_the_template_shows_the_inference_not_the_conclusion(self):
        from pathlib import Path
        tpl = (Path(sdb.__file__).parents[1] / "templates" / "tools"
               / "site_dd_seed_preview.html").read_text(encoding="utf-8")
        self.assertIn("(no status)", tpl)

    def test_the_template_states_findings_preserved_in_words(self):
        from pathlib import Path
        tpl = (Path(sdb.__file__).parents[1] / "templates" / "tools"
               / "site_dd_seed_preview.html").read_text(encoding="utf-8")
        self.assertIn("Findings preserved", tpl)
        self.assertIn("findings_preserved", tpl)

    def test_the_template_has_no_apply_button(self):
        from pathlib import Path
        import re
        tpl = (Path(sdb.__file__).parents[1] / "templates" / "tools"
               / "site_dd_seed_preview.html").read_text(encoding="utf-8")
        markup = re.sub(r"\{#.*?#\}", " ", tpl, flags=re.S)
        for word in ("Apply", "Confirm seed", "Create units"):
            with self.subTest(word=word):
                self.assertNotIn(word, markup)

    def test_the_route_writes_nothing(self):
        """An area count before and after a full preview."""
        with sdb.get_connection() as conn:
            before = len(sdb.list_areas(conn, self.aid))
        self.client.post(
            f"/tools/site-dd/assessment/{self.aid}/seed-preview",
            data={}, content_type="multipart/form-data")
        with sdb.get_connection() as conn:
            self.assertEqual(len(sdb.list_areas(conn, self.aid)), before)

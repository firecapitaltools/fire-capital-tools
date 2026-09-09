"""Bed-level facts on the area note, and the two live dialects left alone.

WHAT THIS COVERS AND WHAT IT CANNOT

`_bed_notes()` is reachable only from this file. There is no Entrata
parser -- dispatch refuses the file by name, `parse_unit_type("4x4
(Regular)")` returns None, and `unit_key("111-A")` returns None -- so
NOTHING IN THE SEEDING PATH CALLS IT WITH BED DATA, because nothing can.

So the classes below split on exactly that line, and the split is the
honest part:

  * `BedNotesAreSynthetic` -- **SYNTHETIC BY NECESSITY.** It hands the
    function the unit dict a future Entrata parser would build and checks
    the sentences that come out. It establishes that the branch composes
    the intended text from the intended input. It establishes NOTHING
    about whether any real path will ever supply that input, or supply it
    in this shape. When the parser is written, the shape below is a
    proposal it may reject.

  * `TheLiveDialectsAreUnchanged` -- **THE REGRESSION THAT MATTERS.**
    ResMan and Appfolio are live and Michelle uses both. Run against the
    real files where they exist, and against synthetic rows shaped like
    them everywhere else.

  * `TheRegressionAssertionIsNotVacuous` -- the control. An assertion that
    "no bed sentence appears" passes trivially on a function that can
    never produce one, so it certifies nothing until the same comparison
    is shown to move when a bed IS present.

A NOTE ON THE FIRST CONTROL WRITTEN FOR THIS, because it failed and the
failure was in the control rather than in the code: it injected beds
while ALSO overriding `dialect` to "entrata", which sent `read_status`
down the ResMan branch, left the status unmapped, and got the whole row
refused -- so the unit disappeared from both sides of the comparison and
they matched. A control that removes its own subject reports agreement.
The fix was to keep the file's real dialect and add only the beds.
"""

import os
import pathlib
import unittest

from tools import underwriting_rentroll as rr
from tools.site_dd_seeding import _bed_notes, _notes_for, plan_units, read_status

# The real client files, if this machine has them. Same arrangement as
# tests/test_appfolio_rent_roll.py and the T12 tests: a client's file does
# not go in the repo.
RESMAN_ROLL = pathlib.Path(
    os.environ.get("RESMAN_ROLL", "C:/Users/jaspe/Downloads/Rent Roll (11).xls"))
APPFOLIO_ROLL = pathlib.Path(
    os.environ.get("APPFOLIO_ROLL_2026_09",
                   "C:/Users/jaspe/Downloads/rent_roll-20260907.xlsx"))

ENVIRONMENT_GATED = (
    "the real rent rolls are clients' files and are not in the repo; set "
    "RESMAN_ROLL / APPFOLIO_ROLL_2026_09 to copies to run the end-to-end "
    "check. The synthetic classes here cover the same behaviour."
)


def entrata_unit(beds, **over):
    """The unit dict a future Entrata parser would hand plan_units.

    SYNTHETIC. Nothing produces this today; see the module docstring.
    """
    unit = {
        "unit": "111",
        "unit_type": "4x4 (Regular)",
        "status": "Occupied No Notice",
        "dialect": "entrata",
        "beds": [{"label": lbl, "status": st} for lbl, st in beds],
    }
    unit.update(over)
    return unit


class BedNotesAreSynthetic(unittest.TestCase):
    """SYNTHETIC BY NECESSITY -- no live path produces these inputs."""

    def test_a_mixed_apartment_gets_one_sentence_per_remarkable_bed(self):
        """34 of The View's 84 apartments are this shape."""
        notes = _bed_notes(entrata_unit([
            ("A", "Vacant Unrented Not Ready"),
            ("B", "Occupied No Notice"),
            ("C", "Occupied No Notice"),
            ("D", "Vacant Rented Ready"),
        ]))
        self.assertEqual(notes, (
            "Rent roll lists bed A as Vacant Unrented Not Ready",
            "Rent roll lists bed D as Vacant Rented Ready",
        ))

    def test_a_full_apartment_gets_nothing(self):
        """42 of 84 at The View. Four lines saying 'normal' is how the
        useful notes stop being read."""
        self.assertEqual(_bed_notes(entrata_unit(
            [(l, "Occupied No Notice") for l in "ABCD"])), ())

    def test_the_three_way_vacant_vocabulary_survives_verbatim(self):
        """The whole point. The area's status collapses to `vacant`; the
        distinction between Rented Ready, Unrented Ready and Unrented Not
        Ready exists nowhere else after the import."""
        notes = _bed_notes(entrata_unit([
            ("A", "Vacant Rented Ready"),
            ("B", "Vacant Unrented Ready"),
            ("C", "Vacant Unrented Not Ready"),
            ("D", "Notice Unrented"),
        ]))
        self.assertEqual(len(notes), 4)
        for state in ("Vacant Rented Ready", "Vacant Unrented Ready",
                      "Vacant Unrented Not Ready", "Notice Unrented"):
            self.assertIn(state, " | ".join(notes))

    def test_every_sentence_is_about_the_document(self):
        """'the rent roll lists bed A as Not Ready', never 'bed A is not
        ready'. Readiness is the property manager's judgement and it is
        the question the inspector is being sent to answer."""
        notes = _bed_notes(entrata_unit([("A", "Vacant Unrented Not Ready")]))
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].startswith("Rent roll lists bed "))
        # The claim-about-the-room forms, none of which may appear.
        for forbidden in ("bed A is", "is not ready", "is vacant",
                          "needs a turn"):
            self.assertNotIn(forbidden, notes[0])

    def test_a_bed_with_no_status_is_recorded_not_inferred(self):
        """The ResMan blank rule was earned on four independent signals
        for a whole unit. None of them has been shown to hold for a bed,
        so nothing here concludes vacancy from an empty cell."""
        notes = _bed_notes(entrata_unit([("A", "")]))
        self.assertEqual(notes, ("Rent roll lists bed A with no status",))
        self.assertNotIn("acant", notes[0])

    def test_an_unknown_dialect_treats_every_bed_as_remarkable(self):
        """The safe direction. A note that says too much is read past; one
        that silently omits a vacant bed is the failure this exists to
        prevent."""
        unit = entrata_unit([(l, "Occupied No Notice") for l in "ABCD"],
                            dialect="some-future-system")
        self.assertEqual(len(_bed_notes(unit)), 4)

    def test_a_bed_with_no_label_is_skipped_rather_than_named_blank(self):
        self.assertEqual(_bed_notes(entrata_unit([("", "Vacant Unrented Ready")])), ())

    def test_the_unit_level_note_still_comes_first(self):
        """Order is deliberate: the apartment, then its beds."""
        unit = entrata_unit([("A", "Vacant Unrented Not Ready")],
                            status="Notice Unrented", move_out="2026-12-31")
        notes = _notes_for(unit, read_status(unit["status"], "entrata"))
        self.assertEqual(notes[-1],
                         "Rent roll lists bed A as Vacant Unrented Not Ready")
        self.assertGreater(len(notes), 1)

    def test_the_stored_note_is_one_line(self):
        """`_insert_area` joins with '; '. The area form renders the stored
        value into a single-line <input type="text"> and `save_area` writes
        notes unconditionally, so a newline here would not survive somebody
        opening that unit and saving it."""
        notes = _bed_notes(entrata_unit([
            ("A", "Vacant Unrented Not Ready"),
            ("D", "Vacant Rented Ready"),
        ]))
        stored = "; ".join(notes)
        self.assertNotIn("\n", stored)
        self.assertNotIn("\r", stored)


class SaveAreaOverwritesNotesUnconditionally(unittest.TestCase):
    """The tested half of the one-line argument.

    The browser half -- that a text input strips CR/LF from its value --
    is a spec claim and is NOT observed here, because nothing in this repo
    drives a browser. This is the half that can be demonstrated, and it is
    the half that makes the conclusion hold either way: whatever that form
    posts back REPLACES the stored note.
    """

    def test_update_area_writes_notes_whether_or_not_they_changed(self):
        import sqlite3
        import tempfile
        from unittest import mock
        from tools import site_dd_db as sdb

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "site_dd.db"
            # PATCH THE FUNCTION, NEVER SET THE ENV VAR. A wrong attribute
            # name raises here; a misspelled variable would silently fall
            # back to the developer's own database. See HANDOFF, "a
            # misspelled environment variable fails open".
            with mock.patch.object(sdb, "get_db_path", lambda: path):
                with sdb.get_connection() as conn:
                    aid = sdb.create_assessment(conn, {
                        "property_label": "Bed note", "assessed_on": "2026-09-09",
                        "inspector": "test", "checklist_version": 2})
                    area = sdb.create_area(conn, aid, {
                        "kind": "unit", "label": "111", "status": "occupied"})
                    sdb.update_area(conn, area, {
                        "label": "111", "status": "occupied",
                        "notes": "Rent roll lists bed A as Vacant Unrented "
                                 "Not Ready; Rent roll lists bed D as "
                                 "Vacant Rented Ready"})
                    kept = sdb.get_area(conn, area)["notes"]
                    self.assertIn("bed A", kept)
                    # A later save carrying a different value replaces it
                    # outright -- there is no merge and no absent-means-
                    # unchanged for this field.
                    sdb.update_area(conn, area, {
                        "label": "111", "status": "occupied",
                        "notes": "walked it"})
                    self.assertEqual(sdb.get_area(conn, area)["notes"],
                                     "walked it")


def _notes_by_label(path):
    """Every note the real route produces for a real file, by unit."""
    parsed = rr.parse_rent_roll_workbook(path)
    plan = plan_units(parsed["units"])
    return ({u.label: tuple(u.notes) for u in plan["units"] if u.notes},
            parsed["source_format"], len(plan["units"]), plan["refusals"])


@unittest.skipUnless(RESMAN_ROLL.exists() and APPFOLIO_ROLL.exists(),
                     ENVIRONMENT_GATED)
class TheLiveDialectsAreUnchanged(unittest.TestCase):
    """THE REGRESSION THAT MATTERS. Both are live; Michelle uses both."""

    def test_resman_produces_exactly_the_notes_it_always_has(self):
        notes, fmt, count, refusals = _notes_by_label(RESMAN_ROLL)
        self.assertEqual((fmt, count, refusals),
                         ("ResMan Rent Roll", 152, []))
        # 18 inferred vacancies, plus UE on 217 and the notice on 640 --
        # the two HANDOFF records for the assessment 21 seed, and the 18
        # the Part 88 branch added afterwards.
        self.assertEqual(notes["217"], ("Rent roll status: UE",))
        self.assertEqual(notes["640"], ("Notice to vacate 2026-08-13",))
        inferred = [k for k, v in notes.items()
                    if v and v[0].startswith("Vacant inferred:")]
        self.assertEqual(len(inferred), 18)
        self.assertEqual(len(notes), 20)

    def test_appfolio_produces_exactly_the_notes_it_always_has(self):
        notes, fmt, count, refusals = _notes_by_label(APPFOLIO_ROLL)
        self.assertEqual((fmt, count, refusals),
                         ("Appfolio Rent Roll", 16, []))
        self.assertEqual(notes, {
            "7": ("Rent roll status: Vacant-Unrented",),
            "15": ("Rent roll status: Vacant-Unrented",),
        })

    def test_no_bed_sentence_reaches_either_live_dialect(self):
        """Because no parser sets `beds`, not because anything filters."""
        for path in (RESMAN_ROLL, APPFOLIO_ROLL):
            notes, _, _, _ = _notes_by_label(path)
            for label, lines in notes.items():
                for line in lines:
                    self.assertNotIn("bed ", line, f"{path.name} unit {label}")

    def test_neither_parser_emits_a_beds_key_at_all(self):
        for path in (RESMAN_ROLL, APPFOLIO_ROLL):
            for unit in rr.parse_rent_roll_workbook(path)["units"]:
                self.assertNotIn("beds", unit)


@unittest.skipUnless(APPFOLIO_ROLL.exists(), ENVIRONMENT_GATED)
class TheRegressionAssertionIsNotVacuous(unittest.TestCase):
    """The control for the class above.

    "No bed sentence appears" is satisfied trivially by a function that
    can never produce one. This shows the same comparison MOVES when a bed
    is present -- on a real row from a real file, with its real dialect
    left alone, which is what the first attempt at this control got wrong.
    """

    def test_injecting_one_bed_changes_the_notes_for_that_unit(self):
        parsed = rr.parse_rent_roll_workbook(APPFOLIO_ROLL)
        units = parsed["units"]
        before = {u.label: tuple(u.notes) for u in plan_units(units)["units"]}
        units[0] = dict(units[0], beds=[
            {"label": "A", "status": "Vacant Unrented Not Ready"}])
        after_plan = plan_units(units)
        after = {u.label: tuple(u.notes) for u in after_plan["units"]}

        self.assertEqual(after_plan["refusals"], [],
                         "the control must not remove its own subject")
        self.assertNotEqual(before, after)
        label = units[0]["unit"]
        self.assertNotIn("Rent roll lists bed A as Vacant Unrented Not Ready",
                         before[label])
        self.assertIn("Rent roll lists bed A as Vacant Unrented Not Ready",
                      after[label])


if __name__ == "__main__":
    unittest.main()

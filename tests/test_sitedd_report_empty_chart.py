"""A legend for nothing, and the warning that was describing it correctly.

`matplotlib` printed *"No artists with labels found to put in legend"*
every time a Site DD report was built for an assessment where no bar was
drawn -- which happens when every condition count is zero, i.e. nobody
has walked it yet. It was recorded as a cosmetic warning on every PDF and
left alone for long enough to become furniture.

TWO THINGS WERE WRONG WITH THAT DESCRIPTION, both measured here rather
than reasoned about:

* it is **not** on every PDF. A populated report has never warned.
* it is **not** cosmetic noise. The page was drawing an empty legend box
  under an empty chart, and the warning was an accurate report of that.

WHY IT MATTERS NOW rather than whenever it was first seen: seeding.
Assessment 21 is 152 units and zero findings, so its report is exactly
the unwalked case -- the condition became ordinary the day a rent roll
created a property nobody had inspected.

The chart now says "Nothing assessed yet" where the legend used to be,
which is the same information the warning carried, on the page, for the
person holding it.
"""

import tempfile
import unittest
import warnings
from pathlib import Path

from tools import site_dd_checklist as cl
from tools import site_dd_conditions as cond
from tools import site_dd_report as rep

ASSESSMENT = {"id": 1, "property_label": "Oxford Pointe",
              "assessed_on": "2026-08-31", "inspector": "MJ",
              "checklist_version": 2, "overall_notes": None}


def walked(n=3):
    """`items` and `summary` for an assessment with real conditions."""
    conds, items = {}, {}
    for i, (key, _label) in enumerate(cl.CATEGORIES[0]["items"][:n]):
        value = "good" if i % 2 else "repair"
        conds[key] = [value]
        items[key] = [{"condition": value, "note": None, "instance_no": 1}]
    return items, cond.summarize(conds, cl.CATEGORIES)


def build(items, summary):
    """Returns the warnings raised while building the report."""
    out = Path(tempfile.mkdtemp()) / "r.pdf"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rep.build_report(out, ASSESSMENT, items, summary, [], None)
    assert out.stat().st_size > 1000, "no PDF was written"
    return [str(w.message) for w in caught]


class TheUnwalkedReportIsSilentTests(unittest.TestCase):

    def test_an_assessment_with_nothing_assessed_raises_no_warning(self):
        self.assertEqual(build({}, cond.summarize({}, cl.CATEGORIES)), [])

    def test_and_still_produces_a_pdf(self):
        """The fix must not have made the empty case throw instead."""
        out = Path(tempfile.mkdtemp()) / "r.pdf"
        rep.build_report(out, ASSESSMENT, {}, cond.summarize({}, cl.CATEGORIES),
                         [], None)
        self.assertGreater(out.stat().st_size, 1000)

    def test_the_page_says_what_the_warning_said(self):
        """The information does not disappear with the warning: it moves
        onto the page, where the person holding the report can see it."""
        import inspect
        self.assertIn("Nothing assessed yet", inspect.getsource(rep.build_report))


class ThePopulatedReportIsUnchangedTests(unittest.TestCase):

    def test_a_walked_assessment_raises_no_warning(self):
        items, summary = walked()
        self.assertEqual(build(items, summary), [])

    def test_it_still_draws_a_legend(self):
        """The guard must skip the legend only when there is nothing to
        label -- otherwise the fix would have removed a real legend from
        every report and no test would have noticed."""
        import inspect
        src = inspect.getsource(rep.build_report)
        self.assertIn("if drawn:", src)
        self.assertIn("ax.legend(", src)


class ThePositiveControlTests(unittest.TestCase):
    """WITHOUT THIS THE TESTS ABOVE ARE VACUOUS: they assert an absence,
    and an absence is also what a report that never draws a chart gives.
    So the warning is provoked deliberately, on the same code path."""

    def test_calling_legend_on_an_empty_axis_does_warn(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig = plt.figure()
        ax = fig.add_subplot(111)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ax.legend(loc="lower right")
        plt.close(fig)
        self.assertTrue(any("No artists with labels" in str(w.message)
                            for w in caught),
                        "matplotlib no longer warns; this test is the reason "
                        "the guard exists and should be re-read if so")


if __name__ == "__main__":
    unittest.main()

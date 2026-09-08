"""Every `btn-` class a template uses has to exist in the stylesheet.

WHAT THIS CATCHES, AND IT HAD ALREADY HAPPENED

`class="btn btn-secondary"` appeared in **nine places across six
templates and four tools**, and `.btn-secondary` was never defined in
`static/style.css`. Base `.btn` supplies padding, weight and
`border: none` — **no background and no colour** — so those controls
rendered as bold text with padding rather than as buttons.

The four `<a>` uses were the sharp ones, "Open Notetaker" on the Investor
Report page being the one a user meets most: an anchor gets no browser
default, so there was nothing to see. The `<button>` uses were milder
only by accident, because the browser paints its own grey.

**Nothing failed.** Not a test, not a sweep, not a render — a class that
does not exist is silent by construction, which is what made it survive
across four tools.

WHY THIS TEST AND NOT AN EYE

The affordance problem in Part 104 — a link nobody could find — is **not**
mechanically checkable and that entry says so. **This one is**, exactly:
the set of classes used is finite and readable, the set defined is finite
and readable, and one must be a subset of the other. Where a check is
available it should exist, precisely so that judgement is spent on the
parts where no check is possible.

THE COMMENT-COLLISION HAZARD, HANDLED

Templates in this repo discuss their own classes in Jinja comments — the
Site DD detail page explains in prose why the import is `btn-primary` on
an empty assessment and `btn-ghost` otherwise. A naive scan reads those as
usages. **Comments are stripped before scanning**, the same rule the
source-grepping tests here already follow.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
STYLESHEET = ROOT / "static" / "style.css"

JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
CLASS_ATTR = re.compile('class="([^"]*)"')

# THE FIRST VERSION OF THIS CHECK REPORTED FIVE FALSE POSITIVES, and the
# fix was in this pattern rather than in any template.
#
#   a plain word boundary matched the TAIL of `sdd-nav-btn--primary`,
#   because there is one between the hyphen and the `b`. Those are BEM
#   modifiers on a different base class and are entirely correct.
#
# and scanning whole files rather than class attributes matched
# `id="btn-refresh-all"` on FIRE Metrics -- element ids, on buttons that
# already carry a correct `class="btn btn-ghost"`.
#
# So: only inside class attributes, and only where the token STARTS a
# class rather than continuing one. An instrument that reports correct
# code is worse than none, because somebody will "fix" what it names.
BTN_TOKEN = re.compile(r"(?<![\w-])btn-[a-z0-9-]+")


def strip_comments(text: str) -> str:
    return HTML_COMMENT.sub(" ", JINJA_COMMENT.sub(" ", text))


def classes_used() -> dict[str, list[str]]:
    """Every `btn-*` token appearing in template markup, by file.

    Scanned inside `class="..."` only, but across the whole attribute so
    that inline Jinja is seen — `class="btn {{ 'btn-primary' if not
    area_total else 'btn-ghost' }}"` uses BOTH, and only one of them is
    taken on any given render.
    """
    out: dict[str, list[str]] = {}
    for path in sorted(TEMPLATES.rglob("*.html")):
        body = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        found = set()
        for attr in CLASS_ATTR.findall(body):
            found.update(BTN_TOKEN.findall(attr))
        if found:
            out[str(path.relative_to(ROOT)).replace(chr(92), "/")] = sorted(found)
    return out


def classes_defined() -> set[str]:
    css = STYLESHEET.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"\.(btn-[a-z0-9-]+)", css))


class EveryButtonClassIsDefinedTests(unittest.TestCase):

    def test_the_stylesheet_and_templates_are_both_there(self):
        """Assert the population before asserting about it: an empty
        template glob or an unreadable stylesheet would make every check
        below pass by having nothing to compare."""
        self.assertTrue(STYLESHEET.exists(), STYLESHEET)
        self.assertGreater(len(list(TEMPLATES.rglob("*.html"))), 20)
        self.assertIn("btn-primary", classes_defined())

    def test_no_template_uses_a_class_the_stylesheet_does_not_define(self):
        """THE ONE THAT WOULD HAVE CAUGHT btn-secondary."""
        defined = classes_defined()
        offenders = {
            f: [c for c in used if c not in defined]
            for f, used in classes_used().items()
        }
        offenders = {f: cs for f, cs in offenders.items() if cs}
        self.assertEqual(
            offenders, {},
            "template button classes with no rule in static/style.css — "
            "these render with no background and no colour:\n" +
            "\n".join(f"  {f}: {cs}" for f, cs in offenders.items()))

    def test_btn_secondary_specifically_is_gone(self):
        """Named because it was the instance, and because a future
        migration back to it should have to argue rather than drift."""
        for f, used in classes_used().items():
            self.assertNotIn("btn-secondary", used, f)

    def test_the_check_can_actually_fail(self):
        """Positive control. Without it, a scanner that silently returned
        nothing would satisfy every assertion above."""
        defined = classes_defined()
        self.assertNotIn("btn-does-not-exist", defined)
        pretend = {"templates/made-up.html": ["btn-primary", "btn-does-not-exist"]}
        offenders = {f: [c for c in used if c not in defined]
                     for f, used in pretend.items()}
        self.assertEqual(offenders, {"templates/made-up.html": ["btn-does-not-exist"]})

    def test_comments_are_not_read_as_usages(self):
        """The Site DD detail page explains its own button weights in a
        Jinja comment. A scan that counted those would report classes no
        rendered page carries."""
        sample = ("{# we use btn-invented here because reasons #}\n"
                  '<a class="btn btn-ghost">x</a>')
        found = set()
        for attr in CLASS_ATTR.findall(strip_comments(sample)):
            found.update(BTN_TOKEN.findall(attr))
        self.assertEqual(found, {"btn-ghost"})

    def test_the_conditional_form_is_seen(self):
        """Both branches of an inline weight choice are real usages."""
        sample = """<a class="btn {{ 'btn-primary' if x else 'btn-ghost' }}">x</a>"""
        found = set()
        for attr in CLASS_ATTR.findall(strip_comments(sample)):
            found.update(BTN_TOKEN.findall(attr))
        self.assertEqual(found, {"btn-primary", "btn-ghost"})

    def test_a_bem_modifier_on_another_base_is_not_a_btn_class(self):
        """`sdd-nav-btn--primary` is not a `btn-` class, and reporting it
        would send somebody to edit a template that is correct."""
        sample = '<button class="sdd-nav-btn sdd-nav-btn--primary">x</button>'
        found = set()
        for attr in CLASS_ATTR.findall(sample):
            found.update(BTN_TOKEN.findall(attr))
        self.assertEqual(found, set())

    def test_an_id_is_not_a_class(self):
        """FIRE Metrics names buttons `id="btn-refresh-all"`. Ids are not
        classes, and those elements already carry correct ones."""
        sample = '<button id="btn-refresh-all" class="btn btn-primary">x</button>'
        found = set()
        for attr in CLASS_ATTR.findall(sample):
            found.update(BTN_TOKEN.findall(attr))
        self.assertEqual(found, {"btn-primary"})


if __name__ == "__main__":
    unittest.main()

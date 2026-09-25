"""Check the built theme-aware icons and restored title after a deploy-base build.

Run: DEPLOY_BASE=/dysonsphere python3 -m unittest discover -s scripts -p 'test_brand_assets.py'
"""

import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
import unittest


SITE = Path(__file__).resolve().parents[1]
DIST = SITE / "dist"
BASE = "/" + os.environ.get("DEPLOY_BASE", "/dysonsphere").strip("/") + "/"
ICONS = SITE / "logo/dysonsphere-brand/svg"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.images = []
        self.links = []
        self.anchors = []
        self.card_anchors = []
        self.nested_anchors = []
        self.headings = []
        self.heading_text = ""
        self.buttons = []
        self.charts = []
        self.hero_in_main = False
        self.landing_in_main = False
        self.title_words = []
        self.scripts = []
        self.styles = []
        self.active_script = None
        self.active_style = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self.images.append((attrs, tuple(self.stack)))
        elif tag == "link":
            self.links.append(attrs)
        elif tag == "a":
            self.anchors.append(attrs)
            if any(t == "a" for t, _ in self.stack):
                self.nested_anchors.append(attrs)
            if any(t == "div" and "sl-link-card" in classes.split() for t, classes in self.stack):
                self.card_anchors.append(attrs)
        elif tag == "h1":
            self.headings.append(attrs)
        elif tag == "button":
            self.buttons.append(attrs)
        elif tag == "div" and attrs.get("data-chart"):
            self.charts.append(attrs)
        if tag == "div" and "hero" in attrs.get("class", "").split():
            self.hero_in_main = any("main-pane" in classes.split() for _, classes in self.stack)
        if tag == "div" and "landing" in attrs.get("class", "").split():
            self.landing_in_main = any("main-pane" in classes.split() for _, classes in self.stack)
        if tag == "script":
            self.active_script = {"attrs": attrs, "body": ""}
            self.scripts.append(self.active_script)
        elif tag == "style":
            self.active_style = {"attrs": attrs, "body": ""}
            self.styles.append(self.active_style)
        if tag in ("div", "a", "h1", "span"):
            self.stack.append((tag, attrs.get("class", "")))

    def handle_data(self, text):
        if self.active_script is not None:
            self.active_script["body"] += text
        if self.active_style is not None:
            self.active_style["body"] += text
        if any(tag == "h1" for tag, _ in self.stack):
            self.heading_text += text
        if any(tag == "a" and "site-title" in classes.split() for tag, classes in self.stack):
            for tag, classes in reversed(self.stack):
                if tag == "span" and set(classes.split()) & {"ds", "sp"}:
                    self.title_words.append(("ds" if "ds" in classes.split() else "sp", text))
                    break

    def handle_endtag(self, tag):
        if tag == "script":
            self.active_script = None
        elif tag == "style":
            self.active_style = None
        if tag in ("div", "a", "h1", "span"):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    break


def page(path):
    parsed = Page()
    parsed.feed((DIST / path).read_text())
    return parsed


def images_with_ancestor(parsed, tag, class_name):
    return [attrs for attrs, stack in parsed.images
            if any(t == tag and class_name in classes.split() for t, classes in stack)]


def compiled_rule(css, selector):
    """Read declarations from a built CSS rule, not the authored stylesheet."""
    start = selector + "{"
    if start not in css:
        raise AssertionError(f"Missing built selector: {selector}")
    body = css.split(start, 1)[1].split("}", 1)[0]
    return dict(part.split(":", 1) for part in body.split(";") if ":" in part)


class BrandBuildTest(unittest.TestCase):
    def assert_asset(self, src):
        self.assertTrue(src.startswith(BASE), src)
        path = DIST / src.removeprefix(BASE)
        self.assertTrue(path.is_file(), str(path))
        return path

    def assert_icon_variants(self, images, *, monochrome=False):
        self.assertEqual(len(images), 2, images)
        for theme in ("light", "dark"):
            variant = {"light": "mono-black", "dark": "mono-white"}[theme] if monochrome else theme
            name = f"dysonsphere-icon-{variant}"
            image = next((img for img in images if Path(img["src"]).name.startswith(name + ".")), None)
            self.assertIsNotNone(image, (theme, images))
            hidden_in = "dark" if theme == "light" else "light"
            self.assertIn(f"{hidden_in}:sl-hidden", image.get("class", "").split())
            self.assertIn("alt", image)
            self.assertIn(image["alt"], ("", None))
            self.assertEqual(self.assert_asset(image["src"]).read_bytes(),
                             (ICONS / f"{name}.svg").read_bytes())

    def test_header_homepage_and_favicon(self):
        for route in ("index.html", "guides/getting-started/index.html"):
            with self.subTest(route=route):
                parsed = page(route)
                header = images_with_ancestor(parsed, "a", "site-title")
                self.assert_icon_variants(header, monochrome=True)  # One monochrome emblem per theme.
                self.assertEqual(parsed.title_words, [("ds", "dyson"), ("sp", "sphere")])
                toggle = next((b for b in parsed.buttons if b.get("id") == "ds-sidebar-toggle"), None)
                self.assertIsNotNone(toggle)
                self.assertEqual(toggle["aria-controls"], "starlight__sidebar")
                self.assertEqual(toggle["aria-expanded"], "true")
                self.assertTrue(any("ds-sidebar" in s["body"] and "astro:after-swap" in s["body"]
                                    for s in parsed.scripts))
                favicon = [l for l in parsed.links if "icon" in l.get("rel", "").split()]
                self.assertEqual(len(favicon), 1)
                self.assertEqual(favicon[0]["href"], BASE + "favicon.svg")
                self.assert_asset(favicon[0]["href"])

        home = page("index.html")
        self.assertTrue(home.hero_in_main and home.landing_in_main)  # Homepage-scoped CSS reaches both.
        self.assert_icon_variants(images_with_ancestor(home, "div", "hero"))
        self.assertEqual(len(home.headings), 1)
        self.assertIn("data-page-title", home.headings[0])
        self.assertEqual(home.heading_text, "dysonsphere")  # Static accessible fallback.
        self.assertEqual(images_with_ancestor(page("guides/getting-started/index.html"), "div", "hero"), [])
        self.assertEqual(home.charts, [])
        html = (DIST / "index.html").read_text()
        self.assertNotIn('id="landing-demo-title"', html)
        self.assertNotIn("home_demo", html)
        for route in ("guides/getting-started/", "guides/marks/", "studio/"):
            self.assertTrue(any(a.get("href") == route for a in home.anchors), route)
            self.assertTrue((DIST / route / "index.html").is_file(), route)
        card_routes = {
            "gallery/", "guides/theming/", "guides/palettes/", "guides/comparisons/",
            "guides/marks/", "guides/saving/", "studio/",
        }
        self.assertEqual(len(home.card_anchors), 7)
        self.assertEqual(home.card_anchors[0]["href"], "gallery/")
        self.assertEqual({a["href"] for a in home.card_anchors}, card_routes)
        self.assertEqual(home.nested_anchors, [])
        for route in card_routes:
            self.assertTrue((DIST / route / "index.html").is_file(), route)

        palette_data = [script for script in home.scripts if script["attrs"].get("id") == "tw-chip-pairs"]
        self.assertEqual(len(palette_data), 1)
        self.assertEqual(palette_data[0]["attrs"].get("type"), "application/json")
        self.assertGreater(len(json.loads(palette_data[0]["body"])), 0)
        # The component's module is included in the built page and registers after page swaps.
        self.assertTrue(any(script["attrs"].get("type") == "module"
                            and "tw-chip-pairs" in script["body"]
                            and "astro:page-load" in script["body"]
                            and "statistical" in script["body"]
                            and "annotations" in script["body"]
                            for script in home.scripts))
        self.assertFalse(any(s["attrs"].get("id") == "tw-chip-pairs" for s in page("guides/getting-started/index.html").scripts))

    def test_theme_rules_and_visible_animated_heading(self):
        home = page("index.html")
        css = "\n".join(p.read_text() for p in (DIST / "_astro").glob("*.css"))
        css += "\n" + "\n".join(style["body"] for style in home.styles)
        self.assertIn("[data-theme=light] .light\\:sl-hidden", css)
        self.assertIn("[data-theme=dark] .dark\\:sl-hidden", css)
        self.assertIn(".hero h1:not([data-tw])", css)
        self.assertIn("tw-appear", css)
        self.assertNotIn(".hero h1[data-page-title]", css)  # No leftover hidden-heading rule.
        self.assertNotIn("aspect-ratio:720/250", css)
        self.assertEqual(compiled_rule(css, ".landing__features .sl-link-card")["cursor"], "pointer")
        self.assertTrue(compiled_rule(css, ".landing__features .sl-link-card:focus-within")["outline"].startswith("2px solid"))
        gallery = compiled_rule(css, ".landing__gallery")
        self.assertEqual(gallery["width"], "min(100%,28rem)")
        self.assertEqual(gallery["margin"], "0 auto 1.5rem")
        self.assertEqual(gallery["text-align"], "center")
        gallery_card = compiled_rule(css, ".landing__gallery .sl-link-card")
        columns = gallery_card["grid-template-columns"].split()
        self.assertEqual(len(columns), 3)
        self.assertEqual(columns[0], columns[2])  # Balance the arrow with equal space on the left.
        self.assertEqual(columns[1], "minmax(0,1fr)")
        self.assertEqual(compiled_rule(css, ".landing__gallery .sl-link-card>.stack")["grid-column"], "2")
        self.assertEqual(compiled_rule(css, ".landing__gallery .sl-link-card>.icon")["grid-column"], "3")
        self.assertEqual(gallery_card["border-inline-start"].split()[:2], ["3px", "solid"])
        self.assertEqual(gallery_card["border-inline-end"].split()[:2], ["3px", "solid"])
        self.assertIn("--gallery-accent", compiled_rule(css, ":root[data-theme=dark] .landing__gallery"))
        self.assertNotIn(".landing__demo", css)

        # Static built-CSS contract, not a measurement of browser geometry. Separate grid rows
        # keep the icon independent of the animated title, and cqi keys type size to the hero's
        # own width even when the desktop sidebar is collapsed.
        scope = ".main-pane:has(.landing) .hero"
        hero = compiled_rule(css, scope)
        icon = compiled_rule(css, scope + ">img")
        stack = compiled_rule(css, scope + " .stack")
        copy = compiled_rule(css, scope + " .copy")
        title = compiled_rule(css, scope + " h1")
        self.assertEqual(hero["container-type"], "inline-size")
        self.assertEqual(hero["grid-template-columns"], "minmax(0,1fr)")
        self.assertEqual(icon["order"], "0")
        self.assertEqual(icon["aspect-ratio"], "1")
        self.assertTrue(icon["width"].startswith("clamp("))
        self.assertEqual(stack["order"], "1")
        self.assertEqual(stack["min-width"], "0")
        self.assertEqual(copy["min-width"], "0")
        self.assertEqual(title["width"], "100%")
        self.assertEqual(title["max-width"], "100%")

        # JetBrains Mono advances roughly 0.6em. Use 0.65em plus chip and caret space to
        # estimate a conservative upper width for statisticalannotations at typical content
        # widths (mobile, tablet, desktop sidebar open and collapsed). Font sizing is based
        # only on the container, so partial typing cannot change this estimate or icon size.
        match = re.fullmatch(r"clamp\(([\d.]+)rem,([\d.]+)cqi,([\d.]+)rem\)", title["font-size"])
        self.assertIsNotNone(match, title)
        min_rem, percent, max_rem = map(float, match.groups())
        tw = compiled_rule(css, ".tw")
        tw_scale = float(tw["font-size"].removesuffix("em"))
        long_stop = "statisticalannotations"
        for width in (240, 328, 736, 468, 932, 1232):
            heading_px = min(max_rem * 16, max(min_rem * 16, width * percent / 100))
            estimated_px = heading_px * tw_scale * (len(long_stop) * 0.65 + 0.5)
            self.assertLess(estimated_px, width, (width, estimated_px))


if __name__ == "__main__":
    unittest.main()

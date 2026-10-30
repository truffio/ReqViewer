import re
import unittest
from pathlib import Path

from reqviewer import config, graph, render
from support import SAMPLE, payload


def data_line(page):
    return re.search(r"^const DATA = .*;$", page, re.M).group(0)


class RenderTest(unittest.TestCase):
    def test_sample_page_embeds_the_data(self):
        data = graph.build(SAMPLE, config.load_config(SAMPLE))
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertNotIn("/*DATA*/", page)
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html"))

    def test_data_is_read_with_json_parse(self):
        self.assertTrue(data_line(render.render({})).startswith('const DATA = JSON.parse("'))

    def test_less_than_is_escaped(self):
        data = {"title": "</script><script>alert(1)</script><!--", "n": "a < b"}
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertEqual(page.count("</script>"), render.render({}).count("</script>"))   # none from the data
        self.assertNotIn("<", data_line(page))
        self.assertIn("\\u003c/script>", page)
        self.assertNotIn("alert(1)</script>", page)

    def test_unicode_is_kept(self):
        data = {"t": "\u00e9\u2014", "line": "a\u2028b\u2029c", "far": "\U0001f600"}
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertTrue(data_line(page).isascii())            # so that no encoding can fail or alter it

    def test_lone_surrogate_does_not_break_the_write(self):
        data = {"message": "\ud800", "name": "x\udfffy"}
        page = render.render(data)
        page.encode("utf-8")
        self.assertEqual(payload(page), data)

    def test_placeholder_text_in_data_is_not_substituted_again(self):
        data = {"t": "/*DATA*/null"}
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertEqual(page.count("/*DATA*/null"), 1)

    def test_keys_named_like_object_members_survive(self):
        data = {"__proto__": {"__proto__": [1]}, "constructor": {"toString": 1}, "findings": {"__proto__": []}}
        self.assertEqual(payload(render.render(data)), data)


class TemplateTest(unittest.TestCase):
    """Page behaviour is run by the smoke script; these pin the fixes that show in the source."""
    template = Path(render.__file__).with_name("template.html").read_text(encoding="utf-8")

    def test_colour_is_not_followed_by_alpha_digits(self):
        self.assertNotRegex(self.template, r'fill="\$\{c\}[0-9a-f]{2}"')   # "#3a7" + "22" is not a colour
        self.assertIn('fill-opacity=', self.template)

    def test_data_lookups_use_own_properties(self):
        self.assertIn("Object.hasOwn(o, k)", self.template)
        self.assertNotRegex(self.template, r"DATA\.findings\[")

    def test_view_parameter_is_checked(self):
        self.assertIn('["explorer", "coverage", "findings"].includes(wanted)', self.template)


if __name__ == "__main__":
    unittest.main()

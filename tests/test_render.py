import json
import re
import unittest

from reqviewer import config, graph, render
from support import SAMPLE


def payload(page):
    return json.loads(re.search(r"^const DATA = (.*);$", page, re.M).group(1))


class RenderTest(unittest.TestCase):
    def test_sample_page_embeds_the_data(self):
        data = graph.build(SAMPLE, config.load_config(SAMPLE))
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertNotIn("/*DATA*/", page)
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html"))

    def test_less_than_is_escaped(self):
        data = {"title": "</script><script>alert(1)</script><!--", "n": "a < b"}
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertEqual(page.count("</script>"), render.render({}).count("</script>"))   # none from the data
        self.assertIn("\\u003c/script>", page)
        self.assertNotIn("alert(1)</script>", page)

    def test_unicode_is_kept(self):
        self.assertIn("é—", render.render({"t": "é—"}))

    def test_placeholder_text_in_data_is_not_substituted_again(self):
        data = {"t": "/*DATA*/null"}
        page = render.render(data)
        self.assertEqual(payload(page), data)
        self.assertEqual(page.count("/*DATA*/null"), 1)


if __name__ == "__main__":
    unittest.main()

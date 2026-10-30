import json
import unittest

from reqviewer import checks
from reqviewer.config import ConfigError
from support import ProjectCase, req

P = "Parent(s)"
REFS = '[ids]\npatterns = ["[A-Z]+-[0-9]+"]\n'


class BuiltInChecksTest(ProjectCase):
    def codes(self, data):
        return {(item, f["code"], f["severity"]) for item, fs in data["findings"].items() for f in fs}

    def test_duplicate_id(self):
        data = self.build({"requirements/L0.md": req("A-1") + req("A-1"), "requirements/L1.md": req("A-1")})
        fs = data["findings"]["A-1"]
        self.assertEqual([f["code"] for f in fs], ["DUPLICATE_ID"] * 2)
        self.assertEqual(fs[0]["severity"], "error")
        self.assertIn("requirements/L1.md", fs[1]["message"])
        self.assertEqual(self.node(data, "A-1")["file"], "requirements/L0.md")     # first kept

    def test_unknown_parent(self):
        data = self.build({"requirements/L1.md": req("A-1", **{P: "Z-9"})}, REFS)
        self.assertEqual(self.codes(data), {("A-1", "UNKNOWN_PARENT", "error")})
        self.assertIn("Z-9", data["findings"]["A-1"][0]["message"])

    def test_dangling_ref(self):
        data = self.build({"requirements/L1.md": req("A-1", Notes="see Z-9")}, REFS)
        self.assertEqual(self.codes(data), {("A-1", "DANGLING_REF", "warning")})

    def test_known_references_give_no_findings(self):
        data = self.build({"requirements/L0.md": req("A-1"),
                           "requirements/L1.md": req("A-2", **{P: "A-1"}, Notes="see A-1")}, REFS)
        self.assertEqual(data["findings"], {})

    def test_format_is_still_reported(self):
        data = self.build({"requirements/L0.md": "```req\nStatement: no id\n```\n"})
        self.assertEqual(self.codes(data), {("", "FORMAT", "error")})


class ExternalFindingsTest(ProjectCase):
    def load(self, text):
        root = self.project({"f.json": text})
        return checks.load_external(root / "f.json")

    def test_good_file(self):
        items = [{"item": "A-1", "severity": "error", "code": "LINT", "message": "m"},
                 {"item": "", "severity": "warning", "code": "LINT", "message": "n"}]
        self.assertEqual(self.load(json.dumps(items)), items)

    def test_empty_list(self):
        self.assertEqual(self.load("[]"), [])

    def test_bad_files(self):
        good = {"item": "", "severity": "error", "code": "C", "message": "m"}
        bad = ["{", '{"a": 1}', "[1]", json.dumps([{**good, "severity": "info"}]),
               json.dumps([{k: v for k, v in good.items() if k != "code"}]),
               json.dumps([{**good, "item": None}])]
        for text in bad:
            with self.subTest(text), self.assertRaises(ConfigError):
                self.load(text)

    def test_missing_file(self):
        root = self.project({})
        with self.assertRaises(ConfigError):
            checks.load_external(root / "nope.json")

    def test_merged_with_built_in(self):
        from reqviewer import config, graph
        import tomllib
        root = self.project({"requirements/L1.md": req("A-1", **{P: "Z-9"})})
        extra = [{"item": "A-1", "severity": "warning", "code": "LINT", "message": "m"}]
        data = graph.build(root, config.parse(tomllib.loads(REFS)), extra)
        self.assertEqual([f["code"] for f in data["findings"]["A-1"]], ["UNKNOWN_PARENT", "LINT"])


if __name__ == "__main__":
    unittest.main()

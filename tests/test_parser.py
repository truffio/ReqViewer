import tomllib
from pathlib import Path
import unittest

from reqviewer import config
from reqviewer.parser import MarkdownLoader
from support import ProjectCase, block, req


class ParserTest(ProjectCase):
    def load(self, files, toml=""):
        root = self.project(files)
        return MarkdownLoader().load(root, config.parse(tomllib.loads(toml)))

    def test_fields_and_continuation_lines(self):
        text = "```req\nID: A-1\nStatement: first line\n  second line\nParent(s): —\n```\n"
        res = self.load({"requirements/L0.md": text})
        self.assertEqual(res.problems, [])
        rec, = res.records
        self.assertEqual(rec.get("Statement"), "first line second line")
        self.assertEqual(rec.get("Missing"), "")
        self.assertEqual((rec.kind, rec.file_level, rec.line), ("req", "L0", 1))

    def test_assumption_fence(self):
        res = self.load({"requirements/L0.md": block({"ID": "A-1", "Assumption": "x"}, "asm")})
        self.assertEqual([r.kind for r in res.records], ["asm"])

    def test_levels_sort_naturally(self):
        files = {f"requirements/{n}.md": req(f"X-{i}") for i, n in enumerate(["L10", "L2", "L1"])}
        res = self.load(files)
        self.assertEqual(res.levels, ["L1", "L2", "L10"])
        self.assertEqual([r.file_level for r in res.records], ["L1", "L2", "L10"])

    def test_level_from_file_name_or_stem(self):
        res = self.load({"requirements/L3_draft.md": req("A-1"), "requirements/Lx.md": req("A-2")})
        self.assertEqual(sorted(res.levels), ["L3", "Lx"])
        res = self.load({"docs/top.md": req("A-1")}, '[files]\nlevels = ["docs/*.md"]')
        self.assertEqual(res.levels, ["top"])

    def test_sections_default_and_empty(self):
        text = ("<!-- BEGIN SECTION ONE -->\n" + req("A-1") + "<!-- END SECTION ONE -->\n"
                "<!-- BEGIN SECTION EMPTY -->\n<!-- END SECTION EMPTY -->\n" + req("A-2"))
        res = self.load({"requirements/L0.md": text})
        self.assertEqual(res.problems, [])
        self.assertEqual(res.sections, [("L0", "ONE"), ("L0", "EMPTY"), ("L0", "General")])
        self.assertEqual([r.section for r in res.records], ["ONE", "General"])

    def test_default_section_is_configurable(self):
        res = self.load({"requirements/L0.md": req("A-1")}, '[format]\ndefault_section = "Misc"')
        self.assertEqual(res.records[0].section, "Misc")
        self.assertEqual(res.sections, [("L0", "Misc")])

    def test_unbalanced_markers_are_problems(self):
        text = ("<!-- END SECTION LOST -->\n<!-- BEGIN SECTION A -->\n<!-- BEGIN SECTION B -->\n"
                "<!-- END SECTION B -->\n<!-- BEGIN SECTION B -->\n")
        res = self.load({"requirements/L0.md": text})
        messages = " | ".join(p.message for p in res.problems)
        self.assertIn("END SECTION LOST without matching BEGIN", messages)
        self.assertIn("section B begins inside A", messages)
        self.assertIn("duplicate section B", messages)
        self.assertIn("section B has no END marker", messages)
        self.assertTrue(all(p.code == "FORMAT" and p.severity == "error" for p in res.problems))

    def test_field_problems(self):
        text = ("```req\nID: A-1\nColour: red\nStatement: x\nStatement: y\nnot a field\n  orphan\n```\n"
                "```req\nStatement: no id\n```\n```req\nID: A-3\nStatement: open")
        res = self.load({"requirements/L0.md": text}, '[format]\nreq_fields = ["ID", "Statement"]')
        messages = " | ".join(f"{p.line}:{p.message}" for p in res.problems)
        for part in ("unknown field 'Colour'", "duplicate field 'Statement'", "not a 'Field: value'",
                     "no ID", "unclosed"):
            self.assertIn(part, messages)
        self.assertEqual([r.get("ID") for r in res.records], ["A-1", "A-3"])
        self.assertEqual(res.records[0].get("Statement"), "x")

    def test_heading_must_match_id(self):
        text = "### A-9\n" + req("A-1") + "### A-2\n" + req("A-2") + req("A-3")
        res = self.load({"requirements/L0.md": text}, "[format]\nheading_must_match_id = true")
        self.assertEqual(len(res.problems), 1)
        self.assertIn("'A-9' does not match", res.problems[0].message)
        res = self.load({"requirements/L0.md": text})
        self.assertEqual(res.problems, [])

    def test_custom_fences_and_id_field(self):
        text = "```need\nCode: N-1\nText: x\n```\n```risk\nCode: R-1\n```\n```req\nCode: no\n```\n"
        toml = '[format]\nreq_fence = "need"\nasm_fence = "risk"\nid_field = "Code"'
        res = self.load({"requirements/L0.md": text}, toml)
        self.assertEqual([(r.kind, r.get("Code")) for r in res.records], [("req", "N-1"), ("asm", "R-1")])

    def test_unreadable_file_is_a_problem(self):
        root = self.project({"requirements/L0.md": ""})
        (root / "requirements" / "L0.md").write_bytes(b"\xff\xfe\x00bad")
        res = MarkdownLoader().load(root, config.Config())
        self.assertEqual(len(res.problems), 1)
        self.assertIn("cannot read", res.problems[0].message)

    def test_no_files(self):
        res = self.load({})
        self.assertEqual((res.records, res.sections, res.levels, res.problems), ([], [], [], []))

    def test_parser_does_not_import_yaml(self):
        import reqviewer.parser as parser
        self.assertNotIn("yaml", Path(parser.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

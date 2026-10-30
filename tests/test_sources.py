import sys
import tomllib
import unittest
from unittest import mock

from reqviewer import config
from reqviewer.sources import load_sources
from support import ProjectCase, needs_yaml

NEEDS = """\
| ID | Who | Need | Meaning |
| --- | --- | --- | --- |
| N-1 | SH-1 | "A long wanted need that goes on and on" | m1 |
| N-2 | SH-1 | short | m2 |
| N-3 | not-a-stakeholder | rejected by require | m3 |
| N-4 | SH-2 |
| N-1 | SH-9 | Again the first ID | m |
| SH-1 | Alice | stakeholder row |
"""
TABLE = """
[[sources]]
type = "table"
kind = "need"
file = "needs.md"
id = 'N-\\d'
title = 2
title_max = 12
title_strip = '"'
min_columns = 4
require = { 1 = '^SH-\\d$' }
columns = { Who = 1, Meaning = 3, Absent = 9 }
links = [{ kind = "who", column = 1 }, { kind = "ids", column = 2, pattern = 'N-\\d' }]
"""


class SourcesTest(ProjectCase):
    def load(self, files, toml):
        root = self.project(files)
        return load_sources(root, config.parse(tomllib.loads(toml)))

    def test_table_rules(self):
        items, problems = self.load({"needs.md": NEEDS}, TABLE)
        self.assertEqual(problems, [])
        self.assertEqual([i["id"] for i in items], ["N-1", "N-2", "N-1"])   # N-3 fails require, N-4 is short
        first = items[0]
        self.assertEqual(first["title"], "A long wante")                   # stripped, then cut at 12
        self.assertEqual(first["fields"], {"Who": "SH-1", "Meaning": "m1", "Absent": ""})
        self.assertEqual([(ln.kind, t) for ln, t in first["links"]], [("who", "SH-1")])
        self.assertEqual(first["kind"], "need")
        self.assertNotIn("status", first)

    def test_table_link_patterns(self):
        text = "| N-1 | SH-1 | see N-2 and N-3 and N-2 | m |\n"
        items, _ = self.load({"needs.md": text}, TABLE)
        self.assertEqual([(ln.kind, t) for ln, t in items[0]["links"]],
                         [("who", "SH-1"), ("ids", "N-2"), ("ids", "N-3")])

    def test_table_without_limits(self):
        toml = '[[sources]]\ntype="table"\nkind="k"\nfile="t.md"\nid="N-\\\\d"\ntitle=2'
        items, _ = self.load({"t.md": "| N-1 | a | " + "x" * 200 + " |\n"}, toml)
        self.assertEqual(len(items[0]["title"]), 200)

    def test_heading_source(self):
        toml = '[[sources]]\ntype="heading"\nkind="sc"\nfile="s.md"\npattern=\'^#### (SC-\\d+) — (.+)$\''
        text = "#### SC-1 —  First one \n### SC-2 — wrong level\n#### SC-3 — Third\ntext #### SC-4 — no\n"
        items, _ = self.load({"s.md": text}, toml)
        self.assertEqual([(i["id"], i["title"]) for i in items], [("SC-1", "First one"), ("SC-3", "Third")])

    def test_utf8_bom_is_ignored(self):
        items, _ = self.load({"needs.md": "﻿" + NEEDS}, TABLE)
        self.assertEqual([i["id"] for i in items], ["N-1", "N-2", "N-1"])
        toml = '[[sources]]\ntype="heading"\nkind="sc"\nfile="s.md"\npattern=\'^#### (SC-\\d+)\''
        items, _ = self.load({"s.md": "﻿#### SC-1\n"}, toml)
        self.assertEqual([i["id"] for i in items], ["SC-1"])

    def test_only_newlines_end_a_row(self):
        text = "| N-1 | SH-1 | a b\x85c | m |\n"
        items, _ = self.load({"needs.md": text}, TABLE.replace("title_max = 12", "title_max = 0"))
        self.assertEqual(items[0]["title"], "a b\x85c")

    @needs_yaml
    def test_yaml_utf8_bom_is_ignored(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"'
        items, problems = self.load({"t.yaml": "﻿- {id: A}\n"}, toml)
        self.assertEqual(([i["id"] for i in items], problems), (["A"], []))

    def test_missing_file_is_skipped(self):
        toml = TABLE + TABLE.replace('file = "needs.md"', 'file = "nope.md"')
        items, problems = self.load({"needs.md": NEEDS}, toml)
        self.assertEqual((len(items), problems), (3, []))                   # missing file skipped silently

    @needs_yaml
    def test_yaml_source(self):
        yaml = "things:\n  - {id: T-1, name: One, status: ok, unit: kg, empty: ~}\n  - {id: 2, name: Two}\n"
        toml = ('[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"\nlist_key="things"\n')
        items, problems = self.load({"t.yaml": yaml}, toml)
        self.assertEqual(problems, [])
        self.assertEqual([i["id"] for i in items], ["T-1", "2"])
        self.assertEqual(items[0]["fields"], {"Id": "T-1", "Name": "One", "Status": "ok", "Unit": "kg", "Empty": ""})
        self.assertEqual((items[0]["title"], items[0]["status"], items[1]["status"]), ("One", "ok", ""))

    @needs_yaml
    def test_yaml_top_level_list(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"'
        items, problems = self.load({"t.yaml": "- {id: A, name: n}\n"}, toml)
        self.assertEqual(([i["id"] for i in items], problems), (["A"], []))

    @needs_yaml
    def test_yaml_problems_are_reported(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"\nlist_key="things"'
        cases = {"things: [a, {id: X}, {name: no id}]\n": ("entry 1 is not a mapping", "entry 3 has no 'id'"),
                 "things: 3\n": ("must be a list",),
                 "things: [unclosed\n": ("cannot read",)}
        for text, messages in cases.items():
            with self.subTest(text):
                items, problems = self.load({"t.yaml": text}, toml)
                self.assertEqual(len(problems), len(messages))
                for p, m in zip(problems, messages):
                    self.assertIn(m, p.message)
                    self.assertEqual((p.file, p.code, p.severity), ("t.yaml", "FORMAT", "error"))
        self.assertEqual(self.load({"t.yaml": "things:\n"}, toml), ([], []))

    @needs_yaml
    def test_yaml_errors_that_are_not_yaml_errors_are_problems(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"'
        for text in ("- {id: A, when: 2001-13-45}\n", "[" * 5000 + "]" * 5000 + "\n"):
            with self.subTest(text[:20]):
                items, problems = self.load({"t.yaml": text}, toml)
                self.assertEqual((items, len(problems)), ([], 1))
                self.assertIn("cannot read", problems[0].message)

    @needs_yaml
    def test_yaml_list_key_missing_is_a_problem(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"\nlist_key="things"'
        items, problems = self.load({"t.yaml": "thing: [{id: A}]\n"}, toml)
        self.assertEqual(items, [])
        self.assertEqual([p.message for p in problems], ["no key 'things' at the top level"])

    @needs_yaml
    def test_yaml_empty_id_is_a_problem(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"'
        items, problems = self.load({"t.yaml": "- {id: ''}\n- {id: ' '}\n- {id: B}\n"}, toml)
        self.assertEqual([i["id"] for i in items], ["B"])
        self.assertEqual(len(problems), 2)

    def test_heading_pattern_without_an_id_is_a_problem(self):
        toml = '[[sources]]\ntype="heading"\nkind="sc"\nfile="s.md"\npattern=\'^#### (SC-\\d+)?x\''
        items, problems = self.load({"s.md": "#### x\n#### SC-1x\n"}, toml)
        self.assertEqual([i["id"] for i in items], ["SC-1"])
        self.assertEqual(len(problems), 1)
        self.assertIn("line 1", problems[0].message)

    def test_yaml_without_pyyaml(self):
        toml = '[[sources]]\ntype="yaml"\nkind="thing"\nfile="t.yaml"'
        with mock.patch.dict(sys.modules, {"yaml": None}):
            items, problems = self.load({"t.yaml": "- {id: A}\n"}, toml)
        self.assertEqual(items, [])
        self.assertIn("PyYAML", problems[0].message)

    def test_yaml_is_not_imported_without_a_yaml_source(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            _, problems = self.load({"needs.md": NEEDS}, TABLE)
        self.assertEqual(problems, [])

    def test_unreadable_source_file(self):
        root = self.project({"needs.md": ""})
        (root / "needs.md").write_bytes(b"\xff\xfe\x00")
        _, problems = load_sources(root, config.parse(tomllib.loads(TABLE)))
        self.assertIn("cannot read", problems[0].message)


if __name__ == "__main__":
    unittest.main()

import json
import re
import unittest
from pathlib import Path

from reqviewer import config, graph
from support import SAMPLE, needs_yaml, ProjectCase, req

REFS = '[ids]\npatterns = ["[A-Z]+-\\\\d+"]\n'
P = "Parent(s)"


@needs_yaml
class SampleContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = graph.build(SAMPLE, config.load_config(SAMPLE))

    def test_top_level_keys_and_json(self):
        self.assertEqual(list(self.data), ["meta", "nodes", "edges", "findings", "sections", "problems"])
        self.assertEqual(json.loads(json.dumps(self.data)), self.data)

    def test_meta(self):
        meta = self.data["meta"]
        self.assertEqual(list(meta), ["title", "storage_key", "id_pattern", "levels", "roles", "id_field",
                                      "uses_fields", "none_value",
                                      "detail_rows", "label_strip", "rationale_split", "criteria_marker",
                                      "value_field", "unit_field", "kinds", "edges"])
        self.assertEqual(meta["title"], "BrewBox requirements")
        self.assertEqual(meta["storage_key"], "reqviewer.brewbox-requirements")
        self.assertEqual(meta["levels"], ["L0", "L1", "L2"])
        self.assertEqual(meta["roles"]["parents"], "Parent(s)")
        self.assertEqual(meta["none_value"], "—")
        self.assertEqual(meta["rationale_split"], "Sufficiency:")
        self.assertEqual(meta["kinds"]["req"], {"label": "Requirement", "group": "Requirements", "color": ""})
        self.assertEqual(meta["kinds"]["param"], {"label": "Parameter", "group": "Parameters", "color": "#8c8c84"})
        self.assertEqual(meta["kinds"]["scenario"]["group"], "Scenarios")
        self.assertEqual(meta["kinds"]["missing"]["color"], "#e15759")
        self.assertEqual(meta["edges"]["uses"], {"label": "uses", "reverse": "used by"})
        self.assertEqual(meta["edges"]["exercises"], {"label": "exercises", "reverse": "exercised by"})
        self.assertTrue(re.compile(meta["id_pattern"]).search("see L1-BRW-001."))

    def test_nodes(self):
        for n in self.data["nodes"]:
            self.assertTrue({"id", "kind", "title", "fields"} <= set(n), n["id"])
            self.assertIn(n["kind"], self.data["meta"]["kinds"])
            if n["kind"] in ("req", "asm"):
                self.assertTrue({"level", "section", "file", "line", "status"} <= set(n), n["id"])
                self.assertIn(n["level"], self.data["meta"]["levels"])
                self.assertIn({"level": n["level"], "section": n["section"]}, self.data["sections"])
        by = {n["id"]: n for n in self.data["nodes"]}
        self.assertEqual(by["L1-BRW-001"]["type"], "Functional")
        self.assertEqual(by["L1-BRW-001"]["file"], "requirements/L1.md")
        self.assertNotIn("type", by["L0-ASM-001"])
        self.assertEqual(by["L0-ASM-001"]["title"], "The machine is used on a 230 V single-phase mains supply.")
        self.assertEqual(by["L2-GRD-002"]["section"], "General")
        self.assertEqual(by["PRM-001"]["fields"]["Unit"], "degC")
        self.assertEqual(by["SC-001"]["fields"]["Needs exercised"], "N-001, N-002")
        self.assertEqual(len(self.data["nodes"]), 27)

    def test_one_placeholder(self):
        missing = [n for n in self.data["nodes"] if n.get("missing")]
        self.assertEqual([(n["id"], n["kind"], n["status"]) for n in missing],
                         [("PRM-099", "param", "not in database")])
        self.assertTrue(all(e["from"] in {n["id"] for n in self.data["nodes"]} for e in self.data["edges"]))

    def test_edges(self):
        kinds = {e["kind"] for e in self.data["edges"]}
        self.assertEqual(kinds, {"parent", "derived", "uses", "source", "refers", "affects",
                                 "stakeholder", "exercises"})
        pairs = {(e["from"], e["to"], e["kind"]) for e in self.data["edges"]}
        for edge in [("L0-SYS-001", "L1-BRW-001", "parent"), ("DD-001", "L1-HTR-001", "derived"),
                     ("L1-BRW-001", "PRM-001", "uses"), ("L1-BRW-001", "N-001", "source"),
                     ("L1-BRW-001", "L1-HTR-001", "refers"), ("L0-ASM-001", "L1-HTR-001", "affects"),
                     ("N-001", "SH-01", "stakeholder"), ("SC-001", "N-002", "exercises")]:
            self.assertIn(edge, pairs)
        self.assertEqual(len(self.data["edges"]), 38)
        self.assertNotIn(("L0-SYS-001", "PRM-002", "refers"), pairs)    # a parameter is not a plain reference
        self.assertNotIn(("L1-HTR-001", "DD-001", "refers"), pairs)     # the derived target is skipped
        self.assertNotIn(("L1-BRW-001", "L0-SYS-001", "refers"), pairs)  # so is a parent
        self.assertFalse(any(e["from"] == e["to"] for e in self.data["edges"]))

    def test_sections_in_file_order(self):
        self.assertEqual([(s["level"], s["section"]) for s in self.data["sections"]],
                         [("L0", "PURPOSE"), ("L0", "SAFETY"), ("L1", "BREWING"), ("L1", "HEATING"),
                          ("L1", "INTERFACE"), ("L2", "HEATER"), ("L2", "GRINDER"), ("L2", "General")])

    def test_sample_only_finding_is_its_deliberate_dangling_parameter(self):
        f, = self.data["findings"].pop("L1-HTR-002")
        self.assertEqual((f["code"], f["severity"]), ("DANGLING_REF", "warning"))
        self.assertIn("PRM-099", f["message"])
        self.assertEqual((self.data["findings"], self.data["problems"]), ({}, []))

    def test_merge_added_fields_to_headings(self):
        by = {n["id"]: n for n in self.data["nodes"]}
        self.assertEqual(by["SC-002"]["fields"], {"Needs exercised": "N-004", "Modes": "Service"})
        self.assertNotIn("SC-009", by)


class GraphRulesTest(ProjectCase):
    def test_levels_sort_naturally(self):
        files = {f"requirements/{n}.md": req(f"X-{i}") for i, n in enumerate(["L10", "L2", "L1"])}
        data = self.build(files)
        self.assertEqual(data["meta"]["levels"], ["L1", "L2", "L10"])

    def test_records_outside_sections_keep_their_place(self):
        data = self.build({"requirements/L0.md": req("A-1")})
        self.assertEqual(data["sections"], [{"level": "L0", "section": "General"}])
        self.assertEqual(self.node(data, "A-1")["section"], "General")

    def test_level_field_differing_from_file(self):
        text = ("<!-- BEGIN SECTION S -->\n" + req("A-1", Level="L3") + req("A-2", Level="L0")
                + "<!-- END SECTION S -->\n")
        data = self.build({"requirements/L0.md": text})
        self.assertEqual(self.node(data, "A-1")["level"], "L3")
        self.assertEqual(self.node(data, "A-2")["level"], "L0")
        self.assertIn({"level": "L3", "section": "S"}, data["sections"])
        self.assertEqual(data["meta"]["levels"], ["L0", "L3"])

    def test_level_role_off_uses_file_level(self):
        data = self.build({"requirements/L1.md": req("A-1", Level="L9")}, '[fields]\nlevel = ""')
        self.assertEqual(self.node(data, "A-1")["level"], "L1")

    def test_new_level_is_placed_by_natural_order(self):
        data = self.build({"requirements/L2.md": req("A-1", Level="L10") + req("A-2")})
        self.assertEqual(data["meta"]["levels"], ["L2", "L10"])

    def test_duplicate_id_keeps_the_first(self):
        files = {"requirements/L0.md": req("A-1", Status="first", **{P: "B-1"}),
                 "requirements/L1.md": req("A-1", Status="second", **{P: "C-1"})}
        data = self.build(files)
        self.assertEqual([n["id"] for n in data["nodes"] if n["kind"] == "req"], ["A-1"])
        self.assertEqual(self.node(data, "A-1")["status"], "first")
        self.assertEqual(self.edges(data, "parent"), {("B-1", "A-1")})

    def test_duplicate_between_record_and_source_keeps_the_record(self):
        toml = '[[sources]]\ntype="table"\nkind="need"\nfile="n.md"\nid="A-\\\\d"\ntitle=1'
        data = self.build({"requirements/L0.md": req("A-1"), "n.md": "| A-1 | table title |\n"}, toml)
        self.assertEqual(self.node(data, "A-1")["kind"], "req")
        self.assertEqual(len(data["nodes"]), 1)

    def test_parents_and_none_value(self):
        files = {"requirements/L0.md": req("A-2", **{P: "A-1, A-3 and not an id"}) + req("A-4", **{P: "TBD-1"})}
        data = self.build(files)
        self.assertEqual(self.edges(data, "parent"), {("A-1", "A-2"), ("A-3", "A-2"), ("TBD-1", "A-4")})
        data = self.build(files, '[links]\nnone_value = "TBD-1"')
        self.assertEqual(self.edges(data, "parent"), {("A-1", "A-2"), ("A-3", "A-2")})

    def test_parents_role_off(self):
        data = self.build({"requirements/L0.md": req("A-1", **{P: "A-2"})}, '[fields]\nparents = ""')
        self.assertEqual(self.edges(data, "parent"), set())

    def test_derived_pattern(self):
        files = {"requirements/L0.md": req("A-1", **{P: "Derived (DD-1)"}, Rationale="Because of DD-1 and DD-2")}
        data = self.build(files, '[links]\nderived_pattern = "Derived \\\\((DD-\\\\d)\\\\)"')
        self.assertEqual(self.edges(data, "derived"), {("DD-1", "A-1")})
        self.assertEqual(self.edges(data, "parent"), set())
        self.assertEqual(self.edges(data, "refers"), {("A-1", "DD-2")})
        self.assertEqual(self.node(data, "DD-1")["kind"], "missing")

    def test_optional_groups_that_stay_unset_are_problems_not_nodes(self):
        toml = r"""[links]
derived_pattern = 'Derived \((D-\d)?\)'
uses_pattern = '(PRM-\d)?x'
uses_fields = ["Parameters"]
"""
        data = self.build({"requirements/L0.md": req("A-1", **{P: "Derived ()"}, Parameters="x")}, toml)
        self.assertEqual(self.edges(data, "derived") | self.edges(data, "uses"), set())
        self.assertEqual(len(data["problems"]), 2)
        self.assertIn("links.derived_pattern", data["problems"][0])
        self.assertEqual([n["id"] for n in data["nodes"]], ["A-1"])

    def test_without_derived_pattern_nothing_is_derived(self):
        data = self.build({"requirements/L0.md": req("A-1", **{P: "Derived (DD-1)"})})
        self.assertEqual(self.edges(data, "derived"), set())
        self.assertEqual(self.edges(data, "parent"), {("DD-1", "A-1")})

    def test_refers_skips_parents_and_uses_and_source(self):
        fields = {P: "A-1", "Source": "S-1", "Parameters": "PRM-1", "Rationale": "A-1 S-1 PRM-1 PRM-2 A-9",
                  "Verification": "see B-7"}
        toml = REFS + '[links]\nuses_pattern = "PRM-\\\\d"\nuses_fields = ["Parameters"]'
        data = self.build({"requirements/L0.md": req("A-2", **fields)}, toml)
        self.assertEqual(self.edges(data, "refers"), {("A-2", "S-1"), ("A-2", "A-9"), ("A-2", "B-7")})
        self.assertEqual(self.edges(data, "uses"), {("A-2", "PRM-1")})
        self.assertEqual(self.edges(data, "source"), {("A-2", "S-1")})

    def test_refer_fields_limit_the_text_searched(self):
        fields = {"Rationale": "see A-9", "Verification": "see B-7"}
        data = self.build({"requirements/L0.md": req("A-2", **fields)}, '[links]\nrefer_fields = ["Verification"]')
        self.assertEqual(self.edges(data, "refers"), {("A-2", "B-7")})

    def test_assumption_affects(self):
        text = "```asm\nID: A-1\nAssumption: x\nAffects: B-1 and B-2\nRationale: B-3\nStatus: Open\n```\n"
        data = self.build({"requirements/L0.md": text}, '[links]\naffects_fields = ["Affects"]')
        self.assertEqual(self.edges(data, "affects"), {("A-1", "B-1"), ("A-1", "B-2")})
        self.assertEqual(self.node(data, "A-1")["status"], "Open")

    def test_placeholders(self):
        toml = ('[links]\nuses_pattern = "PRM-\\\\d"\nuses_fields = ["Parameters"]\n'
                '[[sources]]\ntype="yaml"\nkind="param"\nfile="p.yaml"')
        files = {"requirements/L0.md": req("A-1", Parameters="PRM-1", Rationale="B-2"), "p.yaml": "- {id: PRM-9}\n"}
        data = self.build(files, toml)
        self.assertEqual((self.node(data, "PRM-1")["kind"], self.node(data, "PRM-1")["status"]),
                         ("param", "not in database"))
        self.assertEqual((self.node(data, "B-2")["kind"], self.node(data, "B-2")["status"]),
                         ("missing", "not found"))
        self.assertTrue(self.node(data, "B-2")["missing"] and self.node(data, "PRM-1")["missing"])
        self.assertEqual(self.node(data, "B-2")["fields"], {})

    def test_uses_placeholder_without_yaml_source_is_missing(self):
        toml = '[links]\nuses_pattern = "PRM-\\\\d"\nuses_fields = ["Parameters"]'
        data = self.build({"requirements/L0.md": req("A-1", Parameters="PRM-1")}, toml)
        self.assertEqual(self.node(data, "PRM-1")["kind"], "missing")
        self.assertEqual(self.node(data, "PRM-1")["status"], "not in database")

    def test_edges_are_not_repeated(self):
        data = self.build({"requirements/L0.md": req("A-1", Rationale="B-1 B-1 B-1", **{P: "B-2, B-2"})})
        self.assertEqual(len(data["edges"]), 2)

    def test_merge_does_not_create_nodes_and_comes_last(self):
        toml = ('[[sources]]\ntype="table"\nkind="sc"\nmerge=true\nfile="t.md"\nid="SC-\\\\d"\n'
                'columns={ X = 1 }\nlinks=[{ kind = "ex", column = 1 }]\n'
                '[[sources]]\ntype="heading"\nkind="sc"\nfile="t.md"\npattern=\'^## (SC-\\d) (.*)$\'')
        text = "## SC-1 one\n| SC-1 | v |\n| SC-2 | w |\n"
        data = self.build({"t.md": text}, toml)
        self.assertEqual([n["id"] for n in data["nodes"] if n["kind"] == "sc"], ["SC-1"])
        self.assertEqual(self.node(data, "SC-1")["fields"], {"X": "v"})
        self.assertEqual(self.edges(data, "ex"), {("SC-1", "v")})

    def test_format_problems_become_findings(self):
        data = self.build({"requirements/L0.md": "```req\nStatement: no id\n```\n"})
        self.assertEqual(len(data["problems"]), 1)
        self.assertIn("requirements/L0.md:1", data["problems"][0])
        f, = data["findings"][""]
        self.assertEqual((f["severity"], f["code"]), ("error", "FORMAT"))
        self.assertIn("requirements/L0.md:1", f["message"])
        self.assertEqual(set(f), {"severity", "code", "message"})

    @needs_yaml
    def test_source_problems_are_reported(self):
        toml = '[[sources]]\ntype="yaml"\nkind="p"\nfile="p.yaml"\nlist_key="items"'
        data = self.build({"p.yaml": "items: [1]\n"}, toml)
        self.assertEqual(len(data["problems"]), 1)
        self.assertIn("p.yaml", data["problems"][0])
        self.assertEqual(len(data["findings"][""]), 1)

    def test_empty_project(self):
        data = self.build({})
        self.assertEqual((data["nodes"], data["edges"], data["sections"], data["meta"]["levels"]), ([], [], [], []))

    def test_meta_follows_the_config(self):
        toml = ('title = "Mixed  Title!"\n[display]\ndetail_rows = ["A"]\nvalue_field = "V"\n'
                '[display.kinds.req]\nlabel = "Need"\ncolor = "#123"\n'
                '[[sources]]\ntype="heading"\nkind="sc"\nlabel="Scenes"\nfile="f"\npattern="(x)"\ncolor="#abcdef"\n'
                '[[sources]]\ntype="heading"\nkind="tt"\nfile="f"\npattern="(x)"\nsingular="Tee"')
        meta = self.build({}, toml)["meta"]
        self.assertEqual(meta["storage_key"], "reqviewer.mixed-title")
        self.assertEqual((meta["detail_rows"], meta["value_field"]), (["A"], "V"))
        self.assertEqual(meta["kinds"]["req"], {"label": "Need", "group": "Requirements", "color": "#123"})
        self.assertEqual(meta["kinds"]["sc"], {"label": "Scenes", "group": "Scenes", "color": "#abcdef"})
        self.assertEqual(meta["kinds"]["tt"], {"label": "Tee", "group": "tt", "color": ""})
        self.assertEqual(list(meta["kinds"])[-1], "missing")

    def test_id_pattern_is_the_config_pattern(self):
        cfg = config.parse({"ids": {"patterns": ["A-\\d+", "B-\\d+"]}})
        self.assertEqual(graph.build(self.project({}), cfg)["meta"]["id_pattern"], config.id_regex(cfg))

    def test_graph_imports_no_checkers(self):
        text = Path(graph.__file__).read_text(encoding="utf-8")
        for name in ("lint", "trace_check", "param_check", "reqlib"):
            self.assertNotRegex(text, rf"\bimport {name}\b|\bfrom {name}\b")


if __name__ == "__main__":
    unittest.main()

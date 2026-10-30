import tomllib
import unittest

from reqviewer import config
from reqviewer.config import ConfigError
from support import SAMPLE, ProjectCase

SRC = 'type = "table"\nkind = "need"\nfile = "n.md"\nid = "N-1"\n'


def parse(toml):
    return config.parse(tomllib.loads(toml))


class ConfigTest(ProjectCase):
    def bad(self, toml, *words):
        with self.assertRaises(ConfigError) as cm:
            parse(toml)
        for w in words:
            self.assertIn(w, str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))

    def test_defaults(self):
        cfg = parse("")
        self.assertEqual(cfg, config.Config())
        self.assertEqual(cfg.title, "Requirements")
        self.assertEqual(cfg.out, "build/requirements_viewer.html")
        self.assertEqual(cfg.files.levels, ["requirements/L*.md"])
        self.assertEqual(cfg.fields.parents, "Parent(s)")
        self.assertEqual(cfg.display.kinds["req"]["label"], "Requirement")
        self.assertEqual(cfg.sources, [])

    def test_overrides(self):
        cfg = parse('title = "T"\n[fields]\nstatement = "Text"\n[display.kinds.req]\ncolor = "#abc"')
        self.assertEqual((cfg.title, cfg.fields.statement), ("T", "Text"))
        self.assertEqual(cfg.display.kinds["req"], {"label": "Requirement", "color": "#abc"})
        self.assertEqual(cfg.display.kinds["asm"], {"label": "Assumption"})

    def test_defaults_are_not_shared(self):
        parse('[display.kinds.req]\ncolor = "#abc"')
        self.assertNotIn("color", config.Config().display.kinds["req"])

    def test_unknown_keys_name_the_key(self):
        self.bad('colour = "x"', "colour")
        self.bad("[files]\nlevel = []", "files.level")
        self.bad("[fields]\nname = 'x'", "fields.name")
        self.bad("[bogus]\na = 1", "bogus")
        self.bad("[[sources]]\n" + SRC + "bogus = 1", "sources[0].bogus")
        self.bad("[[sources]]\n" + SRC + 'pattern = "x"', "sources[0].pattern")   # heading-only key
        self.bad("[[sources]]\n" + SRC + "links = [{ kind = 'a', bogus = 1 }]", "links[0].bogus")
        self.bad("[display.kinds.req]\nsize = 1", "display.kinds.req.size")

    def test_wrong_types(self):
        self.bad("title = 3", "title")
        self.bad("[files]\nlevels = 'x'", "files.levels")
        self.bad("[files]\nlevels = [1]", "files.levels")
        self.bad("[format]\nheading_must_match_id = 'yes'", "format.heading_must_match_id")
        self.bad("[[sources]]\n" + SRC + "title = true", "sources[0].title")

    def test_bad_regex_names_the_key(self):
        self.bad("[ids]\npatterns = ['(']", "ids.patterns[0]", "regular expression")
        self.bad("[links]\nuses_pattern = '['", "links.uses_pattern")
        self.bad("[display]\nlabel_strip = '('", "display.label_strip")
        self.bad("[[sources]]\n" + SRC.replace("N-1", "("), "sources[0].id")
        self.bad("[[sources]]\n" + SRC + "require = { 1 = '(' }", "sources[0].require.1")
        self.bad("[[sources]]\n" + SRC + "links = [{ kind = 'a', pattern = '(' }]", "links[0].pattern")

    def test_javascript_incompatible_regex(self):
        for p in ("(?i)abc", "(?P<x>a)", "(?P<x>a)(?P=x)", "(?i:a)", "(?>a)"):
            with self.subTest(p):
                self.bad(f"[ids]\npatterns = ['{p}']", "ids.patterns[0]", "JavaScript")
        self.bad("[links]\nuses_pattern = '(?i)p'", "links.uses_pattern", "JavaScript")
        self.bad("[[sources]]\n" + SRC.replace("N-1", "(?i)n"), "sources[0].id", "JavaScript")
        parse(r"[ids]" + "\npatterns = ['(?<![A-Z])(?:A|B)-\\d+', '(?=x)y']")   # lookarounds are fine

    def test_empty_id_patterns(self):
        self.bad("[ids]\npatterns = []", "ids.patterns")

    def test_level_pattern_needs_one_group(self):
        self.bad("[files]\nlevel_pattern = '^L\\d+'", "files.level_pattern")
        self.bad("[files]\nlevel_pattern = '^(L)(\\d+)'", "files.level_pattern")

    def test_derived_pattern_needs_a_group(self):
        self.bad("[links]\nderived_pattern = 'Derived'", "links.derived_pattern")

    def test_colours(self):
        for good in ("#abc", "#A1b2C3"):
            parse(f'[display.kinds.req]\ncolor = "{good}"')
        for bad in ("red", "#abcd", "#12", "abc", 'x" onclick="'):
            with self.subTest(bad):
                self.bad(f"[display.kinds.req]\ncolor = '{bad}'", "display.kinds.req.color")
        self.bad("[[sources]]\n" + SRC + "color = 'red'", "sources[0].color")
        self.bad('[display.kinds.req]\ncolor = "#abc\\n"', "display.kinds.req.color")   # no trailing newline

    def test_javascript_syntax_the_first_check_missed(self):
        for p in ("(?#c)", r"\d++", "a*+", "a?+", "a{2}+", "(a)(?(1)b|c)"):
            with self.subTest(p):
                self.bad(f"[ids]\npatterns = ['{p}']", "ids.patterns[0]", "JavaScript")

    def test_escaped_and_bracketed_syntax_is_not_rejected(self):
        for p in (r"\(?P<x", r"\\\(?P<x", "[(?P<]", r"a\++", "[*+]+", r"\(\?i\)"):
            with self.subTest(p):
                parse(f"[ids]\npatterns = ['{p}']")

    def test_malformed_values_give_config_errors(self):
        cases = [("[[sources]]\ntype = ['table']", "sources[0].type"),
                 ("[[sources]]\ntype = {a = 1}", "sources[0].type"),
                 ("[ids]\npatterns = ['A{99999999999}']", "ids.patterns[0]"),
                 ("[files]\nlevel_pattern = '(A{99999999999})'", "files.level_pattern"),
                 ("[files]\nlevels = ['/x/*.md']", "files.levels[0]"),
                 ("[files]\nlevels = ['C:/x/*.md']", "files.levels[0]"),
                 ("[files]\nlevels = ['']", "files.levels[0]"),
                 ("[files]\nlevels = ['a**b/*.md']", "files.levels[0]"),
                 ("[ids]\npatterns = ['']", "ids.patterns[0]"),
                 ("[ids]\npatterns = ['A-1', 'Z*']", "ids.patterns[1]"),
                 ("[links]\nuses_pattern = 'Z*'", "links.uses_pattern"),
                 ("[links]\nderived_pattern = '(Z)*'", "links.derived_pattern"),
                 ("[[sources]]\n" + SRC + "title_max = -1", "sources[0].title_max"),
                 ("[[sources]]\n" + SRC.replace("N-1", ".*"), "sources[0].id"),
                 ("[[sources]]\n" + SRC + "links = [{ kind = '' }]", "links[0].kind"),
                 ("[ids]\npatterns = ['" + "(" * 5000 + "']", "ids.patterns[0]")]
        for toml, key in cases:
            with self.subTest(toml[:60]):
                self.bad(toml, key)

    def test_deeply_nested_toml_is_a_config_error(self):
        root = self.project({"reqviewer.toml": "a = " + "[" * 5000 + "]" * 5000})
        with self.assertRaises(ConfigError):
            config.load_config(root)

    def test_reserved_kinds(self):
        for kind in ("req", "asm", "missing"):
            with self.subTest(kind):
                self.bad("[[sources]]\n" + SRC.replace('"need"', f'"{kind}"'), "sources[0].kind", "reserved")

    def test_unknown_kind_in_display(self):
        self.bad("[display.kinds.nope]\nlabel = 'x'", "display.kinds.nope")

    def test_source_required_keys_and_type(self):
        self.bad('[[sources]]\ntype = "csv"\nkind = "a"\nfile = "f"', "sources[0].type")
        self.bad('[[sources]]\ntype = "heading"\nkind = "a"\nfile = "f"', "sources[0].pattern")
        self.bad('[[sources]]\ntype = "heading"\nkind = "a"\nfile = "f"\npattern = "x"', "sources[0].pattern", "group")
        self.bad('[[sources]]\ntype = "yaml"\nfile = "f"', "sources[0].kind")
        self.bad('[[sources]]\ntype = "table"\nkind = "a"\nid = "x"', "sources[0].file")
        self.bad("[[sources]]\n" + SRC + "links = [{ column = 1 }]", "links[0].kind")
        self.bad("[[sources]]\n" + SRC + "require = { x = 'a' }", "require.x")
        self.bad("[[sources]]\n" + SRC + "[[sources]]\ntype = 'yaml'", "sources[1].kind")

    def test_unknown_loader(self):
        self.bad('loader = "xml"', "loader", "xml")

    def test_loaders_table(self):
        self.assertIn("markdown", config.LOADERS)

    def test_table_source_keys_are_converted(self):
        src = parse("[[sources]]\n" + SRC + "require = { 1 = '^S' }\ncolumns = { A = 2 }").sources[0]
        self.assertEqual((src.require, src.columns), ({1: "^S"}, {"A": 2}))

    def test_id_regex(self):
        cfg = parse("[ids]\npatterns = ['A-\\d+', 'B-\\d+']")
        self.assertEqual(config.id_regex(cfg), r"(?<![\w-])(?:A-\d+|B-\d+)\b")

    def test_sample_config_loads(self):
        cfg = config.load_config(SAMPLE)
        self.assertEqual(cfg.title, "BrewBox requirements")
        self.assertEqual([s.kind for s in cfg.sources],
                         ["stakeholder", "need", "decision", "scenario", "scenario", "param"])

    def test_load_config_files(self):
        root = self.project({"reqviewer.toml": 'title = "A"', "other.toml": 'title = "B"', "bad.toml": "title ="})
        self.assertEqual(config.load_config(root).title, "A")
        self.assertEqual(config.load_config(root, root / "other.toml").title, "B")
        with self.assertRaises(ConfigError) as cm:
            config.load_config(root, root / "bad.toml")
        self.assertIn("bad.toml", str(cm.exception))
        with self.assertRaises(ConfigError):
            config.load_config(root, root / "missing.toml")

    def test_utf8_bom_is_ignored(self):
        root = self.project({"reqviewer.toml": '﻿title = "A"'})
        self.assertEqual(config.load_config(root).title, "A")

    def test_no_config_file_gives_defaults(self):
        self.assertEqual(config.load_config(self.project({})), config.Config())

    def test_error_names_the_file(self):
        root = self.project({"reqviewer.toml": "bogus = 1"})
        with self.assertRaises(ConfigError) as cm:
            config.load_config(root)
        self.assertIn("reqviewer.toml", str(cm.exception))
        self.assertIn("bogus", str(cm.exception))

    def test_undecodable_config(self):
        root = self.project({})
        (root / "reqviewer.toml").write_bytes(b"\xff\xfe=")
        with self.assertRaises(ConfigError):
            config.load_config(root)


if __name__ == "__main__":
    unittest.main()

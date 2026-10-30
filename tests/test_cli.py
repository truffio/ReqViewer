import contextlib
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

from reqviewer import cli
from support import ROOT, SAMPLE, ProjectCase, req


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class CliTest(ProjectCase):
    def assert_error(self, code, err, *words):
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertTrue(err.startswith("reqviewer: error: "))
        self.assertNotIn("Traceback", err)
        for w in words:
            self.assertIn(w, err)

    def test_sample_writes_the_configured_page(self):
        root = self.project({})
        code, out, err = run("--root", SAMPLE, "--out", root / "page.html")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue((root / "page.html").is_file())
        self.assertIn("page.html", out)
        self.assertIn("13 record(s), 27 node(s), 38 link(s)", out)

    def test_runs_with_no_config(self):
        root = self.project({"requirements/L0.md": req("A-1") + req("A-2", **{"Parent(s)": "A-1"})})
        code, out, err = run("--root", root)
        self.assertEqual((code, err), (0, ""))
        self.assertTrue((root / "build" / "requirements_viewer.html").is_file())
        self.assertIn("2 record(s), 2 node(s), 1 link(s)", out)

    def test_out_defaults_to_config_relative_to_root(self):
        root = self.project({"reqviewer.toml": 'out = "site/index.html"'})
        self.assertEqual(run("--root", root)[0], 0)
        self.assertTrue((root / "site" / "index.html").is_file())

    def test_explicit_config(self):
        root = self.project({"other.toml": 'out = "x.html"'})
        self.assertEqual(run("--root", root, "--config", root / "other.toml")[0], 0)
        self.assertTrue((root / "x.html").is_file())

    def test_empty_project_still_writes(self):
        root = self.project({})
        self.assertEqual(run("--root", root)[0], 0)

    def test_bad_config_exits_2_naming_the_key(self):
        root = self.project({"reqviewer.toml": "[files]\nlevel = 1"})
        code, out, err = run("--root", root)
        self.assert_error(code, err, "files.level")
        self.assertEqual(out, "")
        self.assertFalse((root / "build").exists())

    def test_each_kind_of_bad_config(self):
        for toml, key in [("[ids]\npatterns = ['(']", "ids.patterns[0]"),
                          ("[ids]\npatterns = ['(?i)a']", "ids.patterns[0]"),
                          ("[display.kinds.req]\ncolor = 'red'", "display.kinds.req.color"),
                          ("[[sources]]\ntype='yaml'\nkind='req'\nfile='f'", "sources[0].kind"),
                          ("title = ", "reqviewer.toml")]:
            with self.subTest(toml):
                code, _, err = run("--root", self.project({"reqviewer.toml": toml}))
                self.assert_error(code, err, key)

    def test_missing_explicit_config(self):
        root = self.project({})
        code, _, err = run("--root", root, "--config", root / "nope.toml")
        self.assert_error(code, err, "nope.toml")

    def test_missing_root(self):
        root = self.project({})
        code, _, err = run("--root", root / "nope")
        self.assert_error(code, err, "nope")

    def test_findings_option_merges_external_findings(self):
        good = '[{"item": "", "severity": "warning", "code": "X", "message": "m"}]'
        root = self.project({"f.json": good})
        code, _, err = run("--root", root, "--findings", root / "f.json", "--out", root / "p.html")
        self.assertEqual((code, err), (0, ""))
        self.assertIn('"code": "X"', (root / "p.html").read_text(encoding="utf-8"))

    def test_findings_option_bad_file(self):
        item = '{"item": "", "severity": "%s", "code": "X", "message": "m"}'
        cases = {"nope": "nope.json", "{": "cannot read", '{"a": 1}': "JSON list", "[1]": "entry 1",
                 "[{}]": "'item'", "[" + item % "info" + "]": "severity"}
        for text, word in cases.items():
            with self.subTest(text):
                root = self.project({} if text == "nope" else {"f.json": text})
                name = "nope.json" if text == "nope" else "f.json"
                code, _, err = run("--root", root, "--findings", root / name)
                self.assert_error(code, err, word)

    def test_unwritable_output(self):
        root = self.project({"blocker": ""})
        code, _, err = run("--root", root, "--out", root / "blocker" / "x.html")
        self.assert_error(code, err)

    def test_bad_arguments_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as cm:
            cli.main(["--nope"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("usage: reqviewer", err.getvalue())

    def test_malformed_values_give_one_line_and_exit_2(self):
        for toml in ["[[sources]]\ntype = ['table']", "[ids]\npatterns = ['A{99999999999}']",
                     "[files]\nlevels = ['/x/*.md']", "[files]\nlevels = ['']", "[files]\nlevels = ['a**b/*.md']",
                     "[links]\nuses_pattern = 'Z*'", 'out = "a\\u0000b"', "a = " + "[" * 5000 + "]" * 5000]:
            with self.subTest(toml[:40]):
                code, out, err = run("--root", self.project({"reqviewer.toml": toml}))
                self.assert_error(code, err)
                self.assertEqual(out, "")

    def test_deeply_nested_findings_file(self):
        root = self.project({"f.json": "[" * 5000 + "]" * 5000})
        code, _, err = run("--root", root, "--findings", root / "f.json")
        self.assert_error(code, err, "f.json")

    def test_a_defect_is_one_line_not_a_traceback(self):
        with mock.patch.object(cli.graph, "build", side_effect=KeyError("boom")):
            code, out, err = run("--root", self.project({}))
        self.assert_error(code, err, "KeyError", "boom")

    def test_output_path_the_console_cannot_encode(self):
        root = self.project({})
        done = subprocess.run([sys.executable, "-m", "reqviewer", "--root", str(root), "--out",
                               str(root / "日本語.html")], cwd=ROOT, capture_output=True, text=True,
                              env={**os.environ, "PYTHONIOENCODING": "ascii"})
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertTrue((root / "日本語.html").is_file())

    def test_python_dash_m(self):
        root = self.project({})
        done = subprocess.run([sys.executable, "-m", "reqviewer", "--root", str(SAMPLE), "--out",
                               str(root / "p.html")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((root / "p.html").is_file())


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import subprocess
import sys
import unittest

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

    def test_findings_option_is_not_implemented(self):
        root = self.project({"f.json": "[]"})
        code, _, err = run("--root", root, "--findings", root / "f.json")
        self.assert_error(code, err, "not implemented")

    def test_unwritable_output(self):
        root = self.project({"blocker": ""})
        code, _, err = run("--root", root, "--out", root / "blocker" / "x.html")
        self.assert_error(code, err)

    def test_bad_arguments_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as cm:
            cli.main(["--nope"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("usage: reqviewer", err.getvalue())

    def test_python_dash_m(self):
        root = self.project({})
        done = subprocess.run([sys.executable, "-m", "reqviewer", "--root", str(SAMPLE), "--out",
                               str(root / "p.html")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((root / "p.html").is_file())


if __name__ == "__main__":
    unittest.main()

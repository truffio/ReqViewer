import json
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from reqviewer import config, graph

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False
needs_yaml = unittest.skipUnless(HAVE_YAML, "PyYAML is not installed")

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample"


def payload(page):
    """The data a rendered page carries: the JSON text inside the JSON.parse string literal."""
    literal = re.search(r'^const DATA = JSON\.parse\((".*")\);$', page, re.M).group(1)
    return json.loads(json.loads(literal))


def block(fields, kind="req"):
    """A fenced record from a dict of fields."""
    return f"```{kind}\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + "```\n"


def req(rid, **extra):
    fields = {"ID": rid, "Statement": f"The thing shall {rid}.", **extra}
    return block(fields)


class ProjectCase(unittest.TestCase):
    def project(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def build(self, files, toml=""):
        root = self.project(files)
        return graph.build(root, config.parse(tomllib.loads(toml)))

    def node(self, data, nid):
        return next(n for n in data["nodes"] if n["id"] == nid)

    def edges(self, data, kind=None):
        return {(e["from"], e["to"]) for e in data["edges"] if kind in (None, e["kind"])}

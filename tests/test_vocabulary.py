import re
import unittest

from support import ROOT

# built from pieces so that this file does not contain the words itself
WORDS = ["aero" + "nef", "air" + "craft", "L1-" + "AER", "CON" + "OPS", "P-" + "SYS"]


class VocabularyTest(unittest.TestCase):
    def hits(self, paths):
        rx = re.compile("|".join(map(re.escape, WORDS)), re.I)
        return [f"{p.relative_to(ROOT)}:{n}" for p in paths
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if rx.search(line)]

    def test_no_project_vocabulary_in_code_and_tests(self):
        files = [*(ROOT / "reqviewer").glob("*.py"), *(ROOT / "tests").glob("*.py")]
        self.assertGreater(len(files), 8)
        self.assertEqual(self.hits(files), [])

    def test_no_project_vocabulary_in_the_template(self):
        self.assertEqual(self.hits([ROOT / "reqviewer" / "template.html"]), [])


if __name__ == "__main__":
    unittest.main()

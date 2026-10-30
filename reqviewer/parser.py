"""Shared parser for the Aeronef requirement level files.

Reads `requirements/L*.md` (or any draft file with the same record format) and
returns requirement records, assumption records, sections and parameters.
Format: see templates/REQUIREMENT.md.
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQ_FIELDS = [
    "ID", "Level", "Type", "Statement", "Rationale", "Parent(s)", "Source",
    "Allocated to", "Criticality", "Verification", "Parameters", "TBD/TBR",
    "Owner", "Status", "Version",
]
ASM_FIELDS = ["ID", "Assumption", "Rationale", "Affects", "Owner", "Status"]

BEGIN_RE = re.compile(r"^<!--\s*BEGIN SECTION ([A-Za-z0-9_-]+)\s*-->\s*$")
END_RE = re.compile(r"^<!--\s*END SECTION ([A-Za-z0-9_-]+)\s*-->\s*$")
FENCE_RE = re.compile(r"^```(req|asm)\s*$")
FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z()/ ]*?):\s*(.*)$")
FILE_LEVEL_RE = re.compile(r"^(L\d+)(?:_|\.md$)")
PARAM_REF_RE = re.compile(r"P-[A-Z]+-\d+")
DASH = "—"  # em dash, "not applicable"


# ---------------------------------------------------------------- findings

@dataclass(order=True)
class Finding:
    file: str
    line: int
    severity: str          # "error" or "warning"
    code: str
    item: str              # requirement / parameter ID, or ""
    message: str
    section: str = ""

    def __str__(self):
        who = f" {self.item}:" if self.item else ""
        return f"{self.file}:{self.line}: {self.severity} [{self.code}]{who} {self.message}"


def report(findings, strict=False, out=None):
    """Print findings and a summary line. Return the process exit code.

    Errors always give exit code 1; warnings only with strict=True."""
    out = out or sys.stdout
    for f in sorted(findings):
        print(f, file=out)
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = len(findings) - errors
    print(f"{errors} error(s), {warnings} warning(s)", file=out)
    return 1 if errors or (strict and warnings) else 0


def add_common_args(parser):
    parser.add_argument("--root", type=Path, default=REPO_ROOT,
                        help="repository root (default: the repo containing tools/)")
    parser.add_argument("--strict", action="store_true",
                        help="exit nonzero on warnings too")


# ------------------------------------------------------------------ records

@dataclass
class Record:
    kind: str                      # "req" or "asm"
    file: Path
    line: int                      # line of the opening fence
    section: str
    file_level: str                # level taken from the file name, e.g. "L2"
    fields: dict = field(default_factory=dict)
    field_lines: dict = field(default_factory=dict)
    heading: str = ""
    heading_line: int = 0

    @property
    def id(self):
        return self.fields.get("ID", "")

    def get(self, name):
        return self.fields.get(name, "")

    def where(self, name=None):
        return self.field_lines.get(name, self.line) if name else self.line


@dataclass
class ParsedFile:
    path: Path
    records: list = field(default_factory=list)       # kind == "req"
    assumptions: list = field(default_factory=list)   # kind == "asm"
    problems: list = field(default_factory=list)      # Finding objects


def file_level(path):
    m = FILE_LEVEL_RE.match(Path(path).name)
    return m.group(1) if m else ""


def draft_section(path):
    """Section name from a draft file name `<level>_<SECTION>.md`, else ''."""
    m = re.match(r"^L\d+_(.+)\.md$", Path(path).name)
    return m.group(1) if m else ""


def parse_text(text, path):
    path = Path(path)
    pf = ParsedFile(path)
    lines = text.splitlines()
    level = file_level(path)
    section = draft_section(path)
    heading, heading_line = "", 0
    i = 0

    def problem(line, msg):
        pf.problems.append(Finding(str(path), line, "error", "FORMAT", "", msg, section))

    while i < len(lines):
        line = lines[i]
        if BEGIN_RE.match(line):
            section = BEGIN_RE.match(line).group(1)
        elif END_RE.match(line):
            section = draft_section(path)
        elif line.startswith("### "):
            heading, heading_line = line[4:].strip(), i + 1
        elif FENCE_RE.match(line):
            kind, start = FENCE_RE.match(line).group(1), i + 1
            body = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                body.append((i + 1, lines[i]))
                i += 1
            if i >= len(lines):
                problem(start, f"unclosed ```{kind} block")
            rec = Record(kind, path, start, section, level,
                         heading=heading, heading_line=heading_line)
            _parse_block(rec, body, problem)
            (pf.records if kind == "req" else pf.assumptions).append(rec)
            heading, heading_line = "", 0
        i += 1
    return pf


def _parse_block(rec, body, problem):
    known = REQ_FIELDS if rec.kind == "req" else ASM_FIELDS
    current = None
    for lineno, line in body:
        if not line.strip():
            continue
        if line[0] in " \t":                      # continuation line
            if current is None:
                problem(lineno, "indented line before any field")
            else:
                rec.fields[current] = (rec.fields[current] + " " + line.strip()).strip()
            continue
        m = FIELD_RE.match(line)
        if not m:
            problem(lineno, f"not a 'Field: value' line: {line.strip()[:40]!r}")
            current = None
            continue
        name, value = m.group(1).strip(), m.group(2).strip()
        if name not in known:
            problem(lineno, f"unknown field {name!r}")
            current = None
        elif name in rec.fields:
            problem(lineno, f"duplicate field {name!r}")
            current = None
        else:
            rec.fields[name] = value
            rec.field_lines[name] = lineno
            current = name
    if not rec.fields.get("ID"):
        problem(rec.line, f"```{rec.kind} block has no ID")
    elif rec.heading and rec.heading != rec.fields["ID"]:
        problem(rec.heading_line,
                f"heading {rec.heading!r} does not match ID {rec.fields['ID']!r}")


def level_files(root):
    """requirements/L*.md sorted by level number."""
    files = list((Path(root) / "requirements").glob("L[0-9]*.md"))
    return sorted(files, key=lambda p: int(re.match(r"L(\d+)", p.name).group(1)))


def resolve_file(root, name):
    # a relative name is looked up under root first, then the working directory
    p = Path(name)
    under_root = Path(root) / p
    return under_root if not p.is_absolute() and under_root.exists() else p


@dataclass
class Repo:
    root: Path
    records: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def load_repo(root, file=None, section=None):
    """Parse all level files (or just `file`), optionally keeping one section."""
    repo = Repo(Path(root))
    paths = [resolve_file(root, file)] if file else level_files(root)
    for p in paths:
        if not p.exists():
            repo.problems.append(Finding(str(p), 0, "error", "FORMAT", "", "file not found"))
            continue
        pf = parse_text(p.read_text(encoding="utf-8"), p)
        repo.problems += pf.problems
        repo.records += pf.records
        repo.assumptions += pf.assumptions
    if section:
        repo.records = [r for r in repo.records if r.section == section]
        repo.assumptions = [r for r in repo.assumptions if r.section == section]
        repo.problems = [p for p in repo.problems if p.section == section]
    return repo


# ------------------------------------------------------------------ sections

def find_sections(text):
    """Return ({name: (begin_index, end_index)}, problems) over the text lines.

    Indexes are 0-based line numbers of the BEGIN and END marker lines;
    problems is a list of (line_number, message)."""
    lines = text.splitlines()
    found, problems, open_name, open_at = {}, [], None, 0
    for i, line in enumerate(lines):
        b, e = BEGIN_RE.match(line), END_RE.match(line)
        if b:
            if open_name:
                problems.append((i + 1, f"section {b.group(1)} begins inside {open_name}"))
            if b.group(1) in found:
                problems.append((i + 1, f"duplicate section {b.group(1)}"))
            open_name, open_at = b.group(1), i
        elif e:
            if e.group(1) != open_name:
                problems.append((i + 1, f"END SECTION {e.group(1)} without matching BEGIN"))
            else:
                found[open_name] = (open_at, i)
            open_name = None
    if open_name:
        problems.append((open_at + 1, f"section {open_name} has no END marker"))
    return found, problems


# ---------------------------------------------------------------- parameters

def load_parameters(root):
    """Return (list of parameter dicts, problems)."""
    import yaml
    path = Path(root) / "parameters" / "PARAMETERS.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [], [Finding(str(path), 0, "error", "YAML", "", f"cannot read: {exc}")]
    params = data.get("parameters") if isinstance(data, dict) else None
    if params is None:
        params = []
    if not isinstance(params, list):
        return [], [Finding(str(path), 0, "error", "YAML", "", "'parameters' must be a list")]
    out, problems = [], []
    for n, p in enumerate(params, 1):
        if isinstance(p, dict):
            out.append(p)
        else:
            problems.append(Finding(str(path), 0, "error", "YAML", "",
                                    f"entry {n} is not a mapping"))
    return out, problems


def param_refs(text):
    return PARAM_REF_RE.findall(text or "")


def table_ids(path, prefix):
    """IDs (first table cell) in a Markdown register, e.g. DD-001."""
    ids = set()
    p = Path(path)
    if not p.exists():
        return ids
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("|"):
            cell = line.strip("| ").split("|")[0].strip()
            if re.fullmatch(prefix + r"-\d+", cell):
                ids.add(cell)
    return ids


# ---------------------------------------------------------------- verification

def split_verification(value):
    """'Test — TP-001; success criteria: x' -> (method, procedure, criteria).

    Missing parts are returned as ''."""
    head, sep, rest = value.partition(DASH)
    if not sep:
        head, sep, rest = value.partition(" - ")
    proc, _, crit = rest.partition("success criteria:")
    return head.strip(), proc.strip().rstrip(";").strip(), crit.strip()


def parent_ids(value):
    """IDs listed in a Parent(s) value; none for 'Derived (DD-nnn)' or the dash."""
    if value.strip().startswith("Derived"):
        return []
    return [t for t in re.split(r"[,;\s]+", value) if t and t != DASH]


def derived_dd(value):
    m = re.match(r"^Derived\s*\(\s*(\S+?)\s*\)\s*$", value.strip())
    return m.group(1) if m else None

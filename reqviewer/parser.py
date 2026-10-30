"""Markdown loader: ```req and ```asm blocks of `Field: value` lines, in level files."""
import re
from pathlib import Path

from reqviewer.model import Finding, LoadResult, Record, natural_key, split_lines

BEGIN_RE = re.compile(r"^<!--\s*BEGIN SECTION ([A-Za-z0-9_-]+)\s*-->\s*$")
END_RE = re.compile(r"^<!--\s*END SECTION ([A-Za-z0-9_-]+)\s*-->\s*$")
FIELD_RE = re.compile(r"^([A-Za-z][\w()/ ]*?):\s*(.*)$")


def rel(root, path):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def file_level(path, level_re):
    m = level_re.match(Path(path).name)
    return m.group(1) if m else Path(path).stem


class MarkdownLoader:
    def load(self, root, config):
        root = Path(root)
        fmt = config.format
        level_re = re.compile(config.files.level_pattern)
        fence_re = re.compile(r"^```(%s|%s)\s*$" % (re.escape(fmt.req_fence), re.escape(fmt.asm_fence)))
        paths = {p for g in config.files.levels for p in root.glob(g) if p.is_file()}
        files = sorted(((natural_key(file_level(p, level_re)), natural_key(rel(root, p)), p) for p in paths),
                       key=lambda t: t[:2])
        res = LoadResult()
        for _, _, path in files:
            level = file_level(path, level_re)
            if level not in res.levels:
                res.levels.append(level)
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as exc:
                res.problems.append(Finding(rel(root, path), 0, "error", "FORMAT", "", f"cannot read: {exc}"))
                continue
            self._parse(text, path, rel(root, path), level, config, fence_re, res)
        return res

    def _parse(self, text, path, name, level, config, fence_re, res):
        fmt = config.format
        lines = split_lines(text)
        section, open_at, seen = fmt.default_section, 0, set()
        heading, heading_line = "", 0

        def problem(line, msg):
            res.problems.append(Finding(name, line, "error", "FORMAT", "", msg))

        def add_section(s):
            if (level, s) not in res.sections:
                res.sections.append((level, s))

        i = 0
        while i < len(lines):
            line = lines[i]
            b, e = BEGIN_RE.match(line), END_RE.match(line)
            if b:
                if open_at:
                    problem(i + 1, f"section {b.group(1)} begins inside {section}")
                if b.group(1) in seen:
                    problem(i + 1, f"duplicate section {b.group(1)}")
                section, open_at = b.group(1), i + 1
                seen.add(section)
                add_section(section)
            elif e:
                if not open_at or e.group(1) != section:
                    problem(i + 1, f"END SECTION {e.group(1)} without matching BEGIN")
                else:
                    section, open_at = fmt.default_section, 0
            elif line.startswith("### "):
                heading, heading_line = line[4:].strip(), i + 1
            elif fence_re.match(line):
                kind = "req" if fence_re.match(line).group(1) == fmt.req_fence else "asm"
                start, body = i + 1, []
                i += 1
                while i < len(lines) and lines[i].strip() != "```":
                    body.append((i + 1, lines[i]))
                    i += 1
                if i >= len(lines):
                    problem(start, f"unclosed ```{kind} block")
                rec = Record(kind, path, start, section, level)
                known = fmt.req_fields if kind == "req" else fmt.asm_fields
                self._fields(rec, body, [*known, fmt.id_field] if known else [], problem)
                rid = rec.fields.get(fmt.id_field)
                if not rid:
                    problem(start, f"```{kind} block has no {fmt.id_field}")
                else:
                    if fmt.heading_must_match_id and heading and heading != rid:
                        problem(heading_line, f"heading {heading!r} does not match {fmt.id_field} {rid!r}")
                    res.records.append(rec)
                    add_section(section)
                heading, heading_line = "", 0
            i += 1
        if open_at:
            problem(open_at, f"section {section} has no END marker")

    @staticmethod
    def _fields(rec, body, known, problem):
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
            if known and name not in known:
                problem(lineno, f"unknown field {name!r}")
                current = None
            elif name in rec.fields:
                problem(lineno, f"duplicate field {name!r}")
                current = None
            else:
                rec.fields[name] = value
                current = name

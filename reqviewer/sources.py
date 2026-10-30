"""Extra sources: table, heading and yaml files that add non-requirement nodes."""
import re
from pathlib import Path

from reqviewer.model import Finding, split_lines
from reqviewer.parser import rel


def load_sources(root, config):
    """Return (items, problems). An item is a node dict plus `links` (kind, target) and `merge`."""
    items, problems = [], []
    for src in config.sources:
        path = Path(root) / src.file
        if not path.is_file():
            continue
        name = rel(root, path)
        first = len(items)

        def problem(msg):
            problems.append(Finding(name, 0, "error", "FORMAT", "", msg))

        try:
            if src.type == "yaml":
                items += _yaml(path, src, problem)
            else:
                text = path.read_text(encoding="utf-8-sig")
                items += _table(text, src) if src.type == "table" else _heading(text, src, problem)
        except (OSError, UnicodeDecodeError) as exc:
            problem(f"cannot read: {exc}")
        for item in items[first:]:
            item["at"] = (name, item["at"])
    return items, problems


def _text(value):
    return "" if value is None else str(value)


def _cell(cells, i):
    return cells[i] if 0 <= i < len(cells) else ""


def _table(text, src):
    items = []
    for lineno, line in enumerate(split_lines(text), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not re.fullmatch(src.id, cells[0]) or len(cells) < src.min_columns:
            continue
        if any(not re.search(rx, _cell(cells, i)) for i, rx in src.require.items()):
            continue
        title = _cell(cells, src.title).strip(src.title_strip)
        links = []
        for ln in src.links:
            value = _cell(cells, ln.column)
            targets = [m.group(0) for m in re.finditer(ln.pattern, value)] if ln.pattern else [value]
            links += [(ln, t) for t in dict.fromkeys(targets) if t]
        items.append({"id": cells[0], "kind": src.kind, "merge": src.merge,
                      "title": title[:src.title_max] if src.title_max else title,
                      "fields": {k: _cell(cells, i) for k, i in src.columns.items()}, "links": links,
                      "at": lineno})
    return items


def _heading(text, src, problem):
    items = []
    for lineno, line in enumerate(split_lines(text), 1):
        m = re.search(src.pattern, line)
        if m and not m.group(1):
            problem(f"line {lineno}: the pattern matched without an ID")
        elif m:
            items.append({"id": m.group(1), "kind": src.kind, "merge": False,
                          "title": (m.group(2) if m.re.groups > 1 and m.group(2) else "").strip(),
                          "fields": {}, "links": [], "at": lineno})
    return items


def _yaml(path, src, problem):
    try:
        import yaml
    except ImportError:
        problem("PyYAML is not installed; yaml source skipped")
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        problem(f"cannot read: {exc}")
        return []
    if src.list_key and isinstance(data, dict) and src.list_key not in data:
        problem(f"no key {src.list_key!r} at the top level")
        return []
    entries = data.get(src.list_key) if src.list_key and isinstance(data, dict) else data
    if entries is None:
        return []
    if not isinstance(entries, list):
        problem(f"{src.list_key or 'the top level'} must be a list")
        return []
    items = []
    for n, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            problem(f"entry {n} is not a mapping")
        elif not _text(e.get(src.id_key)).strip():
            problem(f"entry {n} has no {src.id_key!r}")
        else:
            items.append({"id": _text(e[src.id_key]), "kind": src.kind, "merge": False, "at": 0,
                          "title": _text(e.get(src.title_key)), "status": _text(e.get(src.status_key)),
                          "fields": {str(k).capitalize(): _text(v) for k, v in e.items()}, "links": []})
    return items

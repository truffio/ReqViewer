"""Generate an interactive requirements viewer (one self-contained HTML file).

Usage: python tools/viewer.py [--root DIR] [--out FILE]
Default output: build/requirements_viewer.html (not tracked by git).

The page shows the level files as a navigable graph: an outline, the selected
record, and its neighbourhood (parents, children, references, parameters,
ConOps needs and scenarios), plus a coverage matrix between levels. The
Markdown level files stay the source of truth; re-run this script after edits.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import lint
import param_check
import reqlib
import trace_check

DEFAULT_OUT = Path("build") / "requirements_viewer.html"
ID_RE = re.compile(r"(?<![\w-])(?:L0-(?:OBJ|CON|SUC|ASM)-\d+|L\d+-AER(?:-[A-Z0-9]+)*-\d+|N-\d{3}|SC-\d{3}"
                   r"|SH-\d{2}|P-[A-Z]+-\d+|DD-\d+)\b")
TEXT_FIELDS = ["Statement", "Rationale", "Verification", "TBD/TBR", "Source"]


def table_rows(text, first_cell_re):
    """Markdown table rows whose first cell matches `first_cell_re`, as cell lists."""
    rows = []
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and re.fullmatch(first_cell_re, cells[0]):
                rows.append(cells)
    return rows


def load_conops(root):
    """Stakeholders, needs and scenarios from specs/CONOPS.md, if present."""
    path = Path(root) / "specs" / "CONOPS.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    nodes = []
    for c in table_rows(text, r"SH-\d+"):
        nodes.append({"id": c[0], "kind": "stakeholder", "title": c[1],
                      "fields": {"Description": c[2] if len(c) > 2 else ""}, "links": []})
    for c in table_rows(text, r"N-\d+"):
        if len(c) < 4 or not re.fullmatch(r"SH-\d+", c[1]):
            continue  # traceability tables also start with need IDs
        nodes.append({"id": c[0], "kind": "need", "title": c[2].strip('"“”')[:90],
                      "fields": {"Stakeholder": c[1], "Need": c[2],
                                 "Meaning for the Aeronef": c[3] if len(c) > 3 else ""},
                      "links": [("stakeholder", c[1])]})
    scenarios = {}
    for m in re.finditer(r"^#### (SC-\d+) — (.+)$", text, re.M):
        scenarios[m.group(1)] = {"id": m.group(1), "kind": "scenario", "title": m.group(2).strip(),
                                 "fields": {}, "links": []}
    for c in table_rows(text, r"SC-\d+"):
        if c[0] in scenarios and len(c) >= 3 and "N-" in c[1]:
            scenarios[c[0]]["fields"] = {"Needs exercised": c[1], "D3 modes": c[2]}
            scenarios[c[0]]["links"] = [("exercises", n) for n in re.findall(r"N-\d+", c[1])]
    return nodes + list(scenarios.values())


def load_decisions(root):
    path = Path(root) / "registers" / "DECISIONS.md"
    if not path.exists():
        return []
    return [{"id": c[0], "kind": "decision", "title": c[1][:90],
             "fields": {"Decision": c[1], "Rationale": c[3] if len(c) > 3 else ""}, "links": []}
            for c in table_rows(path.read_text(encoding="utf-8"), r"DD-\d+")]


def rel(root, path):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def build(root):
    """Return the viewer data: nodes, edges and findings."""
    repo = reqlib.load_repo(root)
    params, _ = reqlib.load_parameters(root)
    nodes, edges = {}, []

    def add_edge(src, dst, kind):
        if src != dst:
            edges.append({"from": src, "to": dst, "kind": kind})

    for r in repo.records:
        nodes[r.id] = {"id": r.id, "kind": "req", "level": r.get("Level") or r.file_level,
                       "section": r.section, "type": r.get("Type"), "status": r.get("Status"),
                       "title": r.get("Statement"), "fields": dict(r.fields),
                       "file": rel(root, r.file), "line": r.line}
    for a in repo.assumptions:
        nodes[a.id] = {"id": a.id, "kind": "asm", "level": "L0", "section": a.section,
                       "status": a.get("Status"), "title": a.get("Assumption"),
                       "fields": dict(a.fields), "file": rel(root, a.file), "line": a.line}
    for p in params:
        pid = str(p.get("id", ""))
        nodes[pid] = {"id": pid, "kind": "param", "title": str(p.get("name", "")),
                      "status": str(p.get("status", "")),
                      "fields": {k.capitalize(): "" if v is None else str(v) for k, v in p.items()}}
    for extra in load_conops(root) + load_decisions(root):
        nodes[extra["id"]] = {k: v for k, v in extra.items() if k != "links"}
        for kind, dst in extra["links"]:
            add_edge(extra["id"], dst, kind)

    for r in repo.records:
        parents = reqlib.parent_ids(r.get("Parent(s)"))
        for pid in parents:
            add_edge(pid, r.id, "parent")
        dd = reqlib.derived_dd(r.get("Parent(s)"))
        if dd:
            add_edge(dd, r.id, "derived")
        for pid in set(reqlib.param_refs(r.get("Statement")) + reqlib.param_refs(r.get("Parameters"))):
            add_edge(r.id, pid, "uses")
        for sid in set(ID_RE.findall(r.get("Source"))):
            add_edge(r.id, sid, "source")
        text = " ".join(r.get(f) for f in TEXT_FIELDS if f != "Source")
        for ref in sorted(set(ID_RE.findall(text))):
            if ref not in parents and not ref.startswith("P-") and ref != dd:
                add_edge(r.id, ref, "refers")
    for a in repo.assumptions:
        for ref in sorted(set(ID_RE.findall(a.get("Affects") + " " + a.get("Rationale")))):
            add_edge(a.id, ref, "affects")

    # placeholder nodes for anything referenced but not defined
    for e in edges:
        for end in (e["from"], e["to"]):
            if end not in nodes:
                kind = "param" if end.startswith("P-") else "missing"
                nodes[end] = {"id": end, "kind": kind, "title": "", "missing": True,
                              "status": "not in database" if kind == "param" else "not found",
                              "fields": {}}

    findings = {}
    for f in lint.run(root) + trace_check.run(root) + param_check.run(root):
        findings.setdefault(f.item or "", []).append(
            {"severity": f.severity, "code": f.code, "message": f.message})
    return {"nodes": list(nodes.values()), "edges": edges, "findings": findings,
            "sections": section_order(root), "problems": [str(p) for p in repo.problems]}


def section_order(root):
    out = []
    for path in reqlib.level_files(root):
        found, _ = reqlib.find_sections(path.read_text(encoding="utf-8"))
        level = reqlib.file_level(path)
        for name, (begin, _) in sorted(found.items(), key=lambda kv: kv[1][0]):
            out.append({"level": level, "section": name})
    return out


def render(data):
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("/*DATA*/null", payload)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=reqlib.REPO_ROOT)
    ap.add_argument("--out", type=Path, help=f"output file (default: <root>/{DEFAULT_OUT.as_posix()})")
    args = ap.parse_args(argv)
    out = args.out or args.root / DEFAULT_OUT
    data = build(args.root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    reqs = sum(1 for n in data["nodes"] if n["kind"] == "req")
    print(f"wrote {out} ({reqs} requirement(s), {len(data['nodes'])} node(s), "
          f"{len(data['edges'])} link(s))")
    return 0


TEMPLATE = (Path(__file__).with_name("viewer_template.html")).read_text(encoding="utf-8")

if __name__ == "__main__":
    sys.exit(main())

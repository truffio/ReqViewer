"""Build the viewer data (nodes, edges, findings, sections) from the project files."""
import re
from dataclasses import asdict
from pathlib import Path

from reqviewer import checks
from reqviewer.config import LOADERS, id_regex
from reqviewer.model import natural_key
from reqviewer.parser import rel
from reqviewer.sources import load_sources

EDGES = {
    "parent": ("decomposes", "decomposed by"),
    "derived": ("derives", "derived from"),
    "uses": ("uses", "used by"),
    "source": ("source", "cited as source by"),
    "refers": ("refers to", "referred to by"),
    "affects": ("affects", "affected by"),
}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "viewer"


def build(root, config, extra_findings=()):
    """Return the viewer data: see docs/DESIGN.md section 6."""
    root = Path(root)
    roles, lk = config.fields, config.links
    id_re = re.compile(id_regex(config))
    uses_re = re.compile(lk.uses_pattern) if lk.uses_pattern else None
    derived_re = re.compile(lk.derived_pattern) if lk.derived_pattern else None
    result = LOADERS[config.loader]().load(root, config)
    items, source_problems = load_sources(root, config)
    result.problems += source_problems

    nodes, edges, seen_edges = {}, [], set()

    def add_edge(src, dst, kind):
        if src != dst and (src, dst, kind) not in seen_edges:
            seen_edges.add((src, dst, kind))
            edges.append({"from": src, "to": dst, "kind": kind})

    def ids(text):
        return [m.group(0) for m in id_re.finditer(text)]

    kept = []
    for r in result.records:
        rid = r.get(config.format.id_field)
        if rid in nodes:
            result.duplicates.append((nodes[rid], rel(root, r.file), r.line))   # first node kept; the check reports it
            continue
        req = r.kind == "req"
        node = {"id": rid, "kind": r.kind, "title": r.get(roles.statement if req else roles.assumption),
                "fields": dict(r.fields), "status": r.get(roles.status),
                "level": r.get(roles.level) or r.file_level, "section": r.section,
                "file": rel(root, r.file), "line": r.line}
        if req:
            node["type"] = r.get(roles.type)
        nodes[rid] = node
        kept.append((r, node))

    for item in sorted(items, key=lambda i: i["merge"]):     # merge sources last
        links, merge = item.pop("links"), item.pop("merge")
        if merge and item["id"] in nodes:
            nodes[item["id"]]["fields"].update(item["fields"])
        elif merge or item["id"] in nodes:
            continue
        else:
            nodes[item["id"]] = item
        for ln, target in links:
            add_edge(item["id"], target, ln.kind)

    for r, node in kept:
        rid = node["id"]
        parents_text = r.get(roles.parents)
        derived = None
        if derived_re and (m := derived_re.search(parents_text)):
            derived = m.group(1)
            parents_text = parents_text.replace(m.group(0), " ")
            add_edge(derived, rid, "derived")
        parents = [] if parents_text.strip() == lk.none_value else ids(parents_text)
        for p in parents:
            add_edge(p, rid, "parent")
        if node["kind"] == "asm":
            for f in lk.affects_fields:
                for ref in sorted(set(ids(r.get(f)))):
                    add_edge(rid, ref, "affects")
            continue
        used = set()
        for f in lk.uses_fields if uses_re else []:
            used.update(m.group(1) if uses_re.groups else m.group(0) for m in uses_re.finditer(r.get(f)))
        for u in sorted(used):
            add_edge(rid, u, "uses")
        for f in lk.source_fields:
            for ref in sorted(set(ids(r.get(f)))):
                add_edge(rid, ref, "source")
        skip = {config.format.id_field, roles.parents, *lk.source_fields}
        names = lk.refer_fields or [f for f in r.fields if f not in skip]
        for ref in sorted(set(ids(" ".join(r.get(f) for f in names)))):
            if ref not in parents and ref != derived and ref not in used \
                    and not (uses_re and uses_re.fullmatch(ref)):
                add_edge(rid, ref, "refers")

    yaml_kind = next((s.kind for s in config.sources if s.type == "yaml"), "missing")
    for e in edges:
        for end in (e["from"], e["to"]):
            if end not in nodes:
                uses = e["kind"] == "uses" and end == e["to"]
                nodes[end] = {"id": end, "kind": yaml_kind if uses else "missing", "title": "",
                              "missing": True, "status": "not in database" if uses else "not found",
                              "fields": {}}

    sections = [{"level": lv, "section": s} for lv, s in dict.fromkeys(result.sections)]
    for n in nodes.values():
        if n["kind"] in ("req", "asm"):
            pair = {"level": n["level"], "section": n["section"]}
            if pair not in sections:
                sections.append(pair)
    levels = sorted({*result.levels, *(s["level"] for s in sections)}, key=natural_key)

    data = {"meta": meta(config, levels), "nodes": list(nodes.values()), "edges": edges,
            "findings": {}, "sections": sections, "problems": [str(p) for p in result.problems]}
    for f in [*checks.run(result, data), *extra_findings]:
        data["findings"].setdefault(f["item"], []).append(
            {"severity": f["severity"], "code": f["code"], "message": f["message"]})
    return data


def meta(config, levels):
    kinds = {"req": {"label": "Requirement", "group": "Requirements"},
             "asm": {"label": "Assumption", "group": "Assumptions"}}
    edges = {k: {"label": a, "reverse": b} for k, (a, b) in EDGES.items()}
    for s in config.sources:
        label = s.label or s.kind
        if not s.merge:
            kinds[s.kind] = {"label": s.singular or label, "group": label, "color": s.color}
        for ln in s.links:
            edges[ln.kind] = {"label": ln.label or ln.kind,
                              "reverse": ln.reverse_label or f"{ln.label or ln.kind} (reverse)"}
    kinds["missing"] = {"label": "Not defined", "group": "Not defined", "color": "#e15759"}
    for k, v in kinds.items():
        v.update(config.display.kinds.get(k, {}))
        v.setdefault("color", "")
    d = config.display
    return {"title": config.title, "storage_key": "reqviewer." + slug(config.title),
            "id_pattern": id_regex(config), "levels": levels, "roles": asdict(config.fields),
            "id_field": config.format.id_field, "uses_fields": config.links.uses_fields,
            "none_value": config.links.none_value, "detail_rows": d.detail_rows,
            "label_strip": d.label_strip, "rationale_split": d.rationale_split,
            "criteria_marker": d.criteria_marker, "value_field": d.value_field,
            "unit_field": d.unit_field, "kinds": kinds, "edges": edges}

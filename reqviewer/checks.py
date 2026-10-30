"""Findings: built-in checks and external findings."""
import json
from pathlib import Path

from reqviewer.config import ConfigError

SEVERITIES = ("error", "warning")


def _where(node):
    return f"{node['file']}:{node['line']}: " if node and node.get("file") else ""


def run(load_result, data):
    """Findings as dicts: item, severity, code, message."""
    out = [{"item": f.item, "severity": f.severity, "code": f.code,
            "message": f"{f.file}:{f.line}: {f.message}"} for f in load_result.problems]
    nodes = {n["id"]: n for n in data["nodes"]}
    for first, file, line in getattr(load_result, "duplicates", []):
        out.append({"item": first["id"], "severity": "error", "code": "DUPLICATE_ID",
                    "message": f"{file}:{line}: ID {first['id']} is already defined at "
                               f"{first.get('file')}:{first.get('line')}"})
    for e in data["edges"]:
        src, dst = nodes[e["from"]], nodes[e["to"]]
        for missing, holder in ((src, dst), (dst, src)):
            if not missing.get("missing"):
                continue
            item = "" if holder.get("missing") else holder["id"]
            if e["kind"] == "parent" and missing is src:
                out.append({"item": item, "severity": "error", "code": "UNKNOWN_PARENT",
                            "message": f"{_where(holder)}parent {missing['id']} has no node"})
            else:
                out.append({"item": item, "severity": "warning", "code": "DANGLING_REF",
                            "message": f"{_where(holder)}reference to {missing['id']}, which has no node"})
    return out


def load_external(path):
    """Findings from a JSON file; any defect raises ConfigError."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError) as exc:
        raise ConfigError(f"cannot read findings file {path}: {exc}")
    if not isinstance(data, list):
        raise ConfigError(f"{path}: must be a JSON list")
    out = []
    for i, f in enumerate(data, 1):
        if not isinstance(f, dict):
            raise ConfigError(f"{path}: entry {i} is not an object")
        for key in ("item", "severity", "code", "message"):
            if not isinstance(f.get(key), str):
                raise ConfigError(f"{path}: entry {i}: '{key}' must be a string")
        if f["severity"] not in SEVERITIES:
            raise ConfigError(f"{path}: entry {i}: severity must be 'error' or 'warning'")
        out.append({k: f[k] for k in ("item", "severity", "code", "message")})
    return out

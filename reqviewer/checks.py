"""Findings: built-in checks and external findings."""
from reqviewer.config import ConfigError


def run(load_result, data):
    """Findings as dicts: item, severity, code, message."""
    return [{"item": f.item, "severity": f.severity, "code": f.code,
             "message": f"{f.file}:{f.line}: {f.message}"} for f in load_result.problems]


def load_external(path):
    raise ConfigError("--findings is not implemented yet")

"""Command-line interface for reqviewer."""

import argparse
import sys
from pathlib import Path

from reqviewer import checks, graph, render
from reqviewer.config import ConfigError, load_config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reqviewer",
                                 description="Write a self-contained requirements viewer page.")
    ap.add_argument("--root", type=Path, default=Path("."), help="project root (default: current directory)")
    ap.add_argument("--config", type=Path, help="configuration file (default: <root>/reqviewer.toml)")
    ap.add_argument("--out", type=Path, help="output HTML file (default: the config 'out', under the root)")
    ap.add_argument("--findings", type=Path, help="JSON file of extra findings")
    args = ap.parse_args(argv)
    try:
        if not args.root.is_dir():
            raise ConfigError(f"root is not a directory: {args.root}")
        config = load_config(args.root, args.config)
        extra = checks.load_external(args.findings) if args.findings else []
        data = graph.build(args.root, config, extra)
        out = args.out or args.root / config.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render.render(data), encoding="utf-8")
    except (ConfigError, OSError) as exc:
        print(f"reqviewer: error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:                    # last defence: a defect must not give a traceback
        print(f"reqviewer: error: {type(exc).__name__}: {' '.join(str(exc).split())}", file=sys.stderr)
        return 2
    if hasattr(sys.stdout, "reconfigure"):      # a path the console cannot encode must not fail the run
        sys.stdout.reconfigure(errors="backslashreplace")
    records = sum(1 for n in data["nodes"] if n["kind"] in ("req", "asm"))
    print(f"wrote {out} ({records} record(s), {len(data['nodes'])} node(s), {len(data['edges'])} link(s))")
    return 0

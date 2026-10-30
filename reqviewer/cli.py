"""Command-line interface for reqviewer."""

import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a self-contained requirements viewer page."
    )
    parser.add_argument("--root", type=Path, help="project root directory")
    parser.add_argument("--config", type=Path, help="configuration file")
    parser.add_argument("--out", type=Path, help="output HTML file")
    parser.add_argument("--findings", type=Path, help="findings file")
    parser.parse_args(argv)
    print("not implemented yet")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

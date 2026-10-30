"""Data model shared by the loaders, the graph builder and the checks."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from reqviewer.config import Config


def natural_key(text):
    """Sort key so that 'L2' comes before 'L10'."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


@dataclass(order=True)
class Finding:
    file: str
    line: int
    severity: str          # "error" or "warning"
    code: str
    item: str              # node ID, or ""
    message: str

    def __str__(self):
        who = f" {self.item}:" if self.item else ""
        return f"{self.file}:{self.line}: {self.severity} [{self.code}]{who} {self.message}"


@dataclass
class Record:
    kind: str              # "req" or "asm"
    file: Path
    line: int              # line of the opening fence
    section: str
    file_level: str        # level taken from the file name
    fields: dict = field(default_factory=dict)

    def get(self, name):
        return self.fields.get(name, "")


@dataclass
class LoadResult:
    records: list = field(default_factory=list)    # req and asm Records, in file order
    sections: list = field(default_factory=list)   # (level, section), in file order
    levels: list = field(default_factory=list)     # levels in order
    problems: list = field(default_factory=list)   # Findings
    duplicates: list = field(default_factory=list)  # (kept node, file, line) of later records reusing an ID


class Loader(Protocol):
    def load(self, root: Path, config: "Config") -> LoadResult: ...

"""Configuration: defaults, loading from TOML, validation."""
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from reqviewer.parser import MarkdownLoader

LOADERS = {"markdown": MarkdownLoader}
RESERVED_KINDS = ("req", "asm", "missing")
COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
# Python syntax that JavaScript lacks: named groups, atomic groups, comments, conditionals, inline
# flags, possessive quantifiers
JS_BAD_RE = re.compile(r"\(\?P[<=>]|\(\?>|\(\?#|\(\?\(|\(\?[aiLmsux]+(?:-[imsx]+)?[:)]|\(\?-[imsx]+:|[*+?}]\+")
DEFAULT_KINDS = {"req": {"label": "Requirement"}, "asm": {"label": "Assumption"}}


class ConfigError(Exception):
    pass


@dataclass
class Files:
    levels: list = field(default_factory=lambda: ["requirements/L*.md"])
    level_pattern: str = r"^(L\d+)"


@dataclass
class Format:
    req_fence: str = "req"
    asm_fence: str = "asm"
    req_fields: list = field(default_factory=list)
    asm_fields: list = field(default_factory=list)
    id_field: str = "ID"
    heading_must_match_id: bool = False
    default_section: str = "General"


@dataclass
class Ids:
    patterns: list = field(default_factory=lambda: [r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+"])


@dataclass
class Fields:
    statement: str = "Statement"
    assumption: str = "Assumption"
    level: str = "Level"
    type: str = "Type"
    status: str = "Status"
    parents: str = "Parent(s)"
    allocation: str = "Allocated to"
    verification: str = "Verification"
    rationale: str = "Rationale"
    open_items: str = "TBD/TBR"


@dataclass
class Links:
    none_value: str = "—"
    derived_pattern: str = ""
    uses_pattern: str = ""
    uses_fields: list = field(default_factory=list)
    source_fields: list = field(default_factory=lambda: ["Source"])
    refer_fields: list = field(default_factory=list)
    affects_fields: list = field(default_factory=lambda: ["Affects", "Rationale"])


@dataclass
class Display:
    detail_rows: list = field(default_factory=list)
    label_strip: str = r"^The [\w\s-]{1,40}? shall "
    rationale_split: str = ""
    criteria_marker: str = ""
    value_field: str = "Value"
    unit_field: str = "Unit"
    kinds: dict = field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_KINDS.items()})


@dataclass
class Link:
    kind: str = ""
    column: int = 0
    pattern: str = ""
    label: str = ""
    reverse_label: str = ""


@dataclass
class Source:
    type: str = ""
    kind: str = ""
    file: str = ""
    label: str = ""
    singular: str = ""
    color: str = ""
    merge: bool = False
    id: str = ""                                    # table
    title: int = 0
    title_max: int = 0
    title_strip: str = ""
    min_columns: int = 0
    require: dict = field(default_factory=dict)
    columns: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    pattern: str = ""                               # heading
    list_key: str = ""                              # yaml
    id_key: str = "id"
    title_key: str = "name"
    status_key: str = "status"


COMMON = {"type", "kind", "file", "label", "singular", "color"}
SOURCE_KEYS = {
    "table": COMMON | {"merge", "id", "title", "title_max", "title_strip", "min_columns", "require",
                       "columns", "links"},
    "heading": COMMON | {"pattern"},
    "yaml": COMMON | {"list_key", "id_key", "title_key", "status_key"},
}


@dataclass
class Config:
    title: str = "Requirements"
    out: str = "build/requirements_viewer.html"
    loader: str = "markdown"
    files: Files = field(default_factory=Files)
    format: Format = field(default_factory=Format)
    ids: Ids = field(default_factory=Ids)
    fields: Fields = field(default_factory=Fields)
    links: Links = field(default_factory=Links)
    display: Display = field(default_factory=Display)
    sources: list = field(default_factory=list)


def id_regex(config):
    return r"(?<![\w-])(?:" + "|".join(config.ids.patterns) + r")\b"


def _check_type(value, want, name, items=str):
    ok = isinstance(value, want) and (want is bool or not isinstance(value, bool))
    if ok and want is list:
        ok = all(isinstance(v, items) for v in value)
    if not ok:
        raise ConfigError(f"{name}: expected {f'a list of {items.__name__}s' if want is list else want.__name__}")


def _fill(obj, table, path, allowed=None):
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: expected a table")
    for key, value in table.items():
        name = f"{path}.{key}" if path else key
        if key not in obj.__dataclass_fields__ or (allowed is not None and key not in allowed):
            raise ConfigError(f"{name}: unknown key")
        _check_type(value, type(getattr(obj, key)), name, dict if key == "links" else str)
        setattr(obj, key, value)
    return obj


def _regex(pattern, name):
    try:
        return re.compile(pattern)
    except (re.error, OverflowError, RecursionError) as exc:
        raise ConfigError(f"{name}: bad regular expression: {exc}") from None


def _js_regex(pattern, name):
    rx = _regex(pattern, name)
    plain = re.sub(r"\[\^?\]?[^\]]*\]", "", re.sub(r"\\.", "", pattern, flags=re.S))   # no escapes, no classes
    if JS_BAD_RE.search(plain):
        raise ConfigError(f"{name}: syntax not available in JavaScript")
    return rx


def _not_empty(rx, name):
    if rx.match(""):
        raise ConfigError(f"{name}: must not match an empty string")


def _glob(pattern, name):
    if not pattern or PurePosixPath(pattern).is_absolute() or PureWindowsPath(pattern).anchor:
        raise ConfigError(f"{name}: must be a relative glob")
    if any("**" in part and part != "**" for part in pattern.split("/")):
        raise ConfigError(f"{name}: bad glob: '**' must be a whole path segment")
    try:
        list(Path("no-such-dir").glob(pattern))      # raises on a pattern that cannot work
    except (ValueError, NotImplementedError) as exc:
        raise ConfigError(f"{name}: bad glob: {exc}") from None


def _color(value, name):
    if value and not COLOR_RE.fullmatch(value):
        raise ConfigError(f"{name}: colour must be #rgb or #rrggbb")


def _index(key, name):
    try:
        return int(key)
    except ValueError:
        raise ConfigError(f"{name}.{key}: cell index must be a number") from None


def _source(table, path):
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: expected a table")
    stype = table.get("type")
    if not isinstance(stype, str) or stype not in SOURCE_KEYS:
        raise ConfigError(f"{path}.type: must be one of {', '.join(SOURCE_KEYS)}")
    src = _fill(Source(), table, path, SOURCE_KEYS[stype])
    for key in ("kind", "file", {"table": "id", "heading": "pattern"}.get(stype)):
        if key and not getattr(src, key):
            raise ConfigError(f"{path}.{key}: required")
    if src.kind in RESERVED_KINDS:
        raise ConfigError(f"{path}.kind: {src.kind!r} is reserved")
    _color(src.color, f"{path}.color")
    if stype == "heading" and _js_regex(src.pattern, f"{path}.pattern").groups < 1:
        raise ConfigError(f"{path}.pattern: needs a group for the ID")
    if stype == "table":
        if src.title_max < 0:
            raise ConfigError(f"{path}.title_max: must not be negative")
        if _js_regex(src.id, f"{path}.id").fullmatch(""):
            raise ConfigError(f"{path}.id: must not match an empty cell")
        src.require = {_index(k, f"{path}.require"): v for k, v in src.require.items()}
        for k, v in src.require.items():
            _check_type(v, str, f"{path}.require.{k}")
            _js_regex(v, f"{path}.require.{k}")
        for k, v in src.columns.items():
            _check_type(v, int, f"{path}.columns.{k}")
        src.links = [_link(item, f"{path}.links[{n}]") for n, item in enumerate(src.links)]
    return src


def _link(item, path):
    if isinstance(item, dict) and not item.get("kind"):
        raise ConfigError(f"{path}.kind: required")
    link = _fill(Link(), item, path)
    _js_regex(link.pattern, f"{path}.pattern")
    return link


def parse(table):
    """Build a validated Config from a parsed TOML table."""
    cfg = Config()
    if not isinstance(table, dict):
        raise ConfigError("expected a table")
    sections = {"files": cfg.files, "format": cfg.format, "ids": cfg.ids, "fields": cfg.fields,
                "links": cfg.links, "display": cfg.display}
    for key, value in table.items():
        if key == "sources":
            if not isinstance(value, list):
                raise ConfigError("sources: expected an array of tables")
            cfg.sources = [_source(t, f"sources[{n}]") for n, t in enumerate(value)]
        elif key in sections:
            _fill(sections[key], value, key)
        elif key in ("title", "out", "loader"):
            _check_type(value, str, key)
            setattr(cfg, key, value)
        else:
            raise ConfigError(f"{key}: unknown key")
    _validate(cfg)
    return cfg


def _validate(cfg):
    if cfg.loader not in LOADERS:
        raise ConfigError(f"loader: unknown loader {cfg.loader!r} (known: {', '.join(LOADERS)})")
    if _regex(cfg.files.level_pattern, "files.level_pattern").groups != 1:
        raise ConfigError("files.level_pattern: needs exactly one group")
    if not cfg.ids.patterns:
        raise ConfigError("ids.patterns: at least one pattern is required")
    for n, g in enumerate(cfg.files.levels):
        _glob(g, f"files.levels[{n}]")
    for n, p in enumerate(cfg.ids.patterns):
        _not_empty(_js_regex(p, f"ids.patterns[{n}]"), f"ids.patterns[{n}]")
    _regex(id_regex(cfg), "ids.patterns")                 # the joined pattern must compile too
    ln = cfg.links
    for key in ("derived_pattern", "uses_pattern"):
        if getattr(ln, key):
            _not_empty(_js_regex(getattr(ln, key), f"links.{key}"), f"links.{key}")
    if ln.derived_pattern and re.compile(ln.derived_pattern).groups < 1:
        raise ConfigError("links.derived_pattern: needs a group for the node ID")
    _js_regex(cfg.display.label_strip, "display.label_strip")
    known = set(RESERVED_KINDS) | {s.kind for s in cfg.sources}
    kinds = cfg.display.kinds
    for kind, spec in kinds.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"display.kinds.{kind}: expected a table")
        if kind not in known:
            raise ConfigError(f"display.kinds.{kind}: unknown kind")
        for key, value in spec.items():
            if key not in ("label", "group", "color"):
                raise ConfigError(f"display.kinds.{kind}.{key}: unknown key")
            _check_type(value, str, f"display.kinds.{kind}.{key}")
        _color(spec.get("color", ""), f"display.kinds.{kind}.color")
    for kind, spec in DEFAULT_KINDS.items():
        kinds[kind] = {**spec, **kinds.get(kind, {})}


def load_config(root, explicit=None):
    """Read `explicit`, else <root>/reqviewer.toml if present, else the defaults."""
    path = Path(explicit) if explicit else Path(root) / "reqviewer.toml"
    if not path.is_file():
        if explicit:
            raise ConfigError(f"config file not found: {path}")
        return Config()
    try:
        return parse(tomllib.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, RecursionError, ConfigError) as exc:
        raise ConfigError(f"{path}: {exc}") from None

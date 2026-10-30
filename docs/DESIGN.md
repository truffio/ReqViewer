# ReqViewer design

ReqViewer reads a project's requirements and writes one self-contained HTML page: outline, record detail, link graph, coverage matrix and findings. This note is the design input for issues #5 to #15.

## 1. Rules

- No project vocabulary in `reqviewer/` or `tests/`. Project terms live in config files under `examples/`.
- Python 3.11+ (`tomllib`). Standard library only. PyYAML is an optional extra, used only by `yaml` sources.
- The page is one file and makes no external requests.
- A malformed input gives a reported problem, never a traceback. A bad config or findings file gives a one-line error and exit code 2.

## 2. Layout

```
reqviewer/
  __init__.py     __version__
  __main__.py     calls cli.main
  cli.py          argument parsing, exit codes
  config.py       Config dataclasses, defaults, validation
  model.py        Finding, Record, LoadResult, Loader protocol
  parser.py       markdown loader
  sources.py      table, heading and yaml sources
  graph.py        build(): nodes, edges, sections
  checks.py       built-in checks, external findings
  render.py       render(data): fills the template
  template.html
tests/
examples/sample/     invented project, with its reqviewer.toml
examples/aircraft/   reqviewer.toml only, reads a checkout of truffio/aircraft
docs/
```

Entry points: `python -m reqviewer` and the console script `reqviewer` (`reqviewer.cli:main`). `template.html` is package data.

```
reqviewer --root DIR [--config FILE] [--out FILE] [--findings FILE]
```

- `--root` defaults to the current directory. `--config` defaults to `<root>/reqviewer.toml`; if that file is absent, the defaults apply. An explicit `--config` that does not exist is an error.
- `--out` defaults to the config `out`, relative to the root.
- All paths in the config are relative to the root.
- On success, print the output path and the record, node and link counts.

## 3. Configuration

Every key is optional. The values shown are the defaults. An unknown key is an error that names the key.

```toml
title = "Requirements"
out = "build/requirements_viewer.html"
loader = "markdown"

[files]
levels = ["requirements/L*.md"]    # globs, relative to the root
level_pattern = '^(L\d+)'          # group 1 of the file name is the level; no match: the file stem

[format]                           # markdown loader only
req_fence = "req"
asm_fence = "asm"
req_fields = []                    # allowed field names; empty allows any
asm_fields = []
id_field = "ID"
heading_must_match_id = false      # a '### ...' line just before a block must equal its ID
default_section = "General"        # section of a record outside any section marker

[ids]
patterns = ['[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+']

[fields]                           # roles: which field plays which part. "" switches the feature off
statement = "Statement"
assumption = "Assumption"          # the title of an assumption record
level = "Level"
type = "Type"
status = "Status"
parents = "Parent(s)"
allocation = "Allocated to"
verification = "Verification"
rationale = "Rationale"
open_items = "TBD/TBR"

[links]
none_value = "—"                   # a value meaning "not applicable"
derived_pattern = ""               # regex on the parents value; group 1 is a node ID, giving a "derived" edge
uses_pattern = ""                  # regex; matches give "uses" edges
uses_fields = []
source_fields = ["Source"]         # ID matches give "source" edges
refer_fields = []                  # ID matches give "refers" edges; empty: all fields but ID, parents and source
affects_fields = ["Affects", "Rationale"]    # on assumptions

[display]
detail_rows = []                   # field names, in order; empty: all fields but ID and statement, in file order
label_strip = '^The [\w\s-]{1,40}? shall '   # removed from labels so that they show what differs
rationale_split = ""               # marker text: starts a new paragraph, shown on child cards. E.g. "Sufficiency:"
criteria_marker = ""               # marker text splitting a verification value. E.g. "success criteria:"
value_field = "Value"              # shown next to a used node, if present
unit_field = "Unit"
[display.kinds.req]                # label and colour overrides, for any node kind
label = "Requirement"
[display.kinds.asm]
label = "Assumption"

[[sources]]                        # none by default; see section 4
```

Validation:

- Each entry in `ids.patterns`, `uses_pattern`, and each source pattern must compile in Python, and must not use syntax that JavaScript lacks: reject `(?P<`, `(?P=`, `(?>`, `(?#`, `(?(`, inline flags such as `(?i)` and possessive quantifiers such as `a++`. Escapes and character classes are not scanned. The joined ID pattern must compile too.
- `ids.patterns`, `uses_pattern` and `derived_pattern` must not match the empty string, and a table source `id` must not match an empty cell.
- `display.kinds.*.color` and a source `color` must be `#rgb` or `#rrggbb` (the whole value), because it goes into page attributes.
- A `level_pattern` needs one group. It is searched in the file name; if it does not match, or its group is empty or unset, the level is the file stem.
- Each `files.levels` entry must be a non-empty relative glob that `pathlib` accepts. A glob that matches no file is not an error: it gives a warning problem (`FORMAT`), and the run goes on.
- `title_max` must not be negative. A link needs a non-empty `kind`. A source `type` must be a string.
- Any other defect that reaches `cli.main` is reported as one line and exit code 2, never as a traceback.

The ID pattern is built as `(?<![\w-])(?:p1|p2|...)\b` in Python, and passed to the page as a string (`meta.id_pattern`). `ID_RE` is no longer written in the template. Regular expressions in the config have the same meaning in both places.

## 4. Extra sources

Sources add non-requirement nodes, and replace the former ConOps, decisions and parameters loaders. A source whose file is missing is skipped silently. Each source has `type`, `kind`, `file`. `label` is the outline group name (default: the kind). `singular` is the detail chip (default: `label`). `color` is optional.

**`type = "table"`:** Markdown table rows.

```toml
[[sources]]
type = "table"
kind = "need"
label = "Needs"
singular = "Need"
file = "docs/needs.md"
id = 'N-\d+'                   # full match on the first cell
title = 2                      # cell index
title_max = 90                 # 0: no limit
title_strip = '"“”'            # characters stripped from both ends
min_columns = 4                # shorter rows are skipped
require = { 1 = '^SH-\d+$' }   # cell index -> regex search; rows that fail are skipped
columns = { Stakeholder = 1, Need = 2 }    # field name -> cell index; a missing cell gives ""
links = [{ kind = "stakeholder", column = 1, pattern = '' }]
```

A link gives edges from the node to each match of `pattern` in that cell, or to the whole cell if `pattern` is empty. `merge = true` adds the fields and links to nodes that already exist, and creates nothing; rows with no such node are skipped. This fills in the `heading` nodes below.

**`type = "heading"`:** heading lines.

```toml
[[sources]]
type = "heading"
kind = "scenario"
label = "Scenarios"
file = "docs/scenarios.md"
pattern = '^#### (SC-\d+) — (.+)$'    # group 1 is the ID, group 2 the title
```

**`type = "yaml"`:** a list of mappings.

```toml
[[sources]]
type = "yaml"
kind = "param"
label = "Parameters"
file = "parameters.yaml"
list_key = "parameters"
id_key = "id"
title_key = "name"
status_key = "status"
```

Fields are every key, capitalised, with `None` shown as `""`. If PyYAML is absent, or the file is invalid, or `list_key` is set and absent from the top level, or an entry is not a mapping or has an empty ID, add a problem and carry on. A table or heading row whose ID is already taken (by a record or an earlier row) is dropped with its links, and `DUPLICATE_ID` is reported. A heading pattern that matches without giving its ID group is a problem.

Edge labels: a link may set `label` and `reverse_label`.

Node kinds `req`, `asm` and `missing` are reserved. A source using one is a config error.

## 5. Loader seam

```python
@dataclass(order=True)
class Finding:
    file: str
    line: int
    severity: str     # "error" or "warning"
    code: str
    item: str         # node ID, or ""
    message: str

@dataclass
class Record:
    kind: str         # "req" or "asm"
    file: Path
    line: int
    section: str
    file_level: str
    fields: dict
    def get(self, name): ...        # "" if absent

@dataclass
class LoadResult:
    records: list         # req and asm Records, in file order
    sections: list        # (level, section), in file order, including empty sections
    levels: list          # levels in order
    problems: list        # Findings
    duplicates: list      # (kept node, file, line) of each later record or source row that reuses an ID;
                          # graph.build fills it, checks.run reports it as DUPLICATE_ID

class Loader(Protocol):
    def load(self, root: Path, config: Config) -> LoadResult: ...
```

`parser.py` implements `MarkdownLoader`, keeping the format of the source `reqlib.py`: fences, `Field: value` lines, indented continuation lines, and `<!-- BEGIN SECTION x -->` / `<!-- END SECTION x -->` markers (unbalanced markers are problems). A line that nearly is a fence or a marker (indented, other case, `~~~`, extra words, a space in the section name) is a problem, not ignored. Files are read as UTF-8 with an optional BOM, and lines end at LF, CRLF or CR only. `config.py` maps `loader` names to classes in `LOADERS`; an unknown name is a config error.

`reqlib` helpers for the verification split, reports and common arguments are not carried over.

## 6. Data contract

`graph.build(root, config, extra_findings=())` returns the data below. `extra_findings` are dicts with `item`, `severity`, `code` and `message` (from `--findings`), added after the built-in ones.

```json
{
  "meta": {
    "title": "...",
    "storage_key": "reqviewer.<slug of title>",
    "id_pattern": "...",
    "levels": ["L0", "L1"],
    "roles": {"statement": "...", "parents": "...", "...": "..."},
    "id_field": "ID",
    "uses_fields": [],
    "none_value": "—",
    "detail_rows": [],
    "label_strip": "...",
    "rationale_split": "",
    "criteria_marker": "",
    "value_field": "Value",
    "unit_field": "Unit",
    "kinds": {"req": {"label": "...", "group": "...", "color": "..."}},
    "edges": {"uses": {"label": "...", "reverse": "..."}}
  },
  "nodes": [],
  "edges": [{"from": "...", "to": "...", "kind": "..."}],
  "findings": {"<node id or empty>": [{"severity": "...", "code": "...", "message": "..."}]},
  "sections": [{"level": "...", "section": "..."}],
  "problems": ["..."]
}
```

Nodes:

| Key | Present on | Meaning |
| --- | --- | --- |
| `id`, `kind`, `title`, `fields` | all | `fields` is a mapping of field name to text |
| `status` | all but some sources | Text |
| `level`, `section`, `file`, `line` | `req`, `asm` | `level` is the `level` role value, else the file level |
| `type` | `req` | Text |
| `missing` | placeholders | `true` |

Edge kinds: `parent` (parent to child), `derived` (decision to record), `uses`, `source`, `refers`, `affects`, plus link kinds from sources. Default labels and reverse labels for the built-in kinds are in `graph.py`.

Rules:

- `refers` skips the record's own parents, the `derived` target, and anything matching `uses_pattern`.
- A referenced ID with no node gets a placeholder. A `uses` target gets the kind of the first `yaml` source (`missing` if there is none) and status `not in database`, whatever the order of the edges. Any other target gets kind `missing` and status `not found`.
- A record listing itself as parent (or as the `derived` target) gets no edge and a `SELF_PARENT` warning.
- A `derived_pattern` or `uses_pattern` match whose ID group is unset gives a problem, and no node.
- `levels` comes from the loader, sorted naturally, so `L2` comes before `L10`. Level comparison uses list position, never string order.
- Every (level, section) that a node has must be in `sections`, including the default section and any level set by a `level` field that differs from the file. Otherwise a record is lost from the outline.
- A duplicate ID keeps the first node, and `checks.py` reports it, for a record and for a source row alike.

`render(data)` substitutes `/*DATA*/null` once, with `JSON.parse("...")`. The string literal is the JSON text of the data (`json.dumps(data)`, ASCII only) dumped once more as a string, with every `<` written as the six characters `<`, so that nothing in the data can end the script element. An object literal would turn a `"__proto__"` key into the prototype, and a lone surrogate would not survive writing the file as UTF-8; `JSON.parse` and ASCII-only text avoid both. The title is set from `meta` by script, so that the template needs no HTML substitution.

## 7. Template

Replace each hardcoded item below. A role set to `""` hides its control.

| Today | Becomes |
| --- | --- |
| Heading "Aeronef requirements" | `meta.title`, also `document.title` |
| `ID_RE` literal | `new RegExp(meta.id_pattern, "g")` |
| `KIND_LABEL`, `KIND_COLOR`, `EDGE_LABEL`, `REVERSE_LABEL` | `meta.kinds`, `meta.edges`, with the palette as the fallback colour |
| `levels` by string sort, `"L0"` fallbacks, `l > rowLv` | `meta.levels`, compared by index |
| Fixed outline group list | One group per entry in `meta.kinds` that has nodes, `missing` last |
| Fixed detail rows and field names | `meta.detail_rows` and `meta.roles`; parents and allocation are linkified, `uses` shows the value list |
| Verification split | Only when `criteria_marker` is set; otherwise the value is shown as is |
| `Sufficiency:` | `meta.rationale_split`; no split or card line when empty |
| `isTbd` on `TBD/TBR`, chip "TBD/TBR open", filter "Open TBD/TBR" | Role `open_items`, with the field name in the labels; hidden when off |
| `—` | `meta.none_value` |
| Allocation column option | Only when the `allocation` role is set and some record has a value |
| "from lint, trace check and parameter check" | "finding(s)" |
| Missing-node text naming ConOps and registers | "Referenced but not defined." |
| `localStorage` keys `viewer.*` | `meta.storage_key + "." + key` |
| `short()` replaces the subject by `"… "` | Remove it, no replacement, and capitalise the first letter (aircraft#105) |

Defects to fix on the way:

- `coverage()` crashes on `colOpts[0][0]` when there is one level and no allocation. Show an empty-state message instead.
- Values inserted in HTML unescaped, which is safe only for the old ID format: `n.id`, `id`, `c`, `rowLv`, `f.code`, `f.id` and the `data-id` attributes. All go through `esc`, and `esc` also escapes `'`.
- In `linkify`, IDs are found in the raw text, and the text between them and each ID are escaped separately, so `R&D-1` is found and digits inside an entity such as `&#39;` are not.
- Data keys are looked up as own properties (`Object.hasOwn`, `Map`, `Object.create(null)`), so IDs, kinds and field names such as `constructor` or `__proto__` work.
- `onclick` on a `data-id` of a node with `&` in its ID must still find the node: read `dataset.id`, which decodes it.

## 8. Checks

`checks.run(load_result, data)` gives findings, all shown in the Findings view:

| Code | Severity | Meaning |
| --- | --- | --- |
| `FORMAT` | error, or warning | From the loader's problems. A `files.levels` glob that matches no file is a warning |
| `DUPLICATE_ID` | error | Two records, or a record and a source row, or two source rows, with one ID |
| `UNKNOWN_PARENT` | error | A parent ID that has no node |
| `DANGLING_REF` | warning | Any other reference that has no node |
| `SELF_PARENT` | warning | A record that lists itself as parent. `graph.build` adds it, because the edge is dropped there |

`--findings FILE` reads a JSON list of `{"item", "severity", "code", "message"}`, and adds them to the built-in ones. `item` may be `""`, `severity` must be `error` or `warning`. Anything else is an error with exit code 2. This lets a project's own lint tool feed the page.

The `problems` list keeps the loader problems as text, for the banner in the Findings view.

## 9. Tests

`python -m unittest discover -s tests`. Fixtures come from `examples/sample/`, plus small inline configs. They cover the contract in section 6, each rule in sections 3 to 5, escaping, and the CLI exit codes. A test greps `reqviewer/` and `tests/` for project vocabulary (`aeronef`, `aircraft`, `L1-AER`, `CONOPS`, `P-SYS`).

Page behaviour is checked in a browser at #13. No browser test framework is added.

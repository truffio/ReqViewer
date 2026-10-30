# ReqViewer format guide

## Records

Requirements live in Markdown files. A record is a fenced block of `Field: value` lines. Two fence names are used by default: `req` for a requirement and `asm` for an assumption.

````
### L1-BRW-001

```req
ID: L1-BRW-001
Type: Functional
Statement: The brew unit shall deliver 40 ml of espresso
  within the time given in PRM-002.
Parent(s): L0-SYS-001
Status: Approved
```
````

Rules:

- A field line is a name, a colon and a value. The name starts with a letter and may contain letters, digits, `_`, `(`, `)`, `/` and spaces (`Parent(s)`, `TBD/TBR`).
- A line that starts with a space or a tab continues the previous field. The lines are joined with single spaces.
- Blank lines in a block are ignored.
- Every block needs the ID field (`format.id_field`). A block without one is a problem and is dropped.
- A duplicate field name in one block, an unknown field name (when `req_fields` or `asm_fields` is set), a line that is not a field line, and an unclosed block are each reported as a problem.
- With `heading_must_match_id = true`, a `### ` heading just before a block must equal the block's ID. Only blank lines may sit between them: any other line, such as prose, another heading or a section marker, cancels the heading.
- A line that nearly is a fence (indented, with extra words after the name, another case, or `~~~` instead of backticks) is reported as a problem, so that a block is not skipped silently.
- Files may start with a UTF-8 byte order mark. Lines end at LF, CRLF or CR; other characters, such as U+2028, do not end a line.

### Sections

Records can be grouped in sections with HTML comments, on lines of their own:

```
<!-- BEGIN SECTION BREWING -->
...records...
<!-- END SECTION BREWING -->
```

The section name uses letters, digits, `_` and `-`. Sections do not nest and each name is used once per file. A record outside any section goes in `format.default_section`. Unbalanced or misplaced markers are problems, and so is a line that nearly is a marker (other case, a space in the name, text after the closing `-->`).

### Levels

The level of a record comes from the name of its file. `files.levels` lists globs (relative to the root) for the level files, and `files.level_pattern` is a regular expression with one group, searched in the file name. With the defaults, `requirements/L1.md` is level `L1`. If the pattern does not match, or its group is empty or unset, the file stem is the level. A glob must be relative and not empty; one that matches no file is reported as a warning in the Findings view, and the run goes on. Levels are sorted naturally (`L2` before `L10`). A record can override its level with the field named by the `level` role, when that field is present.

## Configuration

The configuration is a TOML file, `reqviewer.toml` in the root by default. Every key is optional. An unknown key is an error that names the key. Regular expressions must compile in Python and must not use syntax that JavaScript lacks: `(?P<name>...)`, `(?P=name)`, atomic groups `(?>...)`, comments `(?#...)`, conditionals `(?(1)...)`, possessive quantifiers such as `a++` and inline flags such as `(?i)` are rejected. A pattern for IDs (`ids.patterns`, `links.uses_pattern`, `links.derived_pattern`) must not match an empty string.

### Top level

| Key | Default | Meaning |
| --- | --- | --- |
| `title` | `"Requirements"` | Page title. |
| `out` | `"build/requirements_viewer.html"` | Output file, relative to the root. |
| `loader` | `"markdown"` | Loader for the requirement files. Only `markdown` exists. |

### `[files]`

| Key | Default | Meaning |
| --- | --- | --- |
| `levels` | `["requirements/L*.md"]` | Globs of the level files. |
| `level_pattern` | `'^(L\d+)'` | Regular expression with exactly one group, matched against the file name; the group is the level. |

### `[format]`

| Key | Default | Meaning |
| --- | --- | --- |
| `req_fence` | `"req"` | Fence name of requirement blocks. |
| `asm_fence` | `"asm"` | Fence name of assumption blocks. |
| `req_fields` | `[]` | Allowed field names in requirement blocks. Empty allows any. |
| `asm_fields` | `[]` | Same, for assumption blocks. |
| `id_field` | `"ID"` | Field that holds the record ID. |
| `heading_must_match_id` | `false` | Require a `### ` heading before a block to equal its ID. |
| `default_section` | `"General"` | Section of a record outside any section marker. |

### `[ids]`

| Key | Default | Meaning |
| --- | --- | --- |
| `patterns` | `['[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+']` | Regular expressions for IDs. At least one. Text in a record that matches one is treated as a reference. |

### `[fields]`

Roles: which field name plays which part. An empty string `""` switches the feature off.

| Key | Default | Meaning |
| --- | --- | --- |
| `statement` | `"Statement"` | The requirement text. |
| `assumption` | `"Assumption"` | The title of an assumption record. |
| `level` | `"Level"` | Optional level override. |
| `type` | `"Type"` | Record type. |
| `status` | `"Status"` | Record status. |
| `parents` | `"Parent(s)"` | IDs of the parent records. Gives `parent` links. |
| `allocation` | `"Allocated to"` | What the record is allocated to. Adds an option to the coverage matrix. |
| `verification` | `"Verification"` | Verification method. |
| `rationale` | `"Rationale"` | Rationale text. |
| `open_items` | `"TBD/TBR"` | Open items. A record with a value other than `links.none_value` counts as open and can be filtered. |

### `[links]`

| Key | Default | Meaning |
| --- | --- | --- |
| `none_value` | `"—"` | A value that means "not applicable". |
| `derived_pattern` | `""` | Regular expression on the parents value. Group 1 is a node ID and gives a `derived` link. |
| `uses_pattern` | `""` | Regular expression. Matches in `uses_fields` give `uses` links. |
| `uses_fields` | `[]` | Fields searched with `uses_pattern`. |
| `source_fields` | `["Source"]` | Fields whose ID matches give `source` links. |
| `refer_fields` | `[]` | Fields whose ID matches give `refers` links. Empty: all fields except the ID, parents and source fields. |
| `affects_fields` | `["Affects", "Rationale"]` | On assumptions, fields whose ID matches give `affects` links. |

A `refers` link skips the record's own parents, the `derived` target and anything matching `uses_pattern`. A referenced ID with no node gets a placeholder node and a finding.

### `[display]`

| Key | Default | Meaning |
| --- | --- | --- |
| `detail_rows` | `[]` | Field names shown in the detail view, in order. Empty: all fields except the ID and statement, in file order. |
| `label_strip` | `'^The [\w\s-]{1,40}? shall '` | Regular expression removed from the start of labels, so that labels show what differs. |
| `rationale_split` | `""` | Marker text that starts a new paragraph in a rationale and is shown on child cards, for example `"Sufficiency:"`. Empty: no split. |
| `criteria_marker` | `""` | Marker text that splits a verification value, for example `"success criteria:"`. Empty: the value is shown as is. |
| `value_field` | `"Value"` | Field shown next to a used node, if present. |
| `unit_field` | `"Unit"` | Unit of that value. |

`[display.kinds.<kind>]` overrides how a node kind is shown. `<kind>` is `req`, `asm`, `missing` (the placeholders for IDs that have no node) or the `kind` of a source. Keys: `label` (name in the interface), `group` (outline group name) and `color` (`#rgb` or `#rrggbb`). The defaults are `label = "Requirement"` for `req` and `label = "Assumption"` for `asm`.

## Sources

Sources add nodes that are not requirement records: needs, decisions, scenarios, parameters. They are listed as `[[sources]]` tables; there are none by default. A source whose file is missing is skipped silently. A source that cannot be read is reported as a problem and the run goes on.

Keys common to all types:

| Key | Default | Meaning |
| --- | --- | --- |
| `type` | required | `table`, `heading` or `yaml`. |
| `kind` | required | Node kind. `req`, `asm` and `missing` are reserved. |
| `file` | required | File, relative to the root. |
| `label` | the kind | Outline group name. |
| `singular` | the label | Name shown on the detail view. |
| `color` | palette | `#rgb` or `#rrggbb`. |

### `type = "table"`

Reads rows of a Markdown table.

```toml
[[sources]]
type = "table"
kind = "need"
label = "Needs"
singular = "Need"
file = "docs/needs.md"
id = 'N-\d+'                   # required; full match on the first cell
title = 2                      # cell index of the title
title_max = 90                 # longest title; 0: no limit
title_strip = '"“”'            # characters removed from both ends of the title
min_columns = 4                # shorter rows are skipped
require = { 1 = '^SH-\d+$' }   # cell index -> regex; rows that do not match are skipped
columns = { Stakeholder = 1, Need = 2 }   # field name -> cell index
links = [{ kind = "stakeholder", column = 1, pattern = '' }]
```

Cell indexes start at 0, which is the ID cell. `title` defaults to 0, so a row without it is titled with its ID. `title_max` must not be negative, and `id` must not match an empty cell. A row whose ID is already taken by a record or an earlier row is dropped, with its links, and reported as `DUPLICATE_ID`. A missing cell gives an empty value. Each entry of `links` makes links of the given `kind` from the node to each match of `pattern` in that cell, or to the whole cell if `pattern` is empty. A link may also set `label` and `reverse_label`, the texts shown for the link and for its reverse.

`merge = true` adds the fields and links to nodes that already exist and creates nothing; rows with no such node are skipped.

### `type = "heading"`

Reads heading lines.

```toml
[[sources]]
type = "heading"
kind = "scenario"
label = "Scenarios"
file = "docs/scenarios.md"
pattern = '^#### (SC-\d+) — (.+)$'    # required; group 1 is the ID, group 2 the title
```

### `type = "yaml"`

Reads a list of mappings. It needs PyYAML (`pip install .[yaml]`). Without it, the source is skipped and a problem is reported.

```toml
[[sources]]
type = "yaml"
kind = "param"
label = "Parameters"
file = "parameters.yaml"
list_key = "parameters"    # key of the list; default "": the file itself is the list
id_key = "id"
title_key = "name"
status_key = "status"
```

Every key of an entry becomes a field, with the name capitalised. An empty value (`null`) is shown as empty text. An invalid file, a `list_key` that the file does not have, or an entry that is not a mapping or has no ID (or an empty one), is reported as a problem and skipped. The defaults of the other keys are the ones shown: `id_key = "id"`, `title_key = "name"`, `status_key = "status"`.

## Findings

The Findings view shows the built-in findings and the ones from `--findings`.

### The `--findings` file

A JSON list of objects. All four keys are required strings.

```json
[
  {"item": "L1-BRW-001", "severity": "warning", "code": "LINT_LONG",
   "message": "The statement is longer than 200 characters."},
  {"item": "", "severity": "error", "code": "LINT_FILE",
   "message": "requirements/L3.md is not listed in the index."}
]
```

- `item`: the ID of the node the finding is about, or `""` for a finding that belongs to no node.
- `severity`: `error` or `warning`.
- `code`: a short name chosen by the tool that wrote the file.
- `message`: the text shown.

Anything else (not a list, a missing key, another severity, unreadable JSON) stops the run with a one-line error and exit code 2.

### Built-in codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `FORMAT` | error | A problem found while reading a file: bad field line, unknown or duplicate field, missing ID, unclosed block, a near-miss fence or section marker, unbalanced section markers, heading that does not match the ID, unreadable file, or a source that could not be loaded. A `files.levels` glob that matches no file is a `FORMAT` warning. |
| `DUPLICATE_ID` | error | Two records, or a record and a source row, with the same ID. The first one is kept. |
| `UNKNOWN_PARENT` | error | A parent ID that has no node. |
| `DANGLING_REF` | warning | Any other reference to an ID that has no node. |
| `SELF_PARENT` | warning | A record that lists itself as its parent. The link is not drawn. |

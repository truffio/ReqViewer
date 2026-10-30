# ReqViewer

ReqViewer reads a project's requirements, kept as Markdown files, and writes one self-contained HTML page. The page has an outline, a detail view for each record, a link graph, a coverage matrix and a findings view. It makes no external requests, so you can open it from disk or send it by mail.

## Install

ReqViewer needs Python 3.11 or later and has no required dependencies.

```
pip install .
```

To read `yaml` sources (see [docs/FORMAT.md](docs/FORMAT.md)), install the optional PyYAML dependency:

```
pip install .[yaml]
```

## Quick start

From the root of this repository:

```
reqviewer --root examples/sample
```

This reads `examples/sample/reqviewer.toml` and writes `examples/sample/build/brewbox_viewer.html`. It prints the output path and the number of records, nodes and links. Open the file in a browser.

`python -m reqviewer` does the same as the `reqviewer` command. The sample has a `yaml` source: without PyYAML (`pip install .[yaml]`) that source is skipped and a problem is shown in the Findings view.

## Options

```
reqviewer [--root DIR] [--config FILE] [--out FILE] [--findings FILE]
```

- `--root DIR`: the project root. Default: the current directory. All paths in the configuration are relative to it.
- `--config FILE`: the configuration file. Default: `<root>/reqviewer.toml`. If that file does not exist, the defaults apply. An explicit `--config` that does not exist is an error.
- `--out FILE`: the page to write. Default: the `out` key of the configuration, relative to the root.
- `--findings FILE`: a JSON file of extra findings to show in the page, for example from your own lint tool.

Exit code 0 means the page was written. Exit code 2 means a bad configuration or findings file, or an unreadable path; the error is printed on one line. Problems in the requirement files do not stop the run: they appear in the Findings view.

## Use it on your own requirements

1. **Install ReqViewer.** Run `pip install .` from a clone of this repository, or `pip install .[yaml]` if you have YAML sources. Your project needs no copy of ReqViewer.

2. **Put the requirements in level files.** With the defaults, these are `requirements/L0.md`, `requirements/L1.md` and so on, one file per level. In each file, write the records as fenced blocks. Links between records are written in their fields (see [How traceability is encoded](#how-traceability-is-encoded)).

   ````
   ### L1-MOT-001

   ```req
   ID: L1-MOT-001
   Type: Functional
   Statement: The motor shall deliver the torque in PRM-001.
   Parent(s): L0-SYS-001
   Source: N-001
   Status: Draft
   ```
   ````

   A top-level record has `Parent(s): —`. To group records, use the section markers described in [docs/FORMAT.md](docs/FORMAT.md#sections).

3. **Do a first run with the defaults.** You need no configuration file yet:

   ```
   reqviewer --root path/to/project
   ```

   This writes `build/requirements_viewer.html` in the project. To leave the project untouched, add `--out` with a path outside it. Open the page and go to the Findings view. A wrong file path or a malformed record shows up there, not as an error.

4. **Add `reqviewer.toml` to the project root.** Start with the title and your ID patterns. The default pattern takes any capitalised text ending in `-<digits>` as an ID, so a citation like `ISO-9001` becomes a link to a record that does not exist.

   ```toml
   title = "Pump requirements"
   out = "build/pump_viewer.html"

   [format]
   heading_must_match_id = true

   [ids]
   patterns = ['L\d-[A-Z]+-\d+', 'N-\d+', 'DD-\d+', 'PRM-\d+']
   ```

   If your files or field names differ, set `files.levels` and the `[fields]` roles. For example, `parents = "Traces to"` reads parents from a field named `Traces to`.

5. **Add the optional links.** `derived` and `uses` links are off until you set their patterns:

   ```toml
   [links]
   derived_pattern = 'Derived\s*\(\s*(DD-\d+)\s*\)'
   uses_pattern = 'PRM-\d+'
   uses_fields = ["Statement"]
   ```

6. **Add sources for what is not a requirement.** Needs, decisions and parameters kept in Markdown tables, headings or YAML become nodes when listed as `[[sources]]`. Without a source, an ID such as `N-001` has no node and is reported as undefined.

   ```toml
   [[sources]]
   type = "table"
   kind = "need"
   label = "Needs"
   singular = "Need"
   file = "docs/needs.md"
   id = 'N-\d+'
   title = 1
   ```

7. **Run it again and clear the findings.** A finding marks a broken link or a format error. To add checks of your own, pass them with `--findings`.

`examples/sample/` is a complete project to copy from.

## How traceability is encoded

There is no separate trace file or matrix. Traceability is in the records themselves: a link exists because a field of one record contains the ID of another. Each link is written once, on one record, and the page shows it from both ends.

An ID is any text that matches `ids.patterns`, and the match must be exact. Which link it makes depends on the field it is in:

| Link | Written as | Direction | Shown as | Needs |
| --- | --- | --- | --- | --- |
| `parent` | `Parent(s): L0-SYS-001, L0-SYS-002` | parent → this record | decomposes / decomposed by | nothing |
| `derived` | `Parent(s): Derived (DD-001)` | decision → this record | derives / derived from | `links.derived_pattern` |
| `uses` | `PRM-001` in a field of `uses_fields` | this record → parameter | uses / used by | `links.uses_pattern`, `links.uses_fields` |
| `source` | `Source: N-001` | this record → source | source / cited as source by | nothing |
| `refers` | an ID in any other field | this record → that ID | refers to / referred to by | nothing |
| `affects` | `Affects: L1-MOT-001` on an assumption | assumption → that ID | affects / affected by | nothing |

- **One link per ID:** an ID already linked as a parent, a derived target or a `uses` target does not also get a `refers` link.
- **Assumptions:** they make `parent`, `derived` and `affects` links only. By default, `affects` reads both the `Affects` and `Rationale` fields.
- **No parent:** `Parent(s): —` means the record has none. `links.none_value` sets that text.
- **Sources:** a `table` source can add links of its own, from one of its cells to the IDs in it. The sample links each scenario to the needs it exercises this way. See [docs/FORMAT.md](docs/FORMAT.md#type--table).
- **Field names:** `Parent(s)` is a role, set by `fields.parents`. `Source`, `Affects` and the other link fields are set in `[links]`.

An ID that nothing defines still appears, as a placeholder node, so a broken link stays visible. A missing parent gives the error `UNKNOWN_PARENT`, and any other missing target gives the warning `DANGLING_REF`. A record that names itself as parent gives `SELF_PARENT`, and no link is drawn.

## More

- [docs/FORMAT.md](docs/FORMAT.md): the record format, every configuration key, the source types, the findings file and the finding codes.
- `examples/sample/` is a small invented project. `examples/aircraft/` shows a larger configuration.

## License

MIT. See [LICENSE](LICENSE).

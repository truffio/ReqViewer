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

## More

- [docs/FORMAT.md](docs/FORMAT.md): the record format, every configuration key, the source types, the findings file and the finding codes.
- `examples/sample/` is a small invented project. `examples/aircraft/` shows a larger configuration.

## License

MIT. See [LICENSE](LICENSE).

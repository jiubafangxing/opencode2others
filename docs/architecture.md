# Architecture

This document explains how `opencode2others` is put together and how to extend
it. It is aimed at contributors rather than end users.

- [Design goals](#design-goals)
- [Package layout](#package-layout)
- [Data flow](#data-flow)
- [Core types](#core-types)
- [Catalog resolution](#catalog-resolution)
- [Targets](#targets)
- [The TOML codec](#the-toml-codec)
- [CLI orchestration](#cli-orchestration)
- [Error handling](#error-handling)
- [Testing](#testing)
- [Adding a new target](#adding-a-new-target)

## Design goals

1. **Zero runtime dependencies.** The tool must run on a bare Python install,
   including Python 3.9/3.10 where `tomllib` does not exist. This is why a
   small TOML reader/writer lives in the repo.
2. **Never guess a protocol.** A model is only written if a protocol source
   (docs table or live probe) confirms it. Anything else is reported and
   skipped.
3. **Be a good citizen with dotfiles.** Existing config files are merged and
   always backed up before being rewritten.
4. **Make new agents easy.** All agent-specific logic is isolated behind a
   single `Target` interface.

## Package layout

```
opencode2others/
├── __init__.py        # version
├── __main__.py        # python -m opencode2others
├── errors.py          # OpenCode2OthersError / CatalogError / TargetError / TomlError
├── protocol.py        # Protocol enum + endpoint <-> protocol mapping
├── model.py           # Model dataclass + Model.from_metadata()
├── catalog.py         # HTTP, docs scraping, probing, Catalog assembly
├── credentials.py     # recover an API key from existing local configs
├── util.py            # home dir, JSON I/O, deep merge, atomic-ish writes
├── toml_io.py         # minimal TOML reader/writer (Codex)
├── cli.py             # argparse, target resolution, orchestration
└── targets/
    ├── __init__.py    # TARGET_CLASSES / TARGETS registry
    ├── base.py        # Target ABC + Context
    ├── pi.py
    ├── claude_code.py
    ├── codex.py
    └── zcode.py
```

The dependency direction is strictly one way:

```
cli -> targets -> (model, protocol, util, errors)
cli -> catalog  -> (model, protocol, errors)
targets.codex  -> toml_io
```

`model`, `protocol`, `util`, `errors` and `toml_io` have no knowledge of any
specific agent.

## Data flow

```
                 load_catalog(base_url, ...)
                          │
      ┌───────────────────┼────────────────────┐
      ▼                   ▼                    ▼
 fetch_model_ids()   fetch_metadata()   fetch_doc_endpoints()
 (GET /v1/models)    (GET models.dev)   (GET docs, scrape <table>)
      │                   │                    │
      └──────────┬────────┘                    │
                 ▼                             │  (or probe_endpoint()
        endpoints resolved ◄───────────────────┘   with --probe)
                 │
                 ▼
          list[Model]  ──►  Catalog(models, unresolved, missing_metadata)
                 │
                 ▼
   for each Target:  filter() -> render() -> write_text()
```

## Core types

### `Protocol` (`protocol.py`)

A `str`-Enum whose values are exactly the strings Pi uses for its `api` field:

| Member | Value |
| ------ | ----- |
| `OPENAI_CHAT` | `openai-completions` |
| `OPENAI_RESPONSES` | `openai-responses` |
| `ANTHROPIC` | `anthropic-messages` |

It also exposes `.endpoint` (e.g. `chat/completions`) and `.label` via the
`ENDPOINT_TO_PROTOCOL` / `PROTOCOL_TO_ENDPOINT` maps.

### `Model` (`model.py`)

A provider-neutral dataclass: `id`, `name`, `protocol`, `context_window`,
`max_tokens`, `reasoning`, `vision`, `cost`, `input_modalities`.
`Model.from_metadata(id, meta, protocol)` converts a models.dev entry into a
`Model`, tolerating missing fields.

### `Context` (`targets/base.py`)

Everything a target needs that is not the model list: provider id/name, base
URL, the API-key env var name, the resolved key (or `None`), and the merge flag.
`ctx.api_key_value` returns the literal key or `$ENV_VAR`.

## Catalog resolution

`load_catalog()` in `catalog.py` orchestrates:

1. **Model ids** — `GET {base_url}/models`.
2. **Metadata** — `GET https://models.dev/api.json`, provider `opencode-go`.
   Best effort: failures warn and yield empty metadata.
3. **Protocols**:
   - with `--probe`: `probe_endpoint()` sends a 1-token request to each of
     `/chat/completions`, `/responses`, `/messages`. A `404`/`405` means "no
     such route"; any other status means the route exists. The first hit wins.
   - otherwise, `fetch_doc_endpoints()` scrapes the live docs page. The
     `_HtmlTableParser` collects every `<table>`; `parse_endpoint_table()`
     picks the one with the `Model` / `Model ID` header and normalises the
     endpoint URL.
   - probe misses are filled in from the docs table, so the two strategies
     compose.
4. **Assembly** — models absent from every protocol source land in
   `Catalog.unresolved` and are skipped.

All HTTP goes through `http_get_text()` / `http_get_json()` which set a
`User-Agent` and retry transient network errors with a short backoff.

## Targets

`Target` is a small ABC:

```python
class Target(ABC):
    key: str
    label: str
    protocols: tuple[Protocol, ...] | None = None

    def default_path(self) -> Path: ...
    def render(self, models, ctx, path) -> str: ...
    def filter(self, models) -> list[Model]: ...   # provided
    @classmethod
    def add_arguments(cls, parser): ...            # provided (no-op)
```

`add_arguments()` lets a target contribute its own CLI flags; the CLI always
calls it for every registered target, so target-specific options exist
regardless of `--target`.

Each target is responsible for its own merge logic because only it knows the
file format. `write_text()` handles the `.bak` backup.

## The TOML codec

`toml_io.py` exists solely because Codex needs TOML and the project cannot
depend on `tomli`/`tomli-w`. It implements enough of TOML 1.0 for real-world
Codex configs:

- `[table]` and `[[array.of.tables]]`
- dotted keys, bare/quoted keys
- basic/literal strings, single and multi-line (with line continuation)
- booleans, ints (dec/hex/oct/bin), floats, arrays, inline tables

The reader is a recursive-descent parser over the text; the writer emits
scalars before sub-tables so output is re-parseable.

**Merge strategy:** `CodexTarget.render()` parses the existing file, updates
`model`, `model_provider`, `model_providers` and `profiles`, then re-serialises
the whole document. This preserves the *data* but not the original formatting
or comments. If parsing fails, the exception propagates and the CLI reports it
without writing — the old file is never destroyed.

## CLI orchestration

`cli.main()`:

1. Parse arguments (`build_parser()` registers common flags plus every target's).
2. Expand `--target` (default `all`) into an ordered, de-duplicated list of keys.
3. Resolve the API key (`_resolve_key()`): `--api-key` → `$api_key_env` →
   `credentials.discover_api_key()` unless `--no-key-discovery`.
4. `load_catalog()`.
5. If `--list`, print the table and exit.
6. `run()`: build the `Context`, then for each target resolve the path, filter
   models, render and write (or print with `--dry-run`).
7. `--write-auth` is applied only for the `pi` target.

Path resolution precedence: `--<target>-output` → `-o/--output` (single target
only) → `default_path()` (which honours the per-tool env var).

## Error handling

All recoverable problems raise subclasses of `OpenCode2OthersError`:

| Exception | Meaning |
| --------- | ------- |
| `OpenCode2OthersError` | base class |
| `CatalogError` | upstream catalog unreadable |
| `TargetError` | a target cannot build its config (e.g. no compatible model, unknown `--codex-model`) |
| `TomlError` | invalid TOML while merging |

The CLI catches these, prints `[error] ...` to stderr and returns exit code `1`.
Per-target failures inside `run()` do not abort the remaining targets; the final
exit code reflects whether any target failed.

## Testing

`tests/` uses the standard-library `unittest` runner:

```bash
python -m unittest discover -v
```

- `test_toml_io.py` — parser/writer round-trips, quoting, scalar ordering.
- `test_catalog.py` — docs table extraction; protocol mapping invariants.
- `test_targets.py` — renders all four targets from an in-memory model list and
  checks protocol filtering, base-URL normalisation and merge behaviour.

The suite never touches the network; catalog assembly is not exercised end to
end, only its pure helpers.

## Adding a new target

1. `opencode2others/targets/<key>.py` — subclass `Target`, set `key`, `label`,
   `protocols`, implement `default_path()` and `render()`, optionally
   `add_arguments()`.
2. Register it in `opencode2others/targets/__init__.py`'s `TARGET_CLASSES`.
3. Add tests in `tests/test_targets.py`.
4. Document it in `docs/targets.md`, the README tables and `CHANGELOG.md`.

Keep the new module free of imports from other target modules; share code by
putting it in `util.py` or `targets/base.py` instead.

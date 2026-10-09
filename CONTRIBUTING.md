# Contributing

Thanks for taking the time to contribute! This document explains how to set up
the project, run the tests and add a new target.

## Development setup

The project targets Python 3.9+ and has **no runtime dependencies**. A virtual
environment is recommended:

```bash
git clone https://github.com/jiubafangxing/opencode2others.git
cd opencode2others
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # optional tools: pytest, ruff
```

You can run the tool directly from a checkout without installing:

```bash
python -m opencode2others --help
```

## Running the tests

The suite uses the standard library `unittest`, so no dependencies are needed:

```bash
python -m unittest discover -v
```

If you have `pytest`, this also works:

```bash
pytest
```

The tests never hit the network: catalog parsing and target rendering are
exercised with fixtures.

## Linting

```bash
ruff check .
ruff format .        # optional
```

The configured line length is 100 characters.

## Project layout

```
opencode2others/
├── opencode2others/
│   ├── catalog.py        # fetch model ids / metadata / protocols
│   ├── credentials.py    # discover an existing API key from local configs
│   ├── cli.py            # argument parsing + orchestration
│   ├── errors.py         # exception hierarchy
│   ├── model.py          # provider-neutral Model dataclass
│   ├── protocol.py       # Protocol enum + endpoint mapping
│   ├── toml_io.py        # minimal TOML reader/writer (Codex)
│   ├── util.py           # filesystem / JSON helpers
│   └── targets/
│       ├── base.py       # Target ABC + Context
│       ├── pi.py
│       ├── claude_code.py
│       ├── codex.py
│       └── zcode.py
├── tests/
├── docs/
├── fetch_opencode_go_models.py   # legacy shim
└── pyproject.toml
```

## Adding a new target

1. Create `opencode2others/targets/<name>.py` with a `Target` subclass.
2. Declare `key`, `label` and `protocols` (or `None` for all). Implement
   `default_path()` and `render(models, ctx, path)`.
3. Register the class in `opencode2others/targets/__init__.py` (`TARGET_CLASSES`).
4. Add unit tests in `tests/test_targets.py`.
5. Document the file path, format and any caveats in `docs/targets.md` and the
   README tables.

### Target contract

```python
class MyTarget(Target):
    key = "my-agent"
    label = "My Agent"
    protocols = (Protocol.OPENAI_CHAT,)   # or None

    def default_path(self) -> Path:
        return home_dir() / ".my-agent" / "config.json"

    def render(self, models, ctx, path) -> str:
        # `models` is the full catalog; call `self.filter(models)` first.
        # `ctx.merge` tells you whether to merge with an existing file.
        return dump_json({...})
```

Targets must:

* never embed a secret unless the user supplied one (`ctx.resolved_key`),
* create a `.bak` backup when merging (handled by `write_text`, which the CLI
  calls for every target),
* raise `TargetError` with a clear message when no model is compatible.

## Commit / PR guidelines

* Keep pull requests focused; one feature or fix per PR.
* Update `CHANGELOG.md` under `## [Unreleased]`.
* Make sure `python -m unittest` and `ruff check .` pass.
* Avoid adding runtime dependencies; the standard library is a feature.

## Reporting bugs

Please include:

* the command you ran,
* the Python version and OS,
* the generated file (redact API keys!),
* any output from `--dry-run` or `--verbose`.

## Security

Never paste real API keys into issues, PRs or test fixtures. If you discover a
credential leak, rotate the key immediately.

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Automatic API key discovery.** If no `--api-key`/`$OPENCODE_API_KEY` is
  supplied, the key is recovered from existing local configs (Pi `auth.json` and
  `models.json`, ZCode `config.json`, Claude Code `settings.json` when the base
  URL matches, and Codex `auth.json`). Disable with `--no-key-discovery`. The
  chosen source is printed with the secret masked.
- Documentation set: `README.md`, `README.zh-CN.md`, `docs/targets.md`,
  `docs/architecture.md`, `CONTRIBUTING.md`.

## [0.2.0] - 2026-10-09

### Added

- **Project structure.** The single `fetch_opencode_go_models.py` script grew
  into an installable, dependency-free Python package.
- **Pluggable targets.** `pi`, `claude-code`, `codex` and `zcode` are now
  independent generators behind a common `Target` interface.
- `--target/-t` (repeatable, or `all`) and per-target output path overrides.
- `--dry-run` to preview every generated file without touching disk.
- Automatic backups (`<file>.bak`) before overwriting existing configs, and a
  `--no-merge` escape hatch.
- A dependency-free TOML reader/writer (`opencode2others.toml_io`) so Codex
  configs can be merged on Python 3.9/3.10 where `tomllib` is unavailable.
- `pyproject.toml` with a console-script entry point and packaging metadata.
- A unit-test suite (`python -m unittest`) covering the TOML codec, the docs
  table parser and all four targets.

### Changed

- `fetch_opencode_go_models.py` is now a backwards-compatible shim that
  forwards to `opencode2others --target pi`.

## [0.1.0] - 2025

### Added

- Initial single-file script that generated a Pi `models.json` from the
  OpenCode Go catalog, scraping the docs endpoint table for protocols.

[Unreleased]: https://github.com/jiubafangxing/opencode2others/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jiubafangxing/opencode2others/releases/tag/v0.2.0

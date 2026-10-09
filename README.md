# opencode2others

**Turn one [OpenCode Go](https://opencode.ai/docs/go/) subscription into ready-to-use configuration files for Pi, Claude Code, OpenAI Codex and ZCode — from a single command.**

`opencode2others` reads the live OpenCode Go model catalog, discovers which
wire protocol each model speaks, and writes (or merges into) the config file of
every coding agent you use. No hand-maintained model lists, no copy-pasting API
keys between tools.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#requirements)
[![CI](https://github.com/jiubafangxing/opencode2others/actions/workflows/ci.yml/badge.svg)](https://github.com/jiubafangxing/opencode2others/actions/workflows/ci.yml)

---

## Table of contents

- [Why](#why)
- [Supported targets](#supported-targets)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Authentication](#authentication)
- [Usage](#usage)
- [CLI reference](#cli-reference)
- [What gets written](#what-gets-written)
- [How it works](#how-it-works)
- [Protocol and base-URL handling](#protocol-and-base-url-handling)
- [Merging and backups](#merging-and-backups)
- [Environment variables](#environment-variables)
- [Documentation](#documentation)
- [Development](#development)
- [FAQ and troubleshooting](#faq-and-troubleshooting)
- [Security](#security)
- [License](#license)

---

## Why

Models served by the OpenCode Go plan are spread across **three different wire
protocols** (`/chat/completions`, `/responses` and `/messages`) and each coding
agent only understands a subset of them:

- **Claude Code** only speaks Anthropic Messages.
- **Codex** only speaks OpenAI Chat or Responses, and one provider has a single
  `wire_api`.
- **Pi** speaks everything.
- **ZCode** speaks Anthropic and OpenAI, but not Responses.

Keeping four config files in sync by hand is tedious and error-prone.
`opencode2others` does it for you:

1. fetches the live model list from the OpenCode Go API,
2. enriches it with metadata from [models.dev](https://models.dev),
3. resolves each model's protocol from the docs (or with a live probe),
4. writes the right file for each agent, filtering to the protocols it supports.

## Supported targets

| Target            | Config file                        | Protocols consumed                              | Notes |
| ----------------- | ---------------------------------- | ----------------------------------------------- | ----- |
| `pi`              | `~/.pi/agent/models.json`          | all                                             | full fidelity |
| `claude-code`     | `~/.claude/settings.json`          | `anthropic-messages` only                       | writes `ANTHROPIC_*` env vars |
| `codex`           | `~/.codex/config.toml`             | `openai-completions`, `openai-responses`        | one provider per `wire_api`, one profile per model |
| `zcode`           | `~/.zcode/v2/config.json`          | `anthropic-messages`, `openai-completions`      | one provider group per `kind` |

## Requirements

- **Python 3.9+**.
- **No third-party dependencies** — the standard library only. The Codex TOML
  read/write support is bundled (`opencode2others.toml_io`) so it works even on
  Python 3.9/3.10 where `tomllib` does not exist.
- Network access to `opencode.ai`, `models.dev` and your configured base URL.

## Installation

### pip / pipx

```bash
pipx install opencode2others      # recommended for CLI tools
# or
pip install opencode2others
```

### Run without installing

```bash
git clone https://github.com/jiubafangxing/opencode2others.git
cd opencode2others
python -m opencode2others --help
```

### From source (editable)

```bash
pip install -e ".[dev]"
```

## Quick start

```bash
# One command, every agent, key stored for Pi too:
opencode2others --api-key sk-... --write-auth

# Only Pi:
opencode2others --target pi --write-auth

# Preview everything first, touching nothing:
opencode2others --dry-run
```

The key can also come from the environment so it never lands in your shell
history:

```bash
export OPENCODE_API_KEY=sk-...
opencode2others
```

> Existing config files are **merged** and backed up to `<file>.bak` before being
> rewritten. Pass `--no-merge` to overwrite instead. See
> [Merging and backups](#merging-and-backups).

## Authentication

Credentials are resolved in this order:

1. `--api-key sk-...` (literal, highest priority).
2. `$OPENCODE_API_KEY` (or the variable named by `--api-key-env`).
3. **Auto-discovery** from existing local configs — Pi `auth.json` /
   `models.json`, ZCode `config.json`, Claude Code `settings.json` (only when
   its base URL matches) and Codex `auth.json`. Disable with
   `--no-key-discovery`.

The source is printed (masked) so you always know which key was used.

If no key is available the tool still runs — it just writes a `${OPENCODE_API_KEY}`
reference where the target supports it and leaves `apiKey` empty where it does
not. Endpoints that need a key at request time (`--probe`, `--write-auth`)
require one up front.

Where the key ends up:

| Target        | Key location |
| ------------- | ------------ |
| `pi`          | `apiKey` in `models.json`; `--write-auth` also writes `~/.pi/agent/auth.json` |
| `claude-code` | `ANTHROPIC_AUTH_TOKEN` in `settings.json` |
| `codex`       | **not written** — Codex reads it from the env var named by `env_key` (`OPENCODE_API_KEY` by default) |
| `zcode`       | `provider.<id>.options.apiKey` |

## Usage

### Generate for all agents

```bash
opencode2others --api-key sk-...
```

### Generate for a single agent

```bash
opencode2others --target codex
opencode2others --target claude-code --claude-model qwen3.8-max
opencode2others --target zcode
```

`--target` is repeatable:

```bash
opencode2others -t pi -t codex
```

### Preview without writing

```bash
opencode2others --dry-run
opencode2others --target codex --dry-run
```

### List models and their protocols

```bash
opencode2others --list
```

```
MODEL ID                       PROTOCOL (Pi api)          CTX       OUT  NAME
------------------------------------------------------------------------------------------
minimax-m3                     anthropic-messages     1000000    131072  MiniMax-M3
kimi-k3                        openai-completions     1048576    131072  Kimi K3
gpt-6-luna                     openai-responses       1050000    128000  GPT-6 Luna
...
```

### Detect protocols with a live probe

Scraping the docs table is fast and free; if you want ground truth, `--probe`
sends one tiny request per model and records which endpoint answers:

```bash
opencode2others --probe
```

`--probe` first tries each endpoint, then falls back to the docs table for any
model it could not classify. It consumes a negligible amount of usage.

### Custom provider or base URL

```bash
opencode2others \
  --base-url https://opencode.ai/zen/go/v1 \
  --provider-id opencode-go \
  --provider-name "OpenCode Go"
```

### Set a default model

`--model ID` (alias `--default-model`) sets the preferred startup model for
**every target that can speak its protocol**:

| Target | Effect of `--model ID` |
| ------ | ---------------------- |
| `pi` | writes `defaultProvider` + `defaultModel` to `~/.pi/agent/settings.json` |
| `codex` | sets the top-level `model` and its matching profile |
| `zcode` | lists the model first within its provider group |
| `claude-code` | applied **only if** the model speaks `anthropic-messages` |

```bash
opencode2others --model deepseek-v4.1-flash
```

> **Claude Code speaks Anthropic Messages only.** Many OpenCode models —
> including `deepseek-v4.1-flash`, which is served over `/chat/completions` —
> simply cannot be used by Claude Code. When `--model` names such a model the
tool warns and keeps an Anthropic-compatible model. See exactly which models
> are eligible:
>
> ```bash
> opencode2others --list | grep anthropic-messages
> ```

Override the Claude Code slots explicitly:

```bash
# main / opus / sonnet / subagent, and the small/fast haiku slot
opencode2others --target claude-code \
  --claude-model qwen3.8-max \
  --claude-haiku-model qwen3.8-flash

# Codex: the top-level `model` (and the matching profile)
opencode2others --target codex --codex-model glm-5.3
```

## CLI reference

| Option | Description | Default |
| ------ | ----------- | ------- |
| `--target, -t TARGET` | Target to generate. Repeatable. `all` expands to every target. | `all` |
| `--list` | Print the resolved model/protocol table and exit. | off |
| `--probe` | Detect protocols with live 1-token requests. Requires a key. | off |
| `--merge` / `--no-merge` | Merge into (default) or overwrite existing files. | merge |
| `--api-key KEY` | API key to embed. | `$--api-key-env` |
| `--api-key-env NAME` | Env var that holds the key. | `OPENCODE_API_KEY` |
| `--no-key-discovery` | Do not read the key from existing local configs. | off |
| `--base-url URL` | OpenCode Go API base URL. | `https://opencode.ai/zen/go/v1` |
| `--provider-id ID` | Provider id used in generated configs. | `opencode-go` |
| `--provider-name NAME` | Provider display name. | `OpenCode Go` |
| `--model, --default-model ID` | Preferred startup model; applied per protocol (see below). | unset |
| `--timeout SECONDS` | HTTP timeout. | `30` |
| `-o, --output PATH` | Output path override (single target only). | target default |
| `--dry-run` | Print generated files instead of writing them. | off |
| `-v, --verbose` | Extra diagnostics. | off |
| `--version` | Show version and exit. | |
| `--pi-output PATH` | Override `models.json` path. | `~/.pi/agent/models.json` |
| `--auth-file, --pi-auth-file PATH` | Override `auth.json` path. | `~/.pi/agent/auth.json` |
| `--write-auth` | Also store the key in Pi's `auth.json`. | off |
| `--claude-output PATH` | Override `settings.json` path. | `~/.claude/settings.json` |
| `--claude-model ID` | `ANTHROPIC_MODEL`. | first Anthropic model |
| `--claude-opus-model ID` | `ANTHROPIC_DEFAULT_OPUS_MODEL`. | main model |
| `--claude-sonnet-model ID` | `ANTHROPIC_DEFAULT_SONNET_MODEL`. | main model |
| `--claude-haiku-model ID` | `ANTHROPIC_DEFAULT_HAIKU_MODEL`. | first small/fast match, else main |
| `--claude-subagent-model ID` | `CLAUDE_CODE_SUBAGENT_MODEL`. | main model |
| `--claude-timeout-ms MS` | `API_TIMEOUT_MS`. | unset |
| `--codex-output PATH` | Override `config.toml` path. | `~/.codex/config.toml` |
| `--codex-model ID` | Top-level `model` + default profile. | first OpenAI model |
| `--codex-api-key-env NAME` | `env_key` Codex reads the key from. | `--api-key-env` |
| `--zcode-output PATH` | Override `config.json` path. | `~/.zcode/v2/config.json` |

## What gets written

### Pi — `~/.pi/agent/models.json`

```json
{
  "providers": {
    "opencode-go": {
      "name": "OpenCode Go",
      "baseUrl": "https://opencode.ai/zen/go/v1",
      "apiKey": "sk-...",
      "api": "openai-completions",
      "models": [
        {
          "id": "minimax-m3",
          "name": "MiniMax-M3",
          "reasoning": true,
          "input": ["text", "image"],
          "contextWindow": 1000000,
          "maxTokens": 131072,
          "cost": { "input": 0.3, "output": 1.2, "cacheRead": 0.06, "cacheWrite": 0 },
          "api": "anthropic-messages"
        }
      ]
    }
  }
}
```

The most common protocol becomes the provider-level `api`; models that differ
carry their own `api` field.

### Claude Code — `~/.claude/settings.json`

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://opencode.ai/zen/go",
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "ANTHROPIC_MODEL": "qwen3.8-max",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "qwen3.8-max",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "qwen3.8-max",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "qwen3.8-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "qwen3.8-max"
  }
}
```

Unrelated keys already present in `settings.json` (`theme`, `mcpServers`, ...)
are preserved.

### Codex — `~/.codex/config.toml`

```toml
model = "glm-5.3"
model_provider = "opencode-go"

[model_providers.opencode-go]
name = "OpenCode Go"
base_url = "https://opencode.ai/zen/go/v1"
env_key = "OPENCODE_API_KEY"
wire_api = "chat"

[model_providers.opencode-go-responses]
name = "OpenCode Go (Responses)"
base_url = "https://opencode.ai/zen/go/v1"
env_key = "OPENCODE_API_KEY"
wire_api = "responses"

[profiles.'opencode-go-glm-5.3']
model = "glm-5.3"
model_provider = "opencode-go"
```

Switch models with a profile:

```bash
codex --profile opencode-go-glm-5.3
```

Remember to `export OPENCODE_API_KEY=sk-...`.

### ZCode — `~/.zcode/v2/config.json`

```json
{
  "provider": {
    "opencode-go": {
      "name": "OpenCode Go",
      "kind": "anthropic",
      "options": { "apiKey": "sk-...", "baseURL": "https://opencode.ai/zen/go" },
      "enabled": true,
      "source": "custom",
      "models": {
        "qwen3.8-max": {
          "name": "Qwen3.8 Max",
          "reasoning": { "enabled": true, "variants": ["enabled", "off"], "defaultVariant": "enabled" },
          "limit": { "context": 1000000, "output": 131072 },
          "modalities": { "input": ["text"], "output": ["text"] },
          "zcode": { "modified": false, "priority": 1 }
        }
      }
    },
    "opencode-go-openai": {
      "name": "OpenCode Go (OpenAI)",
      "kind": "openai",
      "options": { "apiKey": "sk-...", "baseURL": "https://opencode.ai/zen/go/v1" },
      "enabled": true,
      "source": "custom",
      "models": { "...": {} }
    }
  }
}
```

## How it works

```
                 ┌─────────────────────────────────────────────┐
                 │ 1. GET /zen/go/v1/models                    │
                 │    -> live model ids                        │
                 ├─────────────────────────────────────────────┤
                 │ 2. GET models.dev/api.json                  │
                 │    provider "opencode-go"                   │
                 │    -> name, limits, cost, reasoning, vision │
                 ├─────────────────────────────────────────────┤
                 │ 3. Resolve protocol per model               │
                 │    a) --probe live requests, else           │
                 │    b) scrape /docs/go endpoint table        │
                 └─────────────────────────────────────────────┘
                                    │
                        list[Model] │ (id, name, protocol, ...)
                                    ▼
        ┌───────────────┬───────────────┬───────────────┬───────────────┐
        │  Pi target    │ Claude target │ Codex target  │ ZCode target  │
        │  all protocols│ anthropic only│ chat/responses│ anthropic+chat│
        └───────────────┴───────────────┴───────────────┴───────────────┘
```

### Data sources

| Source | Used for | Required |
| ------ | -------- | -------- |
| `GET https://opencode.ai/zen/go/v1/models` | live model membership | yes |
| `GET https://models.dev/api.json` | metadata (name, limits, cost, reasoning, vision) | optional (warn + defaults) |
| `GET https://opencode.ai/docs/go/` | per-model protocol table | yes unless `--probe` |
| live `POST` probes | ground-truth protocol | only with `--probe` |

Models that appear in `/v1/models` but not in the protocol source are skipped
and reported — the tool never guesses a protocol.

Metadata is intentionally best-effort: if models.dev is unreachable the config
still gets written, just with `name = id` and no limits/pricing.

## Protocol and base-URL handling

OpenCode endpoints map to protocols like this:

| OpenCode endpoint | Pi `api` | Codex `wire_api` | ZCode `kind` |
| ----------------- | -------- | ---------------- | ------------ |
| `/v1/chat/completions` | `openai-completions` | `chat` | `openai` |
| `/v1/responses` | `openai-responses` | `responses` | — (skipped) |
| `/v1/messages` | `anthropic-messages` | — (skipped) | `anthropic` |

Each agent expects the base URL in a slightly different shape, so the tool
normalises it per target:

| Target | Field | Value |
| ------ | ----- | ----- |
| Pi | `baseUrl` | `https://opencode.ai/zen/go/v1` |
| Claude Code | `ANTHROPIC_BASE_URL` | `https://opencode.ai/zen/go` (client appends `/v1/messages`) |
| Codex | `model_providers.*.base_url` | `https://opencode.ai/zen/go/v1` (client appends the endpoint) |
| ZCode (`anthropic`) | `options.baseURL` | `https://opencode.ai/zen/go` |
| ZCode (`openai`) | `options.baseURL` | `https://opencode.ai/zen/go/v1` |

## Merging and backups

By default the tool **merges** into existing files so your other providers,
themes, MCP servers and profiles survive. Every file is backed up to
`<file>.bak` immediately before it is rewritten.

Merge behaviour per target:

| Target | Merge semantics |
| ------ | --------------- |
| Pi | deep-merges so other providers stay; `opencode-go` is updated |
| Claude Code | deep-merges `env`, keeps `theme`, `mcpServers`, ... |
| Codex | keeps existing tables; updates `model`, `model_provider`, and the managed providers/profiles |
| ZCode | deep-merges the `provider` map |

Use `--no-merge` to replace files wholesale (still with a `.bak`).

## Environment variables

| Variable | Effect |
| -------- | ------ |
| `OPENCODE_API_KEY` | Default credential (change the name with `--api-key-env`). |
| `PI_CODING_AGENT_DIR` | Pi agent dir; default `~/.pi/agent`. |
| `CLAUDE_CONFIG_DIR` | Claude config dir; default `~/.claude`. |
| `CODEX_HOME` | Codex home; default `~/.codex`. |
| `ZCODE_HOME` | ZCode home; default `~/.zcode`. |

## Documentation

| Document | Contents |
| -------- | -------- |
| [`README.md`](README.md) | This file — overview, install, usage and CLI reference. |
| [`README.zh-CN.md`](README.zh-CN.md) | Chinese translation. |
| [`docs/manual.zh-CN.md`](docs/manual.zh-CN.md) | Operations manual (Chinese): daily tasks, per-tool verification, rollback, troubleshooting. |
| [`docs/targets.md`](docs/targets.md) | Per-target formats, options, merge semantics and the protocol matrix. |
| [`docs/architecture.md`](docs/architecture.md) | Internal design and how to add a new target. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development setup and contribution guidelines. |
| [`SECURITY.md`](SECURITY.md) | How keys are handled and how to report issues. |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history. |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community expectations. |

## Development

```bash
python -m unittest discover -v   # test suite (no network)
ruff check .                     # lint (optional)
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the layout, the target contract and
how to add support for a new agent. See [`docs/architecture.md`](docs/architecture.md)
for a deeper walkthrough and [`docs/targets.md`](docs/targets.md) for per-target
details.

## FAQ and troubleshooting

**`[warn] N model(s) not in the endpoint table; skipped: ...`**
Those models are listed by the API but not documented on the protocols page.
They are intentionally skipped rather than guessed. Use `--probe` to classify
them with live requests.

**Codex doesn't pick up the key.**
Codex reads the key from the environment variable named by `env_key`. Either
`export OPENCODE_API_KEY=sk-...` or pass `--codex-api-key-env MY_VAR` and export
that variable.

**Claude Code says the token is invalid.**
Make sure `ANTHROPIC_BASE_URL` has no trailing `/v1`; Claude Code appends
`/v1/messages` itself. Use `--claude-model` to select a model that is served
over the Anthropic protocol (`opencode2others --list` shows the protocol).

**ZCode ignores some models.**
ZCode has no Responses wire kind, so `openai-responses` models are skipped with
a warning. The remaining models are written under an `anthropic` and/or
`openai` provider group.

**I want to undo a run.**
Restore the matching `<file>.bak`. Git-versioning your dotfiles also helps.

**Does this send my key anywhere?**
Only to `opencode.ai` (and only if you use `--probe`). Metadata and the docs
table are fetched anonymously from `models.dev` and `opencode.ai`.

## Security

- Prefer the `OPENCODE_API_KEY` environment variable over `--api-key` so the key
  is not recorded in shell history.
- The tool writes `.bak` copies of your config files; those backups contain the
  same secrets, so keep them out of version control (the bundled `.gitignore`
  already excludes `auth.json` and `models.json`).
- Pi's `auth.json` is written with `0600` permissions on POSIX systems.
- Never paste real keys into issues or pull requests.

## License

[MIT](LICENSE) © opencode2others contributors.

OpenCode, Pi, Claude Code, OpenAI Codex and ZCode are projects of their
respective owners. This tool is unofficial and not affiliated with any of them.

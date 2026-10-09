# Targets

This document describes every output target in detail: where the file lives,
what it contains, which models it accepts, how merging works and what to watch
out for.

- [Common concepts](#common-concepts)
- [`pi`](#pi)
- [`claude-code`](#claude-code)
- [`codex`](#codex)
- [`zcode`](#zcode)
- [Protocol support matrix](#protocol-support-matrix)
- [Base URL normalisation](#base-url-normalisation)

## Common concepts

Every target is a subclass of `opencode2others.targets.base.Target` and receives:

| Value | Description |
| ----- | ----------- |
| `models` | the full catalog (`list[Model]`) |
| `ctx` | a `Context` with provider id/name, base URL, key info and `merge` |
| `path` | the resolved output path |

A target declares the protocols it understands via the `protocols` class
attribute and calls `self.filter(models)` to drop the rest. The CLI then writes
whatever `render()` returns using `util.write_text`, which creates a `.bak`
backup before overwriting.

If a target ends up with zero usable models, the CLI prints a warning, skips the
file and returns a non-zero exit code for that target.

### Default model (`--model`)

The global `--model ID` / `--default-model ID` option sets the preferred startup
model. Each target applies it only when the model speaks a protocol the target
supports:

| Target | Behaviour |
| ------ | --------- |
| `pi` | also writes `defaultProvider` + `defaultModel` to `settings.json` |
| `claude-code` | used only if the model is `anthropic-messages`; otherwise warns and falls back |
| `codex` | used if the model is OpenAI-protocol; otherwise warns and falls back |
| `zcode` | promoted to the front of its provider group |

This is what makes a single command safe across agents with different protocol
support: an incompatible model is never written to a target that cannot use it.

---

## `pi`

**Pi coding agent** — [docs](https://github.com/earendil-works/pi-coding-agent)

| | |
| --- | --- |
| Default path | `~/.pi/agent/models.json` |
| Override | `--pi-output PATH`, or `$PI_CODING_AGENT_DIR` |
| Protocols | all three |
| Merge | deep merge, keyed by provider id |

### Format

```json
{
  "providers": {
    "<provider-id>": {
      "name": "OpenCode Go",
      "baseUrl": "https://opencode.ai/zen/go/v1",
      "apiKey": "sk-...",
      "api": "openai-completions",
      "models": [ /* one entry per model */ ]
    }
  }
}
```

Each model entry contains `id`, `name`, plus `reasoning`, `input`
(`["text", "image"]` when the model is multimodal), `contextWindow`,
`maxTokens`, `cost`, and — only when it differs from the provider-level `api` —
an `api` field.

The provider-level `api` is the **most common** protocol among the selected
models. This keeps the file compact while still being exact per model.

### Key storage

`apiKey` is the literal key when one was supplied, otherwise
`"$OPENCODE_API_KEY"`. `--write-auth` additionally merges
`{ "<provider-id>": { "type": "api_key", "key": "..." } }` into
`~/.pi/agent/auth.json` (mode `0600` on POSIX).

### Notes

- Because Pi supports every protocol, no model is ever filtered out.

---

## `claude-code`

**Claude Code** — [docs](https://docs.anthropic.com/en/docs/claude-code)

| | |
| --- | --- |
| Default path | `~/.claude/settings.json` |
| Override | `--claude-output PATH`, or `$CLAUDE_CONFIG_DIR` |
| Protocols | `anthropic-messages` only |
| Merge | deep merge of the `env` object |

### Format

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://opencode.ai/zen/go",
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "ANTHROPIC_MODEL": "qwen3.8-max",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "qwen3.8-max",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "qwen3.8-max",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "qwen3.8-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "qwen3.8-max",
    "API_TIMEOUT_MS": "3000000"
  },
  "theme": "light",
  "mcpServers": { "...": {} }
}
```

### Model selection

| Setting | Option | Default |
| ------- | ------ | ------- |
| `ANTHROPIC_MODEL` | `--claude-model` | first Anthropic model |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `--claude-opus-model` | main model |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `--claude-sonnet-model` | main model |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `--claude-haiku-model` | first id containing `haiku`/`flash`/`air`/`mini`/`small`/`turbo`/`free`, else main |
| `CLAUDE_CODE_SUBAGENT_MODEL` | `--claude-subagent-model` | main model |
| `API_TIMEOUT_MS` | `--claude-timeout-ms` | unset |

Passing a model that is not served over the Anthropic protocol raises a clear
error listing the available ids.

### Notes

- Claude Code appends `/v1/messages` to `ANTHROPIC_BASE_URL`, so the tool strips
  a trailing `/v1` from the OpenCode base URL (`.../zen/go/v1` → `.../zen/go`).
- **Anthropic protocol only.** Claude Code cannot use models served over
  `/chat/completions` or `/responses` (for example `deepseek-v4.1-flash`). Such
  models are filtered out, and if `--model` names one the target warns and keeps
  an Anthropic-compatible model.
- When no key is available, `ANTHROPIC_AUTH_TOKEN` is written as
  `${OPENCODE_API_KEY}`.
- `theme`, `mcpServers` and any other top-level keys are preserved.

---

## `codex`

**OpenAI Codex CLI** — [docs](https://github.com/openai/codex)

| | |
| --- | --- |
| Default path | `~/.codex/config.toml` |
| Override | `--codex-output PATH`, or `$CODEX_HOME` |
| Protocols | `openai-completions` (`wire_api = "chat"`), `openai-responses` (`wire_api = "responses"`) |
| Merge | update the managed tables, keep everything else |

### Format

A Codex `model_provider` has exactly one `wire_api`, but OpenCode serves chat
and responses models simultaneously. The tool therefore emits **one provider per
protocol** and **one profile per model**:

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

Select a profile on the command line:

```bash
codex --profile opencode-go-glm-5.3
```

### Model selection

`--codex-model` sets the top-level `model` (and must be an OpenAI-protocol
model). The default is the first OpenAI-protocol model in catalog order.

### Key storage

Codex reads the key from the environment variable named by `env_key`. The tool
does **not** write secrets to `config.toml`. Use `--codex-api-key-env` to change
the variable name (defaults to `--api-key-env`).

### Notes

- Anthropic models are filtered out entirely.
- Profile names containing dots (e.g. `glm-5.3`) are emitted as quoted TOML keys.
- Merging rewrites the whole file, so comments and fine-grained formatting of
  the existing config are not preserved (a `.bak` is always created first).

---

## `zcode`

**ZCode**

| | |
| --- | --- |
| Default path | `~/.zcode/v2/config.json` |
| Override | `--zcode-output PATH`, or `$ZCODE_HOME` |
| Protocols | `anthropic-messages` (`kind: "anthropic"`), `openai-completions` (`kind: "openai"`) |
| Merge | deep merge of the `provider` map |

### Format

ZCode stores providers under a top-level `provider` object. The tool emits one
provider group per protocol:

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

### Notes

- `openai-responses` models are **skipped with a warning**; ZCode has no
  Responses wire kind.
- The Anthropic group uses the base URL without `/v1`; the OpenAI group keeps
  `/v1`.
- `priority` is assigned sequentially per provider group for stable ordering.
- When no key is available, `apiKey` is `""` and `apiKeyRequired: true` is set.
- Existing providers (including built-ins) are preserved.

---

## Protocol support matrix

| Target | `anthropic-messages` | `openai-completions` | `openai-responses` |
| ------ | :------------------: | :------------------: | :----------------: |
| `pi` | ✅ | ✅ | ✅ |
| `claude-code` | ✅ | ➖ filtered | ➖ filtered |
| `codex` | ➖ filtered | ✅ `wire_api = "chat"` | ✅ `wire_api = "responses"` |
| `zcode` | ✅ `kind: anthropic` | ✅ `kind: openai` | ⚠️ skipped + warning |

## Base URL normalisation

OpenCode Go's base URL is `https://opencode.ai/zen/go/v1`. Each target stores it
differently:

| Target | Field | Stored value |
| ------ | ----- | ------------ |
| Pi | `baseUrl` | `https://opencode.ai/zen/go/v1` |
| Claude Code | `ANTHROPIC_BASE_URL` | `https://opencode.ai/zen/go` |
| Codex | `model_providers.*.base_url` | `https://opencode.ai/zen/go/v1` |
| ZCode (anthropic) | `provider.*.options.baseURL` | `https://opencode.ai/zen/go` |
| ZCode (openai) | `provider.*.options.baseURL` | `https://opencode.ai/zen/go/v1` |

Rule of thumb: clients that append `/v1/...` themselves (Claude Code, ZCode
Anthropic) get the version segment stripped; clients that append only the
endpoint (`/chat/completions`, `/responses`) keep it.

# opencode2others

**一条命令，把一份 [OpenCode Go](https://opencode.ai/docs/go/) 订阅转换成 Pi、Claude Code、OpenAI Codex 与 ZCode 可直接使用的配置文件。**

`opencode2others` 会读取 OpenCode Go 的实时模型目录，自动识别每个模型所使用的
协议，然后写入（或合并进）你所用编码工具的配置文件。无需手工维护模型列表，
也不用在多个工具之间复制粘贴 API Key。

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#环境要求)
[![CI](https://github.com/jiubafangxing/opencode2others/actions/workflows/ci.yml/badge.svg)](https://github.com/jiubafangxing/opencode2others/actions/workflows/ci.yml)

> English documentation: [README.md](README.md)

---

## 目录

- [为什么需要它](#为什么需要它)
- [支持的目标](#支持的目标)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [鉴权／密钥](#鉴权密钥)
- [用法](#用法)
- [命令行参数](#命令行参数)
- [生成的文件](#生成的文件)
- [工作原理](#工作原理)
- [协议与 base URL 处理](#协议与-base-url-处理)
- [合并与备份](#合并与备份)
- [环境变量](#环境变量)
- [文档](#文档)
- [开发](#开发)
- [常见问题](#常见问题)
- [安全](#安全)
- [许可证](#许可证)

---

## 为什么需要它

OpenCode Go 提供的模型分散在 **三种不同的协议** 上（`/chat/completions`、
`/responses`、`/messages`），而每个编码工具只支持其中一部分：

- **Claude Code** 只会说 Anthropic Messages。
- **Codex** 只会说 OpenAI Chat 或 Responses，且一个 provider 只能有一个
  `wire_api`。
- **Pi** 三种协议全支持。
- **ZCode** 支持 Anthropic 与 OpenAI，但不支持 Responses。

手工维护四份配置既繁琐又容易出错。`opencode2others` 帮你完成：

1. 从 OpenCode Go 接口拉取实时模型列表；
2. 用 [models.dev](https://models.dev) 的元数据补全信息；
3. 从官方文档（或实时探测）解析每个模型的协议；
4. 为每个工具写入正确的文件，并自动过滤掉它不支持的协议。

## 支持的目标

| 目标          | 配置文件                            | 可用协议                                        | 说明 |
| ------------- | ----------------------------------- | ----------------------------------------------- | ---- |
| `pi`          | `~/.pi/agent/models.json`           | 全部                                            | 信息最完整 |
| `claude-code` | `~/.claude/settings.json`           | 仅 `anthropic-messages`                         | 写入 `ANTHROPIC_*` 环境变量 |
| `codex`       | `~/.codex/config.toml`              | `openai-completions`、`openai-responses`        | 每种 `wire_api` 一个 provider，每个模型一个 profile |
| `zcode`       | `~/.zcode/v2/config.json`           | `anthropic-messages`、`openai-completions`      | 每种 `kind` 一个 provider 分组 |

## 环境要求

- **Python 3.9+**。
- **零第三方依赖** —— 仅用标准库。Codex 所需的 TOML 读写已内置
  （`opencode2others.toml_io`），因此在没有 `tomllib` 的 Python 3.9/3.10 上也能用。
- 能访问 `opencode.ai`、`models.dev` 以及你配置的 base URL。

## 安装

### pip / pipx

```bash
pipx install opencode2others      # CLI 工具推荐
# 或
pip install opencode2others
```

### 免安装直接运行

```bash
git clone https://github.com/jiubafangxing/opencode2others.git
cd opencode2others
python -m opencode2others --help
```

### 从源码可编辑安装

```bash
pip install -e ".[dev]"
```

## 快速开始

```bash
# 一条命令生成全部配置，并把密钥写入 Pi：
opencode2others --api-key sk-... --write-auth

# 只生成 Pi：
opencode2others --target pi --write-auth

# 先预览，不写任何文件：
opencode2others --dry-run
```

也可以用环境变量传入密钥，避免出现在 shell 历史里：

```bash
export OPENCODE_API_KEY=sk-...
opencode2others
```

> 已存在的配置文件会被 **合并**，并在改写前备份为 `<file>.bak`。
> 如需直接覆盖，请加 `--no-merge`。详见 [合并与备份](#合并与备份)。

## 鉴权／密钥

密钥解析顺序：

1. `--api-key sk-...`（字面量，优先级最高）；
2. `$OPENCODE_API_KEY`（或 `--api-key-env` 指定的变量）；
3. **自动发现** —— 从已有的本地配置中读取：Pi `auth.json` / `models.json`、
   ZCode `config.json`、Claude Code `settings.json`（仅当其 base URL 匹配时）、
   Codex `auth.json`。可用 `--no-key-discovery` 关闭。

使用的密钥来源会以掩码形式打印，方便核对。

即使没有密钥工具也能运行：在支持引用的地方写入 `${OPENCODE_API_KEY}`，在不适用的
地方将 `apiKey` 留空。但在请求阶段需要密钥的功能（`--probe`、`--write-auth`）会提前报错。

密钥的落点：

| 目标          | 密钥位置 |
| ------------- | -------- |
| `pi`          | `models.json` 的 `apiKey`；`--write-auth` 还会写入 `~/.pi/agent/auth.json` |
| `claude-code` | `settings.json` 的 `ANTHROPIC_AUTH_TOKEN` |
| `codex`       | **不写入** —— Codex 从 `env_key` 指定的环境变量读取（默认 `OPENCODE_API_KEY`） |
| `zcode`       | `provider.<id>.options.apiKey` |

## 用法

### 为所有工具生成

```bash
opencode2others --api-key sk-...
```

### 为单个工具生成

```bash
opencode2others --target codex
opencode2others --target claude-code --claude-model qwen3.8-max
opencode2others --target zcode
```

`--target` 可重复：

```bash
opencode2others -t pi -t codex
```

### 只预览、不写盘

```bash
opencode2others --dry-run
opencode2others --target codex --dry-run
```

### 列出模型及其协议

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

### 用实时探测确定协议

抓取文档表格又快又免费；如果你想要“地面真相”，`--probe` 会为每个模型发送一个极小的
请求，记录哪个端点响应：

```bash
opencode2others --probe
```

`--probe` 会先逐个尝试端点，再对无法判定的模型回退到文档表格。消耗的额度可忽略不计。

### 自定义 provider 或 base URL

```bash
opencode2others \
  --base-url https://opencode.ai/zen/go/v1 \
  --provider-id opencode-go \
  --provider-name "OpenCode Go"
```

### 设置默认模型

`--model ID`（别名 `--default-model`）为**所有支持该协议的目标**设置首选启动模型：

| 目标 | `--model ID` 的作用 |
| ---- | ------------------- |
| `pi` | 向 `~/.pi/agent/settings.json` 写入 `defaultProvider` + `defaultModel` |
| `codex` | 设置顶层 `model` 及对应 profile |
| `zcode` | 将该模型排在其 provider 分组的第一位 |
| `claude-code` | **仅当**该模型是 `anthropic-messages` 协议时生效 |

```bash
opencode2others --model deepseek-v4.1-flash
```

> **Claude Code 仅支持 Anthropic Messages 协议。** 许多 OpenCode 模型
> （包括通过 `/chat/completions` 提供的 `deepseek-v4.1-flash`）根本无法被
> Claude Code 使用。当 `--model` 指定这类模型时，工具会告警并保留一个
> Anthropic 兼容的默认模型。查看哪些模型可用：
>
> ```bash
> opencode2others --list | grep anthropic-messages
> ```

显式指定 Claude Code 的各个槽位：

```bash
# 主模型 / opus / sonnet / subagent，以及小快模型 haiku 槽位
opencode2others --target claude-code \
  --claude-model qwen3.8-max \
  --claude-haiku-model qwen3.8-flash

# Codex：顶层 `model`（及对应 profile）
opencode2others --target codex --codex-model glm-5.3
```

## 命令行参数

| 参数 | 说明 | 默认值 |
| ---- | ---- | ------ |
| `--target, -t TARGET` | 要生成的目标，可重复；`all` 展开为全部。 | `all` |
| `--list` | 打印解析后的模型／协议表格后退出。 | 关闭 |
| `--probe` | 用实时 1-token 请求探测协议，需要密钥。 | 关闭 |
| `--merge` / `--no-merge` | 合并（默认）或覆盖已有文件。 | 合并 |
| `--api-key KEY` | 要写入的 API Key。 | `$--api-key-env` |
| `--api-key-env NAME` | 保存密钥的环境变量名。 | `OPENCODE_API_KEY` |
| `--no-key-discovery` | 不从已有本地配置中读取密钥。 | 关闭 |
| `--base-url URL` | OpenCode Go API base URL。 | `https://opencode.ai/zen/go/v1` |
| `--provider-id ID` | 生成配置中的 provider id。 | `opencode-go` |
| `--provider-name NAME` | provider 显示名称。 | `OpenCode Go` |
| `--model, --default-model ID` | 首选启动模型；按协议分别生效（见上）。 | 未设置 |
| `--timeout SECONDS` | HTTP 超时。 | `30` |
| `-o, --output PATH` | 输出路径覆盖（仅单个 target 时可用）。 | 目标默认路径 |
| `--dry-run` | 打印生成内容而不写盘。 | 关闭 |
| `-v, --verbose` | 输出更多诊断信息。 | 关闭 |
| `--version` | 显示版本并退出。 | |
| `--pi-output PATH` | 覆盖 `models.json` 路径。 | `~/.pi/agent/models.json` |
| `--auth-file, --pi-auth-file PATH` | 覆盖 `auth.json` 路径。 | `~/.pi/agent/auth.json` |
| `--write-auth` | 同时把密钥写入 Pi 的 `auth.json`。 | 关闭 |
| `--claude-output PATH` | 覆盖 `settings.json` 路径。 | `~/.claude/settings.json` |
| `--claude-model ID` | `ANTHROPIC_MODEL`。 | 第一个 Anthropic 模型 |
| `--claude-opus-model ID` | `ANTHROPIC_DEFAULT_OPUS_MODEL`。 | 主模型 |
| `--claude-sonnet-model ID` | `ANTHROPIC_DEFAULT_SONNET_MODEL`。 | 主模型 |
| `--claude-haiku-model ID` | `ANTHROPIC_DEFAULT_HAIKU_MODEL`。 | 第一个小／快模型，否则主模型 |
| `--claude-subagent-model ID` | `CLAUDE_CODE_SUBAGENT_MODEL`。 | 主模型 |
| `--claude-timeout-ms MS` | `API_TIMEOUT_MS`。 | 不设置 |
| `--codex-output PATH` | 覆盖 `config.toml` 路径。 | `~/.codex/config.toml` |
| `--codex-model ID` | 顶层 `model` 及默认 profile。 | 第一个 OpenAI 模型 |
| `--codex-api-key-env NAME` | Codex 读取密钥的 `env_key`。 | `--api-key-env` |
| `--zcode-output PATH` | 覆盖 `config.json` 路径。 | `~/.zcode/v2/config.json` |

## 生成的文件

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

出现次数最多的协议会成为 provider 级别的 `api`；不同的模型会各自带上 `api` 字段。

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

`settings.json` 中已有的无关键（`theme`、`mcpServers` 等）会被保留。

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

用 profile 切换模型：

```bash
codex --profile opencode-go-glm-5.3
```

记得 `export OPENCODE_API_KEY=sk-...`。

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

## 工作原理

```
                 ┌─────────────────────────────────────────────┐
                 │ 1. GET /zen/go/v1/models                    │
                 │    -> 实时模型 id                            │
                 ├─────────────────────────────────────────────┤
                 │ 2. GET models.dev/api.json                  │
                 │    provider "opencode-go"                   │
                 │    -> 名称、限制、价格、推理、视觉           │
                 ├─────────────────────────────────────────────┤
                 │ 3. 解析每个模型的协议                        │
                 │    a) --probe 实时探测，否则                 │
                 │    b) 抓取 /docs/go 端点表格                 │
                 └─────────────────────────────────────────────┘
                                    │
                        list[Model] │ (id, name, protocol, ...)
                                    ▼
        ┌───────────────┬───────────────┬───────────────┬───────────────┐
        │  Pi           │ Claude Code   │ Codex         │ ZCode         │
        │  全部协议      │ 仅 anthropic  │ chat/responses│ anthropic+chat│
        └───────────────┴───────────────┴───────────────┴───────────────┘
```

### 数据来源

| 来源 | 用途 | 是否必需 |
| ---- | ---- | -------- |
| `GET https://opencode.ai/zen/go/v1/models` | 实时模型清单 | 是 |
| `GET https://models.dev/api.json` | 元数据（名称、限制、价格、推理、视觉） | 可选（失败仅告警） |
| `GET https://opencode.ai/docs/go/` | 每个模型的协议表 | 是（除非用 `--probe`） |
| 实时 `POST` 探测 | 精确协议 | 仅 `--probe` 时 |

出现在 `/v1/models` 但不在协议来源中的模型会被跳过并报告 —— 本工具绝不猜测协议。

元数据是“尽力而为”：如果 models.dev 不可达，配置仍会生成，只是
`name = id` 且没有限制与价格。

## 协议与 base URL 处理

OpenCode 端点与协议的映射：

| OpenCode 端点 | Pi `api` | Codex `wire_api` | ZCode `kind` |
| ------------- | -------- | ---------------- | ------------ |
| `/v1/chat/completions` | `openai-completions` | `chat` | `openai` |
| `/v1/responses` | `openai-responses` | `responses` | —（跳过） |
| `/v1/messages` | `anthropic-messages` | —（跳过） | `anthropic` |

各工具期望的 base URL 形态略有不同，工具会按目标做归一化：

| 目标 | 字段 | 取值 |
| ---- | ---- | ---- |
| Pi | `baseUrl` | `https://opencode.ai/zen/go/v1` |
| Claude Code | `ANTHROPIC_BASE_URL` | `https://opencode.ai/zen/go`（客户端会补 `/v1/messages`） |
| Codex | `model_providers.*.base_url` | `https://opencode.ai/zen/go/v1`（客户端补端点） |
| ZCode（`anthropic`） | `options.baseURL` | `https://opencode.ai/zen/go` |
| ZCode（`openai`） | `options.baseURL` | `https://opencode.ai/zen/go/v1` |

## 合并与备份

默认情况下，工具会 **合并** 进已有文件，从而保留你的其他 provider、主题、MCP 服务器
与 profile。每个文件在被改写前都会备份为 `<file>.bak`。

各目标的合并行为：

| 目标 | 合并语义 |
| ---- | -------- |
| Pi | 深合并，保留其他 provider，更新 `opencode-go` |
| Claude Code | 深合并 `env`，保留 `theme`、`mcpServers` 等 |
| Codex | 保留已有表，更新 `model`、`model_provider` 以及受管 providers/profiles |
| ZCode | 深合并 `provider` 映射 |

`--no-merge` 会整体替换（仍会生成 `.bak`）。

## 环境变量

| 变量 | 作用 |
| ---- | ---- |
| `OPENCODE_API_KEY` | 默认密钥（可用 `--api-key-env` 改名）。 |
| `PI_CODING_AGENT_DIR` | Pi agent 目录；默认 `~/.pi/agent`。 |
| `CLAUDE_CONFIG_DIR` | Claude 配置目录；默认 `~/.claude`。 |
| `CODEX_HOME` | Codex 主目录；默认 `~/.codex`。 |
| `ZCODE_HOME` | ZCode 主目录；默认 `~/.zcode`。 |

## 文档

| 文档 | 内容 |
| ---- | ---- |
| [`README.md`](README.md) | 英文版说明（概览、安装、用法、CLI 参考）。 |
| [`README.zh-CN.md`](README.zh-CN.md) | 本文件（中文翻译）。 |
| [`docs/manual.zh-CN.md`](docs/manual.zh-CN.md) | 操作手册（日常操作、分工具验证、备份回滚、故障排查）。 |
| [`docs/targets.md`](docs/targets.md) | 各目标的格式、选项、合并语义与协议矩阵。 |
| [`docs/architecture.md`](docs/architecture.md) | 内部设计以及如何新增一个目标。 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 开发环境与贡献指南。 |
| [`SECURITY.md`](SECURITY.md) | 密钥处理方式与漏洞上报。 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本历史。 |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | 社区行为准则。 |

## 开发

```bash
python -m unittest discover -v   # 测试套件（无需联网）
ruff check .                     # 代码检查（可选）
```

项目结构、Target 契约以及如何新增一个工具的支持，见
[`CONTRIBUTING.md`](CONTRIBUTING.md)。更深入的架构说明见
[`docs/architecture.md`](docs/architecture.md)，各目标细节见
[`docs/targets.md`](docs/targets.md)。

## 常见问题

**`[warn] N model(s) not in the endpoint table; skipped: ...`**
这些模型被 API 列出但未出现在协议文档页上。工具会有意跳过而不猜测。可用
`--probe` 通过实时请求为它们判定协议。

**Codex 不认密钥。**
Codex 从 `env_key` 指定的环境变量读取密钥。请
`export OPENCODE_API_KEY=sk-...`，或传 `--codex-api-key-env MY_VAR` 并导出该变量。

**Claude Code 提示 token 无效。**
确认 `ANTHROPIC_BASE_URL` 末尾没有 `/v1`；Claude Code 会自己补上 `/v1/messages`。
并用 `--claude-model` 选择一个通过 Anthropic 协议提供的模型
（`opencode2others --list` 会显示协议）。

**ZCode 少了一些模型。**
ZCode 没有 Responses wire kind，因此 `openai-responses` 模型会被跳过并告警。
其余模型会写入 `anthropic` 和／或 `openai` provider 分组。

**我想撤销一次运行。**
还原对应的 `<file>.bak`。把 dotfiles 纳入 Git 版本管理也很有帮助。

**密钥会被发送到哪里？**
只会发往 `opencode.ai`（且仅当你使用 `--probe` 时）。元数据与文档表均以匿名方式从
`models.dev` 和 `opencode.ai` 获取。

## 安全

- 优先使用 `OPENCODE_API_KEY` 环境变量而非 `--api-key`，以免密钥进入 shell 历史。
- 工具会写入 `.bak` 备份，其中同样含有密钥，请勿纳入版本管理（内置 `.gitignore`
  已排除 `auth.json` 与 `models.json`）。
- 在 POSIX 系统上，Pi 的 `auth.json` 会以 `0600` 权限写入。
- 切勿在 issue 或 PR 中粘贴真实密钥。

## 许可证

[MIT](LICENSE) © opencode2others contributors。

OpenCode、Pi、Claude Code、OpenAI Codex 与 ZCode 均为各自所有者的项目。
本工具为非官方项目，与上述任何项目无隶属关系。

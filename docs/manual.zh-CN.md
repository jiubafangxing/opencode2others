# opencode2others 操作手册

> 本手册面向**使用者**，按“照做即可”的方式描述每一步操作、验证方法与回滚方式。
> 如果你想了解设计原理，请阅读 [`architecture.md`](architecture.md)；
> 各目标的字段细节见 [`targets.md`](targets.md)；命令行参数总表见
> [`../README.zh-CN.md`](../README.zh-CN.md#命令行参数)。

---

## 1. 手册约定

| 记号 | 含义 |
| ---- | ---- |
| `$` | 普通用户 shell 提示符（Windows PowerShell 亦适用，路径用 `\` 或 `/` 均可） |
| `<占位>` | 需要替换成你自己的值，例如 `<你的密钥>` |
| 说明 | 只提示、不改行为的补充文字 |
| 警告 | 可能导致密钥泄露、配置被覆盖或功能不可用的操作 |

**退出码**

| 退出码 | 含义 |
| ------ | ---- |
| `0` | 全部成功 |
| `1` | 至少一个目标失败、无兼容模型，或网络/参数错误 |

> 日常可把退出码接入脚本：`opencode2others --dry-run || echo "生成失败"`。

---

## 2. 前置条件

- Python **3.9+**（在目标机器上执行 `python --version` 确认）。
- 能访问：`opencode.ai`、`models.dev`。
- 一个 OpenCode Go 的 API Key（形如 `sk-...`）。
- 建议用 Git 管理你的 dotfiles，便于回滚。

---

## 3. 安装与自检

### 3.1 安装（任选其一）

```bash
# 推荐：隔离安装 CLI
pipx install opencode2others

# 或
pip install opencode2others
```

免安装试用：

```bash
git clone https://github.com/jiubafangxing/opencode2others.git
cd opencode2others
python -m opencode2others --help
```

### 3.2 自检

```bash
# 1) 版本与帮助可正常输出
opencode2others --version
opencode2others --help

# 2) 网络与目录解析正常：列出模型表（不需要密钥）
opencode2others --list
```

**判定标准**：`--list` 能打印出 `MODEL ID / PROTOCOL / CTX / OUT / NAME` 表格即通过。
如果这一步失败，先解决网络问题再做后续操作。

---

## 4. SOP-01：首次配置（标准作业流程）

> 目标：一条命令为所有工具生成配置，且不破坏已有文件。

**步骤 1 —— 先预览（不写盘）**

```bash
opencode2others --api-key <你的密钥> --dry-run
```

检查输出里每个 `# ===== <target> -> <路径> =====` 段落是否符合预期。

**步骤 2 —— 正式写入**

```bash
# 写入全部目标；同时把密钥写入 Pi 的 auth.json
opencode2others --api-key <你的密钥> --write-auth
```

**步骤 3 —— 逐目标验证**

按第 6 章对应小节执行验证命令，确认文件内容正确。
若使用环境变量承载密钥（更安全），改用：

```bash
export OPENCODE_API_KEY=<你的密钥>
opencode2others --write-auth
```

**步骤 4 —— 记录备份位置**

所有被改写的文件都会在同目录生成 `<文件名>.bak`，例如
`~/.claude/settings.json.bak`。确认这些备份存在后再继续开发工作。

---

## 5. 日常操作

### 5.1 生成全部配置

```bash
opencode2others                 # 密钥来自 $OPENCODE_API_KEY 或本地已存配置
opencode2others --api-key sk-... # 显式指定
```

### 5.2 只生成指定目标

`--target/-t` 可重复；`all` 表示全部（默认）。

```bash
opencode2others -t pi                 # 只生成 Pi
opencode2others -t pi -t codex        # 同时生成 Pi 与 Codex
opencode2others -t codex --dry-run    # 只预览 Codex
```

### 5.3 只预览、不落盘

```bash
opencode2others --dry-run
opencode2others -t claude-code --dry-run
```

输出以 `# ===== <target> -> <路径> =====` 开头，直接打印将要写入的完整内容。

### 5.4 查看模型及其协议

```bash
opencode2others --list
```

```
MODEL ID                       PROTOCOL (Pi api)          CTX       OUT  NAME
------------------------------------------------------------------------------------------
minimax-m3                     anthropic-messages     1000000    131072  MiniMax-M3
kimi-k3                        openai-completions     1048576    131072  Kimi K3
...
```

**排查技巧**：想确认某个目标能用哪些模型，直接按协议过滤：

```bash
# Claude Code 只能用 Anthropic 协议
opencode2others --list | grep anthropic-messages

# Codex 只能用 chat / responses
opencode2others --list | grep -E "openai-(completions|responses)"
```

> `--list` 不要求密钥；表格下方的 `[warn] ...skipped` 表示列出的模型未出现在协议文档
> 中，工具**有意跳过而不猜测**。可用 `--probe` 判定。

### 5.5 设置默认启动模型

`--model`（别名 `--default-model`）会**按协议**作用于各目标：

```bash
opencode2others --model deepseek-v4.1-flash
```

| 目标 | 效果 |
| ---- | ---- |
| `pi` | 写入 `settings.json` 的 `defaultProvider` + `defaultModel` |
| `codex` | 设置顶层 `model` 与默认 profile |
| `zcode` | 将该模型排在其 provider 分组首位 |
| `claude-code` | **仅当**该模型是 `anthropic-messages` 时生效，否则告警并保留兼容默认值 |

> Claude Code 不支持 Responses/Chat 协议模型。指定不兼容模型时它会告警并回退，
> 不会把不可用模型写进去。

### 5.6 用实时探测确定协议

文档抓取失败或想拿“地面真相”时：

```bash
opencode2others --probe --list   # 先看看判定结果
opencode2others --probe          # 再生成
```

`--probe` 会为每个模型发一个极小的请求，**需要密钥**，消耗额度可忽略。
若某模型探测不出，会回退到文档表格。

### 5.7 自定义 provider 或 base URL

```bash
opencode2others \
  --base-url https://opencode.ai/zen/go/v1 \
  --provider-id opencode-go \
  --provider-name "OpenCode Go"
```

---

## 6. 分目标操作与验证

### 6.1 Pi

```bash
opencode2others -t pi --write-auth
```

| 项目 | 位置 |
| ---- | ---- |
| 模型配置 | `~/.pi/agent/models.json`（可用 `--pi-output` 覆盖，或 `$PI_CODING_AGENT_DIR`） |
| 密钥文件 | `~/.pi/agent/auth.json`（`--write-auth` 时写入，POSIX 权限 `0600`） |

**验证**

```bash
# 应看到 providers.<provider-id> 与 models 数组
python -c "import json,os;d=json.load(open(os.path.expanduser('~/.pi/agent/models.json')));print(list(d['providers']))"
```

### 6.2 Claude Code

```bash
opencode2others -t claude-code
```

显式指定各槽位：

```bash
opencode2others -t claude-code \
  --claude-model qwen3.8-max \
  --claude-haiku-model qwen3.8-flash
```

| 环境变量 | 选项 | 默认 |
| -------- | ---- | ---- |
| `ANTHROPIC_MODEL` | `--claude-model` | 第一个 Anthropic 模型 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `--claude-opus-model` | 主模型 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `--claude-sonnet-model` | 主模型 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `--claude-haiku-model` | 第一个“小快”模型，否则主模型 |
| `CLAUDE_CODE_SUBAGENT_MODEL` | `--claude-subagent-model` | 主模型 |
| `API_TIMEOUT_MS` | `--claude-timeout-ms` | 不设置 |

**验证要点**

- `ANTHROPIC_BASE_URL` **末尾不能带 `/v1`**（工具已自动去掉；Claude Code 自己补 `/v1/messages`）。
- `ANTHROPIC_AUTH_TOKEN` 应为你的密钥；无密钥时写入 `${OPENCODE_API_KEY}`。
- 原有 `theme`、`mcpServers` 等无关键应被保留。

### 6.3 Codex

```bash
opencode2others -t codex --codex-model glm-5.3
```

Codex 的每个 provider 只能有一个 `wire_api`，因此工具按协议拆分为两个 provider，
并为每个模型生成一个 profile：

```bash
# 使用某个 profile 启动
codex --profile opencode-go-glm-5.3
```

**验证要点**

- Codex **不写密钥到文件**，它从 `env_key` 命名的环境变量读取。请确保：

  ```bash
  export OPENCODE_API_KEY=sk-...
  # 或自定义变量名，并同步生成配置
  opencode2others -t codex --codex-api-key-env MY_OPENCODE_KEY
  export MY_OPENCODE_KEY=sk-...
  ```

### 6.4 ZCode

```bash
opencode2others -t zcode
```

生成 `anthropic` 与 `openai` 两个 provider 分组（`kind` 分别为 `anthropic` / `openai`）。

**验证要点**

- `openai-responses` 模型会被**跳过并告警**（ZCode 无 Responses wire kind）。
- Anthropic 分组 base URL 不带 `/v1`，OpenAI 分组带 `/v1`。

---

## 7. 密钥管理

### 7.1 解析顺序

1. `--api-key sk-...`（优先级最高）；
2. 环境变量 `$OPENCODE_API_KEY`（可用 `--api-key-env` 改名）；
3. **自动发现**：按 Pi → ZCode → Claude Code → Codex 顺序从已有本地配置中读取，
   可用 `--no-key-discovery` 关闭。

运行时会以掩码形式打印来源，例如 `[info] using API key sk-abcd1234...wxyz (from $OPENCODE_API_KEY)`。

### 7.2 密钥落点

| 目标 | 位置 |
| ---- | ---- |
| `pi` | `models.json` 的 `apiKey`；`--write-auth` 另写 `auth.json` |
| `claude-code` | `settings.json` 的 `ANTHROPIC_AUTH_TOKEN` |
| `codex` | **不写入**，由 `env_key` 环境变量提供 |
| `zcode` | `provider.<id>.options.apiKey` |

### 7.3 安全建议

- **优先用环境变量**而非 `--api-key`，避免密钥进入 shell 历史。
- `.bak` 备份同样含密钥，**不要提交到 Git**（仓库自带 `.gitignore` 已排除
  `auth.json`、`models.json`）。
- 切勿在 issue / PR 中粘贴真实密钥。

---

## 8. 备份、回滚与升级

### 8.1 备份机制

- 默认**合并**进已有文件，保留你的其他 provider、主题、MCP 与 profile。
- 每次改写前，若目标文件已存在，会先复制为 `<file>.bak`。

| 目标 | 合并语义 |
| ---- | -------- |
| Pi | 深合并，保留其他 provider，更新受管 provider |
| Claude Code | 深合并 `env`，保留 `theme`、`mcpServers` 等 |
| Codex | 保留已有表，更新 `model`/`model_provider` 及受管 providers/profiles（注释与格式不保留） |
| ZCode | 深合并 `provider` 映射 |

### 8.2 覆盖模式

```bash
opencode2others --no-merge   # 整体替换（仍会生成 .bak）
```

### 8.3 回滚一次运行

```bash
# 例：撤销 Claude Code 的改动
cp ~/.claude/settings.json.bak ~/.claude/settings.json
```

各目标对应的备份文件：

```
~/.pi/agent/models.json.bak
~/.claude/settings.json.bak
~/.codex/config.toml.bak
~/.zcode/v2/config.json.bak
```

> 建议把 dotfiles 纳入 Git，回滚更可靠。

### 8.4 升级

```bash
pipx upgrade opencode2others      # 或 pip install -U opencode2others
opencode2others --version
```

---

## 9. 故障排查

| 现象 | 原因 | 处理 |
| ---- | ---- | ---- |
| `[warn] N model(s) not in the endpoint table; skipped: ...` | 模型被 API 列出但不在协议文档中，工具拒绝猜测 | 用 `--probe` 实时判定后重跑 |
| Codex 不认密钥 | Codex 从 `env_key` 环境变量读取 | `export OPENCODE_API_KEY=sk-...`，或用 `--codex-api-key-env MY_VAR` 并导出 |
| Claude Code 提示 token 无效 | base URL 带了 `/v1`，或选了非 Anthropic 模型 | 确认 `ANTHROPIC_BASE_URL` 末尾无 `/v1`；用 `--list \| grep anthropic-messages` 选模型 |
| ZCode 少了一些模型 | ZCode 无 Responses wire kind | 属预期；`openai-responses` 模型会跳过并告警 |
| `[warn] <target>: no compatible models; skipping` | 该目标没有可用协议模型 | 检查 `--list`；Exit code 为 1 |
| `[warn] no API key found` | 未提供密钥 | 设置 `$OPENCODE_API_KEY` 或 `--api-key` |
| `--write-auth needs a key` | 无密钥却要求写 auth.json | 先提供密钥 |
| `[info] N model(s) without models.dev metadata` | models.dev 不可达 | 可忽略；配置仍生成，只是 `name = id` 且无限制/价格 |
| `--output can only be used with a single --target` | 多目标时用了 `-o` | 改用各目标专属 `--<name>-output`，或只保留一个 `-t` |

**通用排查顺序**

1. `opencode2others --list` —— 网络、模型与协议是否正常；
2. `opencode2others --dry-run` —— 将要写入的内容是否符合预期；
3. `-v / --verbose` —— 打印更多诊断信息；
4. 检查 `.bak` 与 `models.dev` 可达性。

---

## 10. 常用命令速查

```bash
# 帮助 / 版本
opencode2others --help
opencode2others --version

# 查看模型与协议
opencode2others --list
opencode2others --list | grep anthropic-messages

# 预览
opencode2others --dry-run
opencode2others -t codex --dry-run

# 生成
opencode2others --api-key sk-... --write-auth     # 全部 + Pi auth
opencode2others -t pi                             # 只生成 Pi
opencode2others -t pi -t codex                    # 多个目标

# 默认模型 / 探测 / 覆盖
opencode2others --model deepseek-v4.1-flash
opencode2others --probe
opencode2others --no-merge
```

---

## 11. 附录

### 11.1 默认路径与覆盖

| 目标 | 默认路径 | 覆盖选项 | 环境变量 |
| ---- | -------- | -------- | -------- |
| Pi | `~/.pi/agent/models.json` | `--pi-output` | `PI_CODING_AGENT_DIR` |
| Pi auth | `~/.pi/agent/auth.json` | `--auth-file` / `--pi-auth-file` | `PI_CODING_AGENT_DIR` |
| Claude Code | `~/.claude/settings.json` | `--claude-output` | `CLAUDE_CONFIG_DIR` |
| Codex | `~/.codex/config.toml` | `--codex-output` | `CODEX_HOME` |
| ZCode | `~/.zcode/v2/config.json` | `--zcode-output` | `ZCODE_HOME` |

### 11.2 协议支持矩阵

| 目标 | `anthropic-messages` | `openai-completions` | `openai-responses` |
| ---- | :------------------: | :------------------: | :----------------: |
| `pi` | ✅ | ✅ | ✅ |
| `claude-code` | ✅ | ➖ 过滤 | ➖ 过滤 |
| `codex` | ➖ 过滤 | ✅ `wire_api=chat` | ✅ `wire_api=responses` |
| `zcode` | ✅ `kind=anthropic` | ✅ `kind=openai` | ⚠️ 跳过并告警 |

### 11.3 base URL 归一化

原始 base URL 为 `https://opencode.ai/zen/go/v1`：

| 目标 | 字段 | 存储值 |
| ---- | ---- | ------ |
| Pi | `baseUrl` | `https://opencode.ai/zen/go/v1` |
| Claude Code | `ANTHROPIC_BASE_URL` | `https://opencode.ai/zen/go` |
| Codex | `model_providers.*.base_url` | `https://opencode.ai/zen/go/v1` |
| ZCode（anthropic） | `options.baseURL` | `https://opencode.ai/zen/go` |
| ZCode（openai） | `options.baseURL` | `https://opencode.ai/zen/go/v1` |

### 11.4 数据来源

| 来源 | 用途 | 是否必需 |
| ---- | ---- | -------- |
| `GET https://opencode.ai/zen/go/v1/models` | 实时模型清单 | 是 |
| `GET https://models.dev/api.json` | 元数据（名称、限制、价格、推理、视觉） | 可选 |
| `GET https://opencode.ai/docs/go/` | 每个模型的协议表 | 是（除非 `--probe`） |
| 实时 `POST` 探测 | 精确协议 | 仅 `--probe` |

密钥只会发往 `opencode.ai`，且仅当使用 `--probe` 时。

---

相关文档：[`../README.zh-CN.md`](../README.zh-CN.md) ·
[`targets.md`](targets.md) · [`architecture.md`](architecture.md) ·
[`../SECURITY.md`](../SECURITY.md)

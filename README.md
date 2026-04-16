# codex2gpt

[English](./README_EN.md)

`codex2gpt` 是一个本地 Python 代理服务，用一套服务同时提供 OpenAI、Anthropic、Gemini 兼容接口，以及原生 `Responses API` 风格接口。

它适合放在本机或内网环境里，统一接入 Codex 账号池、代理路由、请求记录和基础运维面板。

## 仓库介绍

这个仓库主要做五件事：

- 把不同协议的请求统一转发到 Codex 后端
- 管理多个本地 OAuth 账号，并按策略分配请求
- 切换 Codex App 使用的登录账号，无需反复重新登录
- 提供一个轻量控制台，查看账号、代理和用量状态
- 作为本地统一入口，减少不同客户端分别适配的成本

当前已经支持的调用方式：

- OpenAI 兼容：`POST /v1/chat/completions`
- Anthropic 兼容：`POST /v1/messages`
- Gemini 兼容：`POST /v1beta/models/{model}:generateContent`
- 原生接口：`POST /v1/responses`

## 界面预览

账号信息页面：

![账号信息截图](./docs/images/account.png)

这个页面用于查看账号总览、当前 Codex App 账号、套餐窗口、请求量和代理分配情况。

登录新账号页面：

![登录新账号截图](./docs/images/login.png)

这个页面用于发起浏览器 OAuth 登录，也支持在自动回调失败时手动粘贴回调 URL 完成登录。

## 适合什么场景

- 想把本地多个 Codex 账号集中成一个统一 API 入口
- 已有 OpenAI / Anthropic / Gemini 客户端，想尽量少改代码接入
- 需要本地控制台查看账号状态、配额窗口、代理和近期请求
- 需要在多个已登录账号之间切换 Codex App 使用账号，不想每次都重新登录
- 希望给 agent、脚本或内部工具提供稳定的本地中转层

## 安装方式

推荐直接在 Codex 里说：

```text
直接下载并启动这个仓库：https://github.com/shengshenglab/codex2gpt.git
```

如果你手动操作，也可以：

```bash
git clone https://github.com/shengshenglab/codex2gpt.git
cd codex2gpt
./run.sh start
```

## 启动前说明

- 需要 Python 3.11+
- `./run.sh start` 首次启动时，默认会尝试导入 `~/.codex/auth.json`
- 如果本机还没有这个文件，启动会失败，并提示你先登录 Codex 再执行 `./run.sh add-auth oauth-01`

最顺手的方式是：

1. 先在本机登录 Codex
2. 确认存在 `~/.codex/auth.json`
3. 再运行 `./run.sh start`

## 使用方法

### 1. 启动服务

```bash
./run.sh start
```

常用命令：

```bash
./run.sh status
./run.sh stop
./run.sh restart
./run.sh add-auth oauth-02
```

### 2. 打开控制台

- Dashboard: [http://127.0.0.1:18100/](http://127.0.0.1:18100/)
- Health: [http://127.0.0.1:18100/health](http://127.0.0.1:18100/health)

### 3. 管理账号

- 如果本机已有 `~/.codex/auth.json`，`run.sh` 会在首次启动时自动导入到 `runtime/accounts/oauth-01.json`
- 如果你已经登录新的 Codex 账号，可以继续执行 `./run.sh add-auth oauth-02`
- 服务运行后，也可以在 Dashboard 里走浏览器 OAuth 流程添加账号
- 管理平台支持切换 Codex App 使用账号。账号都登录进来后，后续只需要在平台里点击目标账号设为 `Codex App` 账号即可，不需要来回重新登录
- 这个切换本质上会把选中的账号写入 `~/.codex/auth.json`，供 Codex App 直接使用

### 4. 调用接口

查看模型列表：

```bash
curl http://127.0.0.1:18100/v1/models
```

调用原生 `Responses API`：

```bash
curl http://127.0.0.1:18100/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "input": "Reply with exactly OK.",
    "stream": false
  }'
```

调用 OpenAI Chat Completions：

```bash
curl http://127.0.0.1:18100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "messages": [
      { "role": "user", "content": "Say hello." }
    ],
    "stream": false
  }'
```

模型级上下文覆盖示例：

项目根目录默认会读取 [model-overrides.toml](model-overrides.toml)。其中可以额外暴露一个本地模型 `gpt-5.4-1m`，它会映射到上游 `gpt-5.4`，但使用独立的 1M 上下文窗口：

```toml
[model_overrides."gpt-5.4-1m"]
upstream_model = "gpt-5.4"
context_window = 1000000
auto_compact_token_limit = 900000
advertise = true
```

其他模型仍继续使用 `~/.codex/config.toml` 里的全局默认窗口配置。完整示例可参考 [docs/codex-config.example.toml](docs/codex-config.example.toml)。

说明：

- `gpt-5.4` 仍是普通上下文版本，继续使用全局默认窗口。
- `gpt-5.4-1m` 是项目里额外暴露的本地模型名，只在代理侧区分，转发到上游时仍会使用 `gpt-5.4`。
- 只有确实需要超长上下文时再选择 `gpt-5.4-1m`。1M 窗口会显著增加输入 token 消耗，也可能带来更高的成本、更慢的请求耗时，以及更频繁的上下文整理。

调用 Anthropic Messages：

Anthropic 兼容层当前映射：

- `claude-opus-4-6` -> 本地 `gpt-5.4-1m` -> 上游 `gpt-5.4`
- `claude-sonnet-4-6` -> 本地 `gpt-5.4` -> 上游 `gpt-5.4`
- `claude-haiku-4-5` -> 本地 `gpt-5.3-codex` -> 上游 `gpt-5.3-codex`
- 也可以直接传 `gpt-5.4`、`gpt-5.4-1m`、`gpt-5.3-codex`，方便在 Claude Code 里显式切换 GPT 模型类型

Anthropic 兼容层的 1M 特殊说明：

- `claude-opus-4-6` 现在会走 `gpt-5.4-1m` 的模型预算，因此它默认就是 1M 上下文版本。
- 如果你希望 Anthropic 接口走普通窗口，请使用 `claude-sonnet-4-6`。
- 选择 `claude-opus-4-6` 同样会带来更高的 token 消耗、潜在更高成本，以及更慢的请求耗时。

Anthropic 兼容层当前额外支持：

- `thinking` 的 `budget_tokens` 与 `type: "adaptive"` 请求
- `output_config.format` 和 `output_config.effort`
- `speed: "fast"`。当请求带 `anthropic-beta: fast-mode-*` 时，代理会优先退回非 1M 路由，并在未显式指定 effort/thinking 时自动使用 `low` effort；响应 `usage` 也会回传 `speed: "fast"`
- 用户消息里的 `image` 内容块
- 用户消息里的 `document` 内容块，会映射到 Responses `input_file`
- `POST /v1/messages/count_tokens`，会把 tools、image、structured output schema 一并计入估算
- Bearer 鉴权或 Claude-Code 风格客户端的兼容型 SSE 输出
- thinking 流式块会附带空 `signature_delta` 兼容事件

和 `free-code` / Claude Code 一起使用时，当前还额外打通了这几类交互：

- 可以直接把 `gpt-5.4`、`gpt-5.4-1m`、`gpt-5.3-codex` 作为 Anthropic `model` 传进来，方便在 `/model` 里显式切换 GPT 型号
- `/model` picker 会按当前模型族显示对应选项。当前会话如果已经是 GPT 模型，就显示 GPT 选项；如果还是 Claude 模型，就继续显示 Claude 选项
- `/effort` 现在可以直接弹出 effort 选择列表；`gpt-5.4` / `gpt-5.4-1m` 可用 `low`、`medium`、`high`、`extra-high`、`auto`
- Anthropic 侧传入的 `extra-high` 会在代理层归一化成上游可接受的 `xhigh`
- `/fast` 会走 `speed: "fast"` 的 Anthropic 兼容路径，要求 `anthropic-beta: fast-mode-*`；代理会优先避开 1M 路由，并把返回 `usage.speed` 设为 `fast`

Anthropic 兼容层当前会接收但忽略：

- `metadata`

Anthropic 兼容层当前会校验并按需使用 `anthropic-beta`：

- `output_config.format` 需要 `structured-outputs-*`
- `output_config.effort` 需要 `effort-*`
- `output_config.task_budget` 需要 `task-budgets-*`
- `context_management` 需要 `context-management-*`
- `speed: "fast"` 需要 `fast-mode-*`
- 流式 `connector_text` 事件兼容需要 `summarize-connector-text-*`
- `tool_reference` 和工具 schema 里的 `defer_loading` / `eager_input_streaming` 需要 `advanced-tool-use-*` 或 `tool-search-tool-*`

在对应 beta 存在时：

- `context_management` 和 `speed` 仍会被兼容层消费后忽略，不会原样透传到上游
- 流式文本块会改为 `connector_text` / `connector_text_delta` 事件形状，并在结束前附带空 `signature_delta`

Anthropic 兼容层当前对 `tool_reference` 的处理：

- 会在 `tool_result` 中保留工具名信息，并翻译成兼容性文本提示转发给上游
- 这不是 Anthropic 原生 server-side expansion 语义，但足够让 `free-code` 之类客户端继续沿消息历史维护“已发现工具”状态

旧会话兼容层当前还会做的降级处理：

- assistant 历史里的 `server_tool_use` 会保留工具名和输入摘要，并降级成文本继续转发
- `connector_text` 会按普通文本块处理
- `tool_result` 内容数组里的 `image` / `document` 会降级成占位文本，避免旧会话恢复时直接报错

Anthropic 兼容层当前仍会明确拒绝：

- 暂时无法安全映射的 `document.source.type = "content"` 之类形状
- 仍无法安全映射的更深 Anthropic server-side 工具语义

```bash
curl http://127.0.0.1:18100/v1/messages \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "claude-opus-4-6",
    "max_tokens": 256,
    "messages": [
      { "role": "user", "content": "Say hello." }
    ],
    "stream": false
  }'
```

调用 Gemini 兼容接口：

```bash
curl http://127.0.0.1:18100/v1beta/models/gpt-5.4:generateContent \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [{ "text": "Say hello." }]
      }
    ]
  }'
```

## 核心特性

- 多协议兼容，尽量复用现有客户端
- 多账号轮转，支持 `least_used`、`round_robin`、`sticky`
- 支持结构化输出和工具调用
- 自带 Dashboard，便于查看账号、代理、用量和近期请求
- 运行时状态本地落盘，便于排查和恢复

## 运行时目录

服务会把本地状态写到 `runtime/` 下，常见内容包括：

- `runtime/accounts/*.json`
- `runtime/state.sqlite3`
- `runtime/settings.json`
- `runtime/cookies.json`
- `runtime/fingerprint-cache.json`
- `runtime/transcripts/`

这些属于运行时数据，不建议当作源码直接修改或提交。

## 给 Agent 的文档

- 仓库介绍：[`AGENT_OVERVIEW.md`](./AGENT_OVERVIEW.md)
- API 使用方法：[`AGENT_INTEGRATION.md`](./AGENT_INTEGRATION.md)

## 仓库结构

```text
.
├── app.py
├── codex2gpt/
│   ├── events.py
│   ├── protocols/
│   ├── schema_utils.py
│   └── state_db.py
├── run.sh
├── runtime/
├── tests/
└── web/
```

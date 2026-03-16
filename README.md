# codex2gpt

一个独立的轻量 Python 版本，用来把 Codex 订阅直接转成本地 Responses API。默认模型是 `gpt-5.4`，也可以切到其他 Codex 支持的模型。

特点：

- 纯 Python 标准库
- 不依赖前端、数据库、Redis
- 多个 `oauth.json` 账号池
- 某个账号限流或失败时自动切到下一个账号
- 启动后直接提供本地 `/v1/responses` 接口
- 额外兼容 `/v1/chat/completions`
- 模型名直接透传给 Codex 上游

## 目录结构

```text
codex2gpt/
├── app.py
├── run.sh
├── README.md
└── runtime/
    ├── lite.env
    ├── server.pid
    ├── server.log
    └── accounts/
        ├── oauth-01.json
        ├── oauth-02.json
        └── ...
```

## 前提

- macOS / Linux
- 已安装 `python3.11+`
- 已登录 Codex，并且当前机器存在 `~/.codex/auth.json`

说明：

- `run.sh` 依赖 Python 3.11 自带的 `tomllib`，不支持 Python 3.10 及以下
- 推荐使用 Python 3.11 / 3.12

如果还没登录：

```bash
codex login
```

如果你是在 Linux 服务器上部署，推荐直接同步一份本机已经可用的 `~/.codex/auth.json` 到服务器，避免服务器网络环境导致 `codex login` 失败。

推荐做法：

```bash
scp ~/.codex/auth.json root@YOUR_SERVER:/root/.codex/auth.json
```

如果你希望在服务器本机完成登录，也可以使用下面两种方式：

```bash
codex login --device-auth
```

或者用 API Key：

```bash
printenv OPENAI_API_KEY | codex login --with-api-key
```

## 一键启动

```bash
cd codex2gpt
./run.sh start
```

首次启动会自动：

1. 创建 `runtime/`
2. 生成 `runtime/lite.env`
3. 把当前机器的 `~/.codex/auth.json` 导入为 `runtime/accounts/oauth-01.json`
4. 启动本地服务

## Linux 服务器部署

下面是一个最小可用的 Linux 部署流程，默认服务器上已经有可用的 Python 3.11+ 环境。

推荐方案是先把本机已经可用的 `auth.json` 同步到服务器，再启动服务：

```bash
ssh root@YOUR_SERVER
mkdir -p /root/working /root/.codex
cd /root/working

# 把项目代码放到 /root/working/codex2gpt
git clone <your-repo-url> codex2gpt
cd codex2gpt

# 确认 Python 版本
python3 --version

# 启动服务
./run.sh start
```

在本机执行同步认证文件：

```bash
scp ~/.codex/auth.json root@YOUR_SERVER:/root/.codex/auth.json
```

如果你不想同步认证文件，也可以在服务器本机登录后再启动：

```bash
codex login --device-auth
./run.sh start
```

如果你的服务器上同时存在多个 Python 版本，先切到 Python 3.11+ 对应环境，再执行 `./run.sh start`。

如果你希望对外提供服务，可以修改 `runtime/lite.env`：

```bash
LITE_HOST=0.0.0.0
LITE_PORT=18100
LITE_API_KEY=CHANGE_ME
```

然后重启：

```bash
./run.sh restart
```

## 调用示例

```bash
curl http://127.0.0.1:18100/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-5.4","input":"用中文打个招呼。","stream":false}'
```

如果你配置了 `LITE_API_KEY`，再加上：

```bash
curl http://127.0.0.1:18100/v1/responses \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_LOCAL_API_KEY' \
  -d '{"model":"gpt-5.4","input":"用中文打个招呼。","stream":false}'
```

健康检查：

```bash
curl http://127.0.0.1:18100/health
```

模型列表：

如果你没有配置 `LITE_API_KEY`，模型列表也可以直接调用：

```bash
curl http://127.0.0.1:18100/v1/models
```

如果你配置了 `LITE_API_KEY`：

```bash
curl http://127.0.0.1:18100/v1/models \
  -H 'Authorization: Bearer YOUR_LOCAL_API_KEY'
```

## 模型选择

默认配置里会声明这几个模型：

- `gpt-5.4`
- `gpt-5.3-codex`

它们会出现在 `/v1/models` 里；默认请求模型由 `LITE_MODEL` 控制，可选模型列表由 `LITE_MODELS` 控制。

你可以在 `runtime/lite.env` 里改成自己的列表，例如：

```bash
LITE_MODEL=gpt-5.3-codex
LITE_MODELS=gpt-5.4,gpt-5.3-codex,gpt-5.1-codex,gpt-5.1-codex-max,gpt-5.1-codex-mini
```

重启后生效：

```bash
./run.sh restart
```

这个代理不会限制你请求里的 `model` 字段，实际能不能用，取决于你当前 Codex 账号对上游开放了哪些模型。

## 常用命令

```bash
./run.sh start
./run.sh stop
./run.sh restart
./run.sh status
./run.sh add-auth oauth-02
```

## 多账号

如果你切换了另一个 Codex 账号并重新登录：

```bash
codex login
./run.sh add-auth oauth-02
./run.sh restart
```

如果你已经有别的账号文件，也可以直接放进去：

```bash
cp /path/to/auth.json ./runtime/accounts/oauth-03.json
./run.sh restart
```

代理会按轮询使用这些账号；如果某个号返回 429/403/5xx 或网络错误，会自动切下一个号，并把失败账号短暂冷却。

## API

启动成功后会输出：

- Base URL
- API Key 状态

默认地址：

- Base URL: `http://127.0.0.1:18100/v1`
- Default Model: `gpt-5.4`

`LITE_API_KEY` 是可选的，默认留空。留空时不校验 API Key；如果你想加一层本地鉴权，手动在 `runtime/lite.env` 里填一个值后重启即可。

## 默认请求配置

这个代理除了透传请求参数，也会在你没有显式传值时补一组默认配置：

```json
{
  "model": "gpt-5.4",
  "reasoning": {"effort": "high"},
  "text": {"verbosity": "low"}
}
```

对应的本地配置项是：

```bash
LITE_MODEL=gpt-5.4
LITE_MODELS=gpt-5.4,gpt-5.3-codex
LITE_REASONING_EFFORT=high
LITE_TEXT_VERBOSITY=low
LITE_MODEL_CONTEXT_WINDOW=258400
LITE_MODEL_AUTO_COMPACT_TOKEN_LIMIT=232560
```

这两个值可以按 Codex 默认目录下的客户端配置生成：

- `LITE_REASONING_EFFORT` 优先读取 `~/.codex/config.toml` 里的 `model_reasoning_effort`
- `LITE_TEXT_VERBOSITY` 读取 `~/.codex/models_cache.json` 里当前模型的 `default_verbosity`
- `LITE_MODEL_CONTEXT_WINDOW` 优先读取 `~/.codex/config.toml`，没有时回退到 Codex 当前默认窗口
- `LITE_MODEL_AUTO_COMPACT_TOKEN_LIMIT` 优先读取 `~/.codex/config.toml`，没有时默认用窗口的 90%

## 高级参数

这个轻量代理会把大多数 Responses API 参数原样透传给 Codex 上游。当前已验证结果如下：

- `gpt-5.4`：`reasoning.effort=medium/high`、`text.verbosity=high`
- `gpt-5.3-codex`：默认可用；未显式指定时，上游返回 `reasoning.effort=medium`、`text.verbosity=medium`
- `text.verbosity=xhigh`：上游明确拒绝，当前正式可用值是 `low / medium / high`

也就是说，请求参数能透传，但具体支持哪些取值，仍然取决于模型本身。

示例：

```bash
curl http://127.0.0.1:18100/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "input": "请用中文解释这段代码。",
    "stream": false,
    "reasoning": {"effort": "high"},
    "text": {"verbosity": "high"}
  }'
```

可选值建议：

- `reasoning.effort`：`low`、`medium`、`high`、`xhigh`
- `text.verbosity`：`low`、`medium`、`high`

需要区分两类配置：

- `reasoning.effort`、`text.verbosity` 这类是请求参数，代理可以直接透传。
- `context window`、最大输出上限这类主要是模型能力，不是这个代理自身的开关。
- 这个代理现在会按 `LITE_MODEL_CONTEXT_WINDOW` 和 `LITE_MODEL_AUTO_COMPACT_TOKEN_LIMIT` 做本地预检查，超过阈值会在本地直接拒绝，避免把明显超限的请求打到上游。

如果上游支持，同样可以继续传 `previous_response_id`、`truncation`、`prompt_cache_key` 等 Responses API 字段。

## 兼容性增强

为了兼容更多本地客户端，这个代理现在会在转发前自动清洗一批 Codex 上游不支持、但 OpenAI 兼容客户端经常会附带的字段。

当前会自动忽略这些顶层字段：

- `max_output_tokens`
- `max_tokens`
- `max_completion_tokens`
- `metadata`
- `service_tier`
- `response_format`
- `parallel_tool_calls`
- `stream_options`
- `user`
- `n`

这样像 `openclaw`、OpenAI SDK 兼容模式、以及部分第三方客户端在默认附带这些字段时，不会再因为上游报 `Unsupported parameter` 直接失败。

## Chat Completions 兼容入口

除了 `/v1/responses`，现在也支持：

- `POST /v1/chat/completions`

这个入口会把 Chat Completions 风格请求自动转换成 Responses 请求再发给上游。

当前支持的常见输入：

- `messages`
- `tools`
- `tool_choice`
- `stream`
- `temperature`
- `reasoning`
- `text`
- `prompt_cache_key`

说明：

- `stream=true` 时，会返回 SSE 格式，并输出一个兼容的 completion chunk，最后跟 `[DONE]`
- 目前更偏向“接口兼容”而不是“逐 token 仿真”，也就是流式返回是单块完成态输出，不是逐字增量

非流式示例：

```bash
curl http://127.0.0.1:18100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "messages": [
      {"role": "system", "content": "你是一个助手"},
      {"role": "user", "content": "只回复OK"}
    ],
    "stream": false
  }'
```

流式示例：

```bash
curl http://127.0.0.1:18100/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-5.4",
    "messages": [
      {"role": "user", "content": "只回复OK"}
    ],
    "stream": true
  }'
```

## 测试

当前仓库已经带了标准库回归测试，重点覆盖：

- 不兼容字段清洗
- Chat Completions 转换
- `prompt_cache_key` 保留
- 缓存命中信息映射（`prompt_tokens_details.cached_tokens`）

运行方式：

```bash
cd codex2gpt
python3 -m unittest discover -s tests -v
```

真实缓存命中 smoke test：

```bash
cd codex2gpt
python3 tests/cache_hit_smoke.py
```

说明：

- 这个 smoke test 会对 `/v1/responses` 用同一个 `prompt_cache_key` 连续请求两次
- 如果第二次请求返回的 `usage.input_tokens_details.cached_tokens > 0`，脚本会成功退出
- 如果没有观察到 cache hit，脚本会返回非零退出码

当前经验上，验证真实 cache hit 建议优先用 `/v1/responses`，因为它更接近上游原生返回结构

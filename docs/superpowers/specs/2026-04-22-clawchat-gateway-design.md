# ClawChat Gateway Design

## Goal

在 `packages/hermes/clawchat` 中实现一个 Python 版 `hermes-agent/gateway` ClawChat adapter，面向 ClawChat v2 主链路协议，支持：

- WebSocket 握手与重连
- 入站 `message.send`
- 出站静态 `message.reply`
- 出站流式 `message.created` / `message.add` / `message.done` / 最终 `message.reply`
- direct / group 路由与 `groupMode`
- reply context 透传
- text + media 收发

本次范围不包含 invite-code 激活、`/v1/users/*` / `friends` / profile 更新，以及 `clawchat_*` 工具注册。

## Context

协议基线来自 [openclaw-clawchat.md](/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/docs/openclaw-clawchat.md) 与同目录 TypeScript 参考实现。Hermes 侧目标是提供一个可被现有 `gateway.platforms.base` 加载的 Python adapter，行为尽量与 `packages/openclaw-clawchat` 保持一致，但不引入 Node 子进程依赖。

当前工作目录为空目录，因此本实现会直接在这里建立独立 Python 包与测试结构。

## Scope

### Included

- ClawChat v2 WebSocket 连接与握手
- 握手后入站 envelope 解析
- `message.send` 映射到 Hermes `MessageEvent`
- direct / group 路由与 mention 过滤
- reply preview / context 透传
- 文本 fragments 聚合
- 入站 media URL 下载到本地上下文
- 出站静态回复
- 出站流式回复与最终 consolidated reply
- 出站 media 上传后拼接 fragments
- 单元测试与 fake WebSocket 联调测试
- Docker hermes 实例联调

### Excluded

- 邀请码激活与 token 换取
- `clawchat_activate` / `clawchat_get_my_profile` 等工具
- profile / friends / avatar 相关 API
- refresh token 生命周期
- SDK 级别完全兼容实现

## Protocol Summary

### Routing

ClawChat v2 使用根级字段：

- `chat_id`: 会话标识
- `chat_type`: `direct` 或 `group`
- `sender`: `{ id, nick_name }`

在 direct 中，`chat_id` 通常等于 `sender.id`。在 group 中，`chat_id` 是群 id，`sender.id` 是发言者 id。

### Handshake

主链路沿用 ClawChat 参考实现中的三步握手：

1. 建立 WebSocket，并带上 `Authorization: Bearer <token>`
2. 服务端下发 `event = "connect.challenge"`，payload 中带 `nonce`
3. 客户端计算签名并发送 `method = "connect"`
4. 服务端返回匹配 `requestId` 的 `hello-ok`
5. 连接进入 ready 状态

签名算法与参考实现保持一致：

- `client.sign = HMAC-SHA256(client.id + "|" + nonce, token)`
- 输出为小写 hex

### Inbound Event

主入站事件为 `message.send`。adapter 只在连接 ready 后处理这类消息。解析后的关键信息：

- `chat_id`
- `chat_type`
- `sender`
- `payload.message.fragments`
- `payload.message.context.reply`
- `payload.message.context.mentions`

### Outbound Events

静态回复：

- 直接发送 `message.reply`

流式回复：

1. `message.created`
2. 一个或多个 `message.add`
3. `message.done`
4. 一个最终 consolidated `message.reply`

媒体存在时，无论配置是否为 stream，都强制退化为静态 `message.reply`。

## Architecture

实现分为六个模块。

### 1. `config.py`

负责从 Hermes platform config 读取主链路所需字段，并标准化默认值。

字段：

- `websocket_url`
- `base_url`
- `token`
- `user_id`
- `reply_mode`
- `group_mode`
- `forward_thinking`
- `forward_tool_calls`
- `stream.flush_interval_ms`
- `stream.min_chunk_chars`
- `stream.max_buffer_chars`
- `reconnect.initial_delay`
- `reconnect.max_delay`
- `reconnect.jitter_ratio`
- `reconnect.max_retries`
- `heartbeat.interval`
- `heartbeat.timeout`
- `ack.timeout`
- `ack.auto_resend_on_timeout`
- `media_local_roots`

本次只对主链路真正使用到的字段生效；未用字段仍接受并保留默认值，避免后续扩展时破坏兼容。

### 2. `protocol.py`

纯函数层，不做 IO。

职责：

- frame encode / decode
- frame id 生成
- `connect.challenge` nonce 提取
- `client.sign` 计算
- `connect` 请求构造
- `hello-ok` 校验
- `message.send` 入站 envelope 解析
- reply preview 映射
- 文本 / media fragments 转内部表示
- `message.created` / `message.add` / `message.done` / `message.reply` / typing 事件构造

这个模块要保证：即使连接层变化，协议映射规则也能通过纯单测稳定验证。

### 3. `inbound.py`

负责把 ClawChat 入站 envelope 变成 Hermes 可消费的输入对象。

职责：

- 依据 `chat_type` 和 `group_mode` 决定是否触发
- `groupMode = "mention"` 时检查 `context.mentions` 是否包含当前 `user_id`
- 聚合 text fragments 为主文本
- 为 image / file / audio / video 生成 markdown 占位
- 生成 reply context 元数据
- 调用 media runtime 下载媒体并注入本地路径上下文

输出应包含：

- 最终给 LLM 的 `text`
- `chat_id`
- `sender_id`
- `chat_type`
- `raw_message`
- `reply_preview`
- `media_paths`

### 4. `media_runtime.py`

只实现聊天主链路需要的媒体能力。

入站：

- 下载公开 URL
- 单文件大小限制 20MB
- 失败时记录日志并忽略该项
- 成功后返回本地路径数组

出站：

- 接收 `mediaUrl` 或 `mediaUrls`
- 允许远程 URL 或本地绝对路径
- 本地路径必须受 `media_local_roots` 约束
- 通过 `POST /media/upload` 上传
- 根据 mime 推断 fragment kind
- 返回可直接写入 `message.reply` 的 fragment 列表

### 5. `connection.py`

负责 WebSocket 生命周期。

职责：

- 用 Bearer token 建连
- 心跳配置
- 握手状态机
- read loop / write queue
- backoff reconnect
- ack 跟踪与超时
- ready 前缓存出站消息
- 入站 frame 分发到 adapter

连接状态：

- `disconnected`
- `connecting`
- `handshaking`
- `ready`
- `reconnecting`
- `closed`

错误策略：

- malformed frame: 记日志并丢弃
- 握手失败: 关闭并触发重连
- ack timeout: 记日志并交由重连路径恢复，不做自动 resend

### 6. `adapter.py`

Hermes 对接层。

职责：

- 继承 `BasePlatformAdapter`
- 在 `connect()` 中启动 ClawChat connection
- 在入站回调中创建 `MessageEvent`
- 将 `send` / `edit_message` / `on_run_complete` 映射为静态或流式事件
- 管理 active run 状态
- 维护 stream buffer
- 在流式完成后发送 consolidated `message.reply`

## Data Flow

### Inbound

1. WebSocket 收到 frame
2. `protocol.py` 解码并判别事件类型
3. `connection.py` 将 `message.send` 转给 `inbound.py`
4. `inbound.py` 执行路由判断
5. 媒体下载完成后，组合成 Hermes `MessageEvent`
6. `adapter.py` 调用 `handle_message(event)`

### Outbound Static

1. Hermes 调用 `send(...)`
2. `adapter.py` 判断当前回复应走 static
3. 若有媒体，先走 `media_runtime.py` 上传
4. `protocol.py` 构造 `message.reply`
5. `connection.py` 发送并等待 ack

### Outbound Stream

1. Hermes 首次输出时建立 active run
2. 发 `message.created`
3. 内容进入 stream buffer
4. 达到 flush 条件时发 `message.add`
5. 完成时发 `message.done`
6. 再发最终 consolidated `message.reply`

## Stream Semantics

为了贴近 `openclaw-clawchat`，流式模式使用缓冲器而不是每个 token 都直接下发。

flush 条件：

- 达到 `flush_interval_ms`
- 新增字符达到 `min_chunk_chars`
- buffer 超过 `max_buffer_chars`
- run 完成时强制 flush

`message.add` 的 fragment 只包含文本：

- `text`: 当前完整文本
- `delta`: 本次新增部分

若 Hermes 输出发生前缀重置，即新文本不再以旧文本开头，则本次 `delta` 回退为完整文本，避免客户端流式拼接错误。

## Group Trigger Rules

direct:

- 永远触发

group with `group_mode = "all"`:

- 永远触发

group with `group_mode = "mention"`:

- 只有 `payload.message.context.mentions` 中包含当前 `user_id` 才触发

若 group 消息不触发，adapter 不回包，不报错，仅记 debug 日志。

## Reply Context

当上游消息是 reply 时，保留：

- replied sender id
- replied sender nick name
- replied fragments

这部分不改写为普通文本，而是作为结构化元数据放入 `raw_message["clawchat_reply"]`，同时可选生成一段简短 preview 文本供模型参考。

## Media Handling

### Inbound

文本正文中保留占位：

- image: `![name](url)`
- file/audio/video: `[name](url)`

上下文中注入：

- `MediaPath`: 第一项本地路径
- `MediaPaths`: 全量本地路径

若下载失败：

- 仅丢弃失败媒体
- 文本占位仍可保留 URL

### Outbound

若 reply 包含媒体：

- 上传所有媒体
- 将文本 fragment 与上传后 media fragments 合并
- 强制走单次 `message.reply`

如果部分媒体上传失败：

- 其余媒体继续发送
- 若最终仍有文本，文本照常发送
- 若所有媒体都失败且文本为空，则返回发送失败

## Testing Strategy

### Unit Tests

- `test_config.py`
  - 默认值与字段映射
- `test_protocol.py`
  - 握手签名
  - frame 构造
  - `hello-ok` 匹配
  - reply / stream envelopes
- `test_inbound.py`
  - direct / group / mention 路由
  - fragments 聚合
  - reply preview
  - media placeholders
- `test_media_runtime.py`
  - 本地路径限制
  - 上传结果映射
  - 单媒体失败容忍
- `test_connection.py`
  - 鉴权头
  - 握手完成
  - 错误 requestId 被忽略
  - 发送队列
  - 重连退避
- `test_adapter.py`
  - static reply
  - stream lifecycle
  - final consolidated reply
  - media 强制 static

### Integration Tests

- `fake_ws.py`: 模拟 ClawChat 服务端
- `fake_http.py` 或 monkeypatch fetch: 模拟 `/media/upload`
- 端到端验证：
  - `message.send` -> Hermes `handle_message`
  - Hermes `send/edit/on_run_complete` -> ClawChat frames

### Docker Debugging

最终联调步骤：

1. 将当前目录实现挂载到 Docker 中的 hermes 实例
2. 配置 `platforms.clawchat`
3. 启动 fake ClawChat WS/HTTP server 或对接真实测试环境
4. 观察握手、入站、流式回复、媒体上传
5. 修正协议细节直到 fake tests 与 Docker 实例都通过

## File Layout

建议结构：

```text
packages/hermes/clawchat/
  docs/superpowers/specs/
  pyproject.toml
  src/clawchat_gateway/
    __init__.py
    adapter.py
    config.py
    connection.py
    inbound.py
    media_runtime.py
    protocol.py
    stream_buffer.py
  tests/
    __init__.py
    conftest.py
    fake_ws.py
    test_adapter.py
    test_config.py
    test_connection.py
    test_inbound.py
    test_media_runtime.py
    test_protocol.py
```

## Risks

### Protocol Drift

TypeScript 参考实现可能存在文档未写明的 envelope 细节。缓解方式是优先以 `packages/openclaw-clawchat/src/*.test.ts` 的断言为准。

### Hermes Adapter Contract Unknowns

当前目录没有现成 Hermes gateway 代码。实现前必须先读取运行中的 `gateway.platforms.base`、`MessageEvent`、`SendResult` 等签名，避免接口假设错误。

### Streaming Semantics Mismatch

Hermes 的 `send` / `edit_message` / completion 生命周期可能与 `openclaw-clawchat` 的 stream dispatcher 不完全一致。需要通过 fake tests 和 Docker 实例同时验证。

### Media Runtime Variance

Hermes 侧可能已有媒体加载工具或路径限制机制。优先复用现有能力，避免自定义下载 / 上传实现与宿主冲突。

## Acceptance Criteria

- 能以 Python adapter 形式被 Hermes gateway 加载
- 能完成 `connect.challenge -> connect -> hello-ok` 握手
- 能正确处理 direct / group 入站消息
- `group_mode = "mention"` 只在提及时触发
- 能把 reply context 透传到 Hermes 事件
- 能发送静态 `message.reply`
- 能发送 `message.created/add/done` 与最终 consolidated `message.reply`
- 媒体消息可收可发
- 单元测试与 fake 集成测试通过
- Docker hermes 实例联调通过主链路

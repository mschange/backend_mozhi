# 墨知后端项目文档

墨知是一个面向个人资料问答与连续对话的 FastAPI 异步后端。项目目标不是只把模型调用包装成接口，而是把账号身份、用户隔离、会话记录、Agent 工具循环、长短期记忆、知识入库与多存储一致性放进一套可验证的服务边界中。普通 HTTP 接口使用统一 `{code, message, data}` 信封，流式对话使用 `delta/done/error` SSE 事件；当前 OpenAPI 对外路径共 15 条。

## 整体项目简介

### 身份、用户隔离与会话

- **注册、登录与 JWT**：注册会校验用户名和邮箱唯一性，密码只保存 bcrypt 哈希；登录支持用户名或邮箱。服务签发短期 access token 与长期 refresh token，二者都携带 `sub`、`token_type`、`iat`、`exp`，refresh token 不能直接访问受保护 API。
- **用户隔离**：HTTP 鉴权先从 access token 解析用户，再回查 MySQL。会话、消息、知识文档、长期记忆的 repository 查询都绑定当前用户；Milvus 检索表达式也包含 `user_id`，向量命中后还必须回查 MySQL 所有权和状态。
- **会话 CRUD**：接口支持创建、列表、详情、删除和重命名会话。详情返回持久化消息；删除会话同时清理 MySQL 记录和对应 PostgreSQL checkpoint thread。
- **新增用户消息**：普通发送和 SSE 发送都先锁定当前用户拥有的会话，再写入用户消息、更新会话时间，并在首条消息时按内容生成会话标题。空白消息会在进入模型前被拒绝。

### 对话、Agent 与记忆

- **普通与 SSE 对话**：`/api/chat/send` 内部消费同一套流式核心并返回最终助手消息；`/api/chat/stream` 使用独立 MySQL session，逐段发送 `delta`。助手消息和 checkpoint 水位写入后，SSE 层先提交 MySQL，再发送 `done`；提交或模型失败只发送 `error`。
- **短期记忆**：MySQL 最近 `SHORT_TERM_MEMORY_N` 条消息用于 checkpoint 不同步时的历史恢复；模型调用中间件再次按最近消息裁剪上下文，避免上下文无限增长。
- **长期记忆保存与查询**：Agent 可调用 `save_long_term_memory` 把用户事实规范化并按 SHA-256 去重。事实先提交 MySQL，再写 Milvus，索引失败会保留事实并标记失败。查询会重试可恢复索引、执行向量搜索，再按当前用户回查 MySQL 并返回前 5 条有效记忆。
- **工具循环**：默认工具包括知识检索、长期记忆查询、长期记忆保存，以及配置 Tavily key 后启用的联网搜索。模型可以发起一次或多次工具调用；工具结果作为消息返回模型，模型继续推理，直到产生最终回复。当前实现只有模型输入上下文裁剪中间件；输出侧由 Agent 流过滤工具节点并提取正文 token，没有虚构独立的“输出中间件”。

### 知识库与向量检索

- **上传与解析**：知识库接受 `.txt`、`.md`、`.pdf`。原文件以 UUID 文件名保存在 `uploads/`，原始文件名仅进入 MySQL 元数据；txt/md 以 UTF-8 容错读取，PDF 使用 `pypdf` 逐页抽取文本。
- **切片与 embedding**：文本使用 `RecursiveCharacterTextSplitter`，`chunk_size=500`、`chunk_overlap=80`，优先按段落、换行和中文标点切分，每个文档最多处理前 200 段。嵌入优先调用 DashScope 兼容接口；远端不可用时，进程会固定回退到同维度的本地哈希向量。
- **Milvus 检索与 MySQL 回查**：`knowledge_chunks` 保存用户、文档、文本和向量。检索先取当前用户前 20 个向量命中，再从 MySQL 筛出仍属于该用户且状态为 `ready` 的文档，最终按向量顺序返回前 5 段。Milvus 是可重建索引，不是权限或业务状态的事实源。

### 三类存储与错误日志

| 存储 | 当前职责 | 一致性边界 |
|---|---|---|
| MySQL | 用户、会话、消息、知识文档状态、长期记忆事实、checkpoint 同步水位 | 业务事实源；普通请求由依赖统一 commit/rollback，SSE 使用独立 session |
| PostgreSQL | `AsyncPostgresSaver` 管理 LangGraph checkpoint | thread id 同时包含 `user_id` 与 `conversation_id`；与 MySQL 水位不一致时删除 thread 并从消息恢复 |
| Milvus Lite/HTTP | `knowledge_chunks` 与 `long_term_memory` 向量索引 | 检索必须带用户过滤并回查 MySQL；schema 或 embedding 维度不兼容时拒绝启动 |

应用错误通过统一异常处理转换为稳定业务码；模型、知识解析、索引和生命周期异常使用 `logger.exception()` 记录 traceback。文件日志位于配置的 `LOG_FILE`，采用 UTF-8、按大小轮转，最低有效级别为 ERROR，不主动记录 token、密钥或完整用户正文。

## Agent 工具循环与 API/service/storage 流程

```text
用户输入
  ↓
┌─────────────────────────────────────┐
│ FastAPI API 与 JWT 鉴权             │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ ChatService 锁定当前用户拥有的会话  │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ MySQL 写用户消息并读取短期历史       │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ AgentRuntime / LangGraph            │ ←→ PostgreSQL Checkpoint
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ 输入中间件：裁剪最近消息             │ ← 修改模型输入上下文
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│              聊天模型               │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────┐
        │             │
  直接生成正文     发起 tool call
        │             ↓
        │    ┌─────────────────────────┐
        │    │       用户绑定工具       │
        │    └──────┬──────┬──────┬───┘
        │           │      │      │
        │           ↓      ↓      ↓
        │        知识检索  长期记忆  Tavily
        │                  查询/保存  可选搜索
        │           │      │      │
        │           └──┬───┘      │
        │              ↓          │
        │          Embedding      │
        │              ↓          │
        │        Milvus 向量索引   │
        │              │          │
        │              ↓          │
        │    MySQL 所有权/ready 状态回查
        │              │          │
        │              └────┬─────┘
        │                   ↓
        │          ┌──────────────────┐
        │          │    工具结果消息   │
        │          └────────┬─────────┘
        │                   └────────────→ 返回聊天模型继续推理
        ↓
┌─────────────────────────────────────┐
│ 正文 token 过滤与流式输出           │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│ MySQL 写助手消息与同步水位           │
└──────────────────┬──────────────────┘
                   ↓
             MySQL commit
               ┌───┴───┐
          成功 ↓       ↓ 失败
   普通响应或 SSE done  SSE error / 统一错误处理
```

```text
┌──────────────┐
│    客户端    │
└──────┬───────┘
       ↓
┌──────────────────┐
│   api/v1 路由    │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ services 业务层  │
└────┬──────┬────┬─┘
     │      │    │
     ↓      ↓    ↓
┌──────────┐ ┌──────────┐ ┌──────────────┐
│repository│ │  agent   │ │ uploads 原文件│
│ 数据访问 │ │  运行时  │ └──────────────┘
└────┬─────┘ └────┬─────┘
     ↓            ├────────────→ PostgreSQL checkpoint
┌──────────┐      ↓
│  MySQL   │ ┌──────────────────┐
└────↑─────┘ │知识/记忆/搜索工具│
     └───────┤                  │
             └────────┬─────────┘
                      ↓
                  Milvus
```

## 关键约束

1. 所有受保护资源查询和向量过滤都绑定当前 `user_id`。
2. 知识文档与长期记忆必须回查 MySQL，不能直接信任 Milvus 命中。
3. SSE 的 `done` 必须晚于 MySQL commit；提交失败只能发送 `error`。
4. MySQL 水位与 PostgreSQL checkpoint 不一致时，删除旧 thread 并从 MySQL 最近消息重建。
5. 密钥、token、密码和用户正文在文档中只使用占位值；真实 `.env` 不进入版本控制。

## 当前实现状态

| 能力 | 状态 | 说明 |
|---|---|---|
| 15 条 API、统一信封、六张 MySQL 表 | 已实现 | [07](./07-conversation-chat-and-sse.md) 说明服务与 API，[08](./08-api-testing-and-rebuild.md) 说明契约验证 |
| PostgreSQL AsyncPostgresSaver | 已实现 | 应用启动时必须可连接并执行 `setup()` |
| 两个 Milvus collection | 已实现 | 默认 Lite，也支持 HTTP URI |
| DeepSeek、DashScope、Tavily | 已实现 | Tavily 按 key 可选；嵌入可回退本地哈希 |
| 知识上传/检索、长期/短期记忆 | 已实现 | MySQL 是事实源，Milvus 索引可重建 |
| `reindex_document()` | 内部已实现、未开放 | 没有 HTTP 路由 |
| MinerU | 尚未实现 | 只保留配置项，PDF 实际由 pypdf 解析 |
| Alembic、应用 Dockerfile、后台队列 | 尚未实现 | Compose 只含 MySQL/PostgreSQL |
| refresh 自动续期/吊销 | 尚未实现 | 后端仅提供 refresh API |

## 项目验收

以下命令在项目的 `backend/` 目录执行；预期结果是 pytest 全部通过，并输出“最终结构验收通过”：

```bash
. .venv/bin/activate
pytest -q
python - <<'PY'
from app.main import app
from app.models import Base
assert len(app.openapi()["paths"]) == 15
assert len(Base.metadata.tables) == 6
print("最终结构验收通过")
PY
```

真实环境验收还应启动 MySQL、PostgreSQL、Milvus Lite 与模型服务，验证注册/登录、会话 CRUD、普通与 SSE 对话、知识上传及删除。任何 SSE `done` 都必须能立即在会话详情中读到对应的已提交消息。

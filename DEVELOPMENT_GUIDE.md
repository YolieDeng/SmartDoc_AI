# SmartDoc AI 开发流程详解

基于 Agentic RAG 架构的智能文档问答系统，完整开发流程分为 6 个阶段。

---

## 第一阶段：基础设施搭建

> 目标：搭建项目骨架，接通所有外部服务。

### 1.1 项目初始化

- 后端使用 `uv` 管理 Python 依赖（`pyproject.toml`），Python >= 3.11
- 前端使用 Vite + React + TypeScript + Tailwind CSS v4
- 根目录 `docker-compose.yml` 编排三个服务：backend、frontend、redis

### 1.2 配置管理 — `backend/app/core/config.py`

基于 `pydantic-settings`，从 `.env` 文件统一加载配置：

```python
class Settings(BaseSettings):
    openrouter_api_key: str          # Chat 模型（Gemini 2.0 Flash）
    zhipuai_api_key: str = ""        # 智谱 embedding-3
    supabase_url: str                # 向量数据库
    supabase_key: str
    redis_url: str = "redis://localhost:6379/0"
    tavily_api_key: str = ""         # 网络搜索（可选）
    api_key: str = ""                # 接口鉴权（可选）
    langsmith_api_key: str = ""      # 可观测性（可选）
```

用 `@lru_cache` 做单例，全局只实例化一次。

### 1.3 数据库客户端

| 服务 | 文件 | 作用 |
|------|------|------|
| Supabase | `app/db/supabase_client.py` | pgvector 向量存储，懒加载单例 |
| Redis | `app/db/redis_client.py` | 异步连接池（`redis.asyncio`），对话历史 + 答案缓存 |

### 1.4 FastAPI 入口 — `backend/main.py`

```python
app = FastAPI(title="SmartDoc AI", version="0.3.0", lifespan=lifespan)
app.add_middleware(ApiKeyMiddleware)   # API Key 鉴权
app.add_middleware(CORSMiddleware)     # 跨域
app.include_router(upload_router)     # /upload
app.include_router(qa_router)         # /ask, /ask/stream
```

`lifespan` 管理生命周期：启动时初始化 LangSmith，关闭时释放 Redis 连接。

---

## 第二阶段：文档处理管线（PDF → 向量入库）

> 目标：实现 PDF 上传后的完整处理流水线。

### 2.1 上传接口 — `backend/app/api/upload.py`

```
POST /upload  (multipart/form-data)
```

- 校验文件类型：仅允许 `application/pdf`
- 校验文件大小：上限 50MB
- 调用 `document_service.process_pdf()` 执行处理管线

### 2.2 文档处理服务 — `backend/app/services/document_service.py`

四步流水线：

```
保存临时文件 → PDF 解析 + 切片 → 批量向量化 → 批量入库
```

**Step 1 — PDF 解析**
- 使用 `PyMuPDFLoader` 解析 PDF 内容
- CPU 密集操作，通过 `asyncio.to_thread` 放到线程池执行

**Step 2 — 文本切片**
- 使用 `RecursiveCharacterTextSplitter`
- 参数：`chunk_size=500`, `chunk_overlap=50`
- 递归按段落、句子、字符分割，保证语义完整性

**Step 3 — 批量向量化**
- 调用智谱 AI `embedding-3` 模型（HTTP 直连，避免 SDK 版本冲突）
- 分批并发请求（默认 batch_size=64）
- 使用 `asyncio.gather` 并发处理多个批次

**Step 4 — 批量入库**
- 写入 Supabase `documents` 表（content + metadata + embedding）
- 分批插入，每批 500 条

---

## 第三阶段：Agentic RAG 智能体（核心）

> 目标：构建 LangGraph 状态机工作流，实现智能路由 + 自我纠错。

### 3.1 Agent 状态定义 — `backend/app/agent/state.py`

```python
class AgentState(TypedDict):
    question: str          # 用户问题
    history: list[dict]    # 对话历史
    tool_name: str         # "rag_search" | "web_search"
    context: str           # 检索到的上下文
    sources: list[str]     # 来源列表
    answer: str            # 生成的回答
    retried: bool          # 是否已重试
```

### 3.2 工具实现 — `backend/app/agent/tools.py`

**rag_search（文档检索）**
```
用户问题 → 智谱 embedding-3 向量化 → Supabase match_documents RPC → Top-3 结果
```
- 调用 Supabase 的 `match_documents` RPC 函数进行 pgvector 相似度匹配

**web_search（网络搜索）**
```
用户问题 → Tavily API → Top-3 搜索结果
```
- 使用 `asyncio.to_thread` 包装同步 SDK 调用

### 3.3 LangGraph 工作流 — `backend/app/agent/graph.py`

```
┌─────────┐     ┌──────┐     ┌──────────┐     ┌─────────┐
│  Route  │────▶│ Tool │────▶│ Generate │────▶│ Reflect │
└─────────┘     └──────┘     └──────────┘     └────┬────┘
                  ▲                                  │
                  │           ┌─────────────┐        │
                  └───────────│ Switch Tool │◀───────┘
                              └─────────────┘    (不合格 & 未重试)
```

**四个节点：**

| 节点 | 功能 | 实现方式 |
|------|------|----------|
| `route_node` | 意图识别，决定用哪个工具 | OpenRouter Function Calling，定义了 rag_search 和 web_search 两个 tool |
| `tool_node` | 执行选中的工具 | 根据 tool_name 分发到 rag_search 或 web_search |
| `generate_node` | 基于上下文生成回答 | OpenRouter Chat Completion（Gemini 2.0 Flash） |
| `reflect_edge` | 质量检查（条件边） | 检测回答中是否包含"不知道""未找到"等不确定关键词 |

**自我纠错机制：**
- `reflect_edge` 检测到回答质量不合格时，进入 `switch_tool_node`
- 切换工具（RAG ↔ Web），标记 `retried=True`，重新执行 tool → generate
- 最多重试一次，防止无限循环

---

## 第四阶段：问答服务层（流式 + 非流式）

> 目标：封装 Agent 调用，实现缓存、对话历史、流式输出。

### 4.1 会话服务 — `backend/app/services/session_service.py`

**对话历史管理：**
- Redis List 存储，key 格式：`session:{session_id}:history`
- 最多保留 10 条消息（5 轮对话），TTL 1 小时
- 使用 Pipeline 批量操作（rpush + ltrim + expire）

**答案缓存：**
- 对问题做 MD5 哈希作为 key：`cache:answer:{hash}`
- 缓存 TTL 30 分钟
- 完全相同的问题直接返回缓存，跳过 LLM 调用

**容错设计：** Redis 不可用时静默降级（catch + warning log），不影响核心问答功能。

### 4.2 问答编排 — `backend/app/services/qa_service.py`

**非流式 `ask()`：**
```
缓存检查 → 加载对话历史 → agent_graph.ainvoke() → 写缓存 + 写历史 → 返回结果
```

**流式 `ask_stream()`：**
```
缓存检查 → 加载对话历史 → 手动执行 route_node + tool_node
→ SSE 推送工具名和来源 → httpx 流式调用 OpenRouter → 逐 token SSE 推送
→ 写缓存 + 写历史
```

流式模式的关键设计：
- 手动拆分 graph 执行（route → tool），不走 generate_node，避免双重 LLM 调用
- 直接用 `httpx.AsyncClient.stream()` 流式请求 OpenRouter
- 解析 SSE 格式的 `data:` 行，逐 token 转发给前端

### 4.3 API 路由 — `backend/app/api/qa.py`

```python
POST /ask          → 非流式，返回 JSON
POST /ask/stream   → 流式，返回 SSE（EventSourceResponse）
```

### 4.4 SSE 事件协议

前后端约定的 SSE 事件类型：

| type | 含义 | payload |
|------|------|---------|
| `tool` | 使用了哪个工具 | `{ name: "rag_search" \| "web_search" }` |
| `sources` | 参考来源 | `{ content: string[] }` |
| `token` | 回答内容片段 | `{ content: string }` |
| `error` | 错误信息 | `{ content: string }` |
| `done` | 流结束 | `{}` |

---

## 第五阶段：前端交互层

> 目标：构建聊天式 UI，实现文件上传和 SSE 流式对话。

### 5.1 技术栈

- React 19 + TypeScript 5.9
- Tailwind CSS v4（通过 `@tailwindcss/vite` 插件集成）
- Vite 7 开发服务器，配置 `/api` 代理到后端 `localhost:8000`

### 5.2 组件结构

```
App.tsx
├── FileUpload.tsx    — PDF 上传按钮 + 状态反馈
├── MessageList.tsx   — 消息列表（气泡样式 + 自动滚动）
└── ChatInput.tsx     — 输入框 + 发送/停止按钮
```

**App.tsx** — 页面布局：顶栏（标题 + 上传 + 新对话）、消息区、输入区

**FileUpload.tsx** — 文件上传组件：
- `<input type="file" accept=".pdf">` 隐藏在 label 内
- FormData 上传到 `/api/upload`
- 显示上传状态和切片数量

**MessageList.tsx** — 消息展示：
- 用户消息右对齐蓝色气泡，助手消息左对齐灰色气泡
- 显示工具标签（📄 文档检索 / 🌐 网络搜索）
- 可折叠的参考来源（`<details>` 标签）
- `useEffect` + `scrollIntoView` 自动滚动到底部

**ChatInput.tsx** — 输入控制：
- 流式输出中禁用输入框，显示"停止"按钮
- 空内容时禁用发送按钮

### 5.3 核心 Hook — `frontend/src/hooks/useChat.ts`

```typescript
export function useChat() {
  // 状态：messages, streaming
  // 方法：send, stop, clear

  // send() 流程：
  // 1. 添加 user 消息 + 空 assistant 占位消息
  // 2. fetch('/api/ask/stream') 获取 ReadableStream
  // 3. 逐行解析 SSE data: 行
  // 4. 根据 evt.type 更新 assistant 消息（token/tool/sources/error）
  // 5. AbortController 支持中断

  // clear() → 清空消息 + 重新生成 sessionId
}
```

关键实现细节：
- 使用 `crypto.randomUUID()` 生成 session_id，关联后端对话历史
- `ReadableStream` + `TextDecoder` 手动解析 SSE（不依赖 EventSource API，支持 POST）
- `AbortController` 实现流式中断

---

## 第六阶段：安全、可观测性与部署

> 目标：加固安全、接入监控、容器化部署。

### 6.1 API Key 鉴权 — `backend/app/core/auth.py`

- 纯 ASGI 中间件（不缓冲 response body，兼容 SSE 流式输出）
- 从请求头 `X-API-Key` 提取 token 进行校验
- `/docs`、`/openapi.json`、`/redoc` 为公开路径
- `API_KEY` 为空时不启用鉴权

### 6.2 LangSmith 可观测性 — `backend/app/core/langsmith.py`

- 在 `lifespan` 启动时设置环境变量启用 tracing
- 可选功能，`LANGSMITH_API_KEY` 为空时不启用
- 追踪 LangGraph 工作流的每个节点执行

### 6.3 Docker 部署

**docker-compose.yml — 三个服务：**

```yaml
services:
  backend:    # FastAPI，端口 8000，依赖 redis
  frontend:   # Nginx 静态托管，端口 3000，依赖 backend
  redis:      # Redis 7 Alpine，持久化 volume
```

**前端 Nginx 配置（`frontend/nginx.conf`）：**
- `/` → 静态文件 + SPA fallback（`try_files`）
- `/upload` → 反向代理到 backend:8000，`client_max_body_size 50m`
- `/ask` → 反向代理到 backend:8000，关闭 `proxy_buffering` 以支持 SSE 流式

**后端 Dockerfile：** 基于 Python 镜像，使用 uvicorn 运行
**前端 Dockerfile：** 多阶段构建，先 `npm run build`，再用 nginx 托管 dist

### 6.4 本地开发

```bash
# 后端
cd backend && cp .env.example .env  # 填入 API Key
uv sync && uv run uvicorn main:app --reload

# 前端
cd frontend && npm install && npm run dev
# Vite 代理 /api → localhost:8000（自动去掉 /api 前缀）
```

---

## 整体数据流总结

```
┌──────────────────────────────────────────────────────────────────┐
│                          用户浏览器                               │
│                                                                  │
│  ┌────────────┐   POST /upload   ┌────────────────────────────┐  │
│  │ FileUpload │─────────────────▶│ upload API                 │  │
│  └────────────┘                  │  → PyMuPDF 解析            │  │
│                                  │  → RecursiveTextSplitter   │  │
│  ┌────────────┐   POST /ask/     │  → 智谱 embedding-3       │  │
│  │  ChatInput │───stream────────▶│  → Supabase 入库           │  │
│  └────────────┘                  └────────────────────────────┘  │
│        │                                                         │
│        ▼                                                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    SSE 流式问答                              │  │
│  │                                                            │  │
│  │  1. Redis 缓存检查                                          │  │
│  │  2. Route（Function Calling 意图识别）                       │  │
│  │     ├── rag_search → 智谱 Embedding + pgvector 检索         │  │
│  │     └── web_search → Tavily 网络搜索                        │  │
│  │  3. OpenRouter 流式生成（Gemini 2.0 Flash）                  │  │
│  │  4. Reflect 质量检查 → 不合格则切换工具重试                    │  │
│  │  5. 写入 Redis 缓存 + 对话历史                               │  │
│  └────────────────────────────────────────────────────────────┘  │
│        │                                                         │
│        ▼ SSE events (tool → sources → token* → done)             │
│  ┌─────────────┐                                                 │
│  │ MessageList │  逐 token 渲染回答                               │
│  └─────────────┘                                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 技术栈速查

| 层 | 技术 | 用途 |
|---|------|------|
| LLM | OpenRouter (Gemini 2.0 Flash) | Chat 生成 + 意图路由 |
| Embedding | 智谱 AI (embedding-3) | 文档/查询向量化 |
| 编排 | LangGraph StateGraph | Agent 工作流状态机 |
| 后端 | FastAPI + SSE-Starlette | REST API + 流式输出 |
| HTTP | httpx | 异步 HTTP 客户端 |
| PDF | PyMuPDF | PDF 解析 |
| 切片 | LangChain Text Splitters | 文本分割 |
| 向量库 | Supabase (pgvector) | 向量存储 + 相似度检索 |
| 缓存 | Redis 7 | 对话历史 + 答案缓存 |
| 搜索 | Tavily | 网络搜索 |
| 监控 | LangSmith | Agent 执行追踪 |
| 前端 | React 19 + Tailwind CSS v4 | 聊天 UI |
| 构建 | Vite 7 | 前端构建 + 开发代理 |
| 部署 | Docker Compose + Nginx | 容器编排 + 反向代理 |


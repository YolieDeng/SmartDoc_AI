# SmartDoc AI

基于 Agentic RAG 架构的智能文档问答系统。上传 PDF，提问即可获得基于文档内容的精准回答。系统默认优先检索本地文档，文档中找不到答案时自动 fallback 到网络搜索，并具备自我纠错能力。

## 技术栈

| 层 | 技术 |
|---|------|
| LLM | OpenRouter (Gemini 2.0 Flash) |
| Embedding | OpenRouter (Gemini Embedding 001, 3072 维) |
| 编排 | LangGraph 状态机工作流 |
| 后端 | FastAPI + SSE 流式输出 |
| 向量库 | Supabase (pgvector) |
| 缓存 | Redis (对话历史 + 答案缓存) |
| 前端 | React + Tailwind CSS + react-markdown |
| 部署 | Docker Compose |

## 工作流

```
用户提问 → Router (关键词路由)
              │
              ├── 默认 → rag_search → Gemini Embedding + pgvector 向量检索
              └── 用户明确要求联网 → web_search → Tavily 网络搜索
                      ↓
              Generate (基于上下文生成回答, temperature=0)
                      ↓
              Reflect (质量检查)
              ├── 合格 → 返回答案
              └── 不合格 → 切换工具重试 (最多一次)
```

### 路由策略

- **默认走本地文档检索** (`rag_search`)，确保上传的文档优先被使用
- 用户提问包含"上网查"、"最新"、"今天"等关键词时，走网络搜索 (`web_search`)
- 如果 `rag_search` 回答质量不合格（包含"未找到"、"未提及"等关键词），自动 fallback 到 `web_search` 重试

## 项目结构

```
.
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── app/
│   │   ├── agent/
│   │   │   ├── graph.py           # LangGraph 工作流 (Route→Tool→Generate→Reflect)
│   │   │   ├── tools.py           # rag_search / web_search 工具
│   │   │   └── state.py           # AgentState 定义
│   │   ├── api/
│   │   │   ├── qa.py              # POST /ask, POST /ask/stream
│   │   │   └── upload.py          # POST /upload
│   │   ├── services/
│   │   │   ├── qa_service.py      # 问答编排 (非流式 + 流式)
│   │   │   ├── document_service.py # PDF 解析 → 切片 → 向量化 → 入库
│   │   │   └── session_service.py  # Redis 对话历史 + 答案缓存
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings 配置
│   │   │   ├── auth.py            # API Key 中间件 (ASGI)
│   │   │   └── langsmith.py       # LangSmith 初始化
│   │   └── db/
│   │       ├── redis_client.py
│   │       └── supabase_client.py
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── hooks/useChat.ts       # SSE 流式解析 + 状态管理
│   │   └── components/
│   │       ├── FileUpload.tsx
│   │       ├── MessageList.tsx     # Markdown 渲染 (react-markdown)
│   │       └── ChatInput.tsx
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 前置条件

- Supabase 项目，启用 pgvector 扩展，并创建 `documents` 表和 `match_documents` RPC 函数（见下方数据库初始化）
- Redis
- OpenRouter API Key

### 数据库初始化

在 Supabase SQL Editor 中执行：

```sql
-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建 documents 表
CREATE TABLE documents (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  content    TEXT NOT NULL,
  metadata   JSONB DEFAULT '{}'::jsonb,
  embedding  VECTOR(3072),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 创建向量相似度搜索函数
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding VECTOR(3072),
  match_count     INT DEFAULT 5
)
RETURNS TABLE (
  id         BIGINT,
  content    TEXT,
  metadata   JSONB,
  similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    content,
    metadata,
    1 - (embedding <=> query_embedding) AS similarity
  FROM documents
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

### 本地开发

```bash
# 后端
cd backend
cp .env.example .env   # 填入你的 API Key
uv sync
uv run uvicorn main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
# 确保 backend/.env 已配置
docker compose up -d
# 前端: http://localhost:3000
# 后端: http://localhost:8000/docs
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENROUTER_API_KEY` | 是 | Chat + Embedding 共用 API Key |
| `OPENROUTER_MODEL` | 否 | Chat 模型，默认 `google/gemini-2.0-flash-001` |
| `OPENROUTER_EMBED_MODEL` | 否 | Embedding 模型，默认 `google/gemini-embedding-001` |
| `SUPABASE_URL` | 是 | Supabase 项目 URL |
| `SUPABASE_KEY` | 是 | Supabase anon/service key |
| `TAVILY_API_KEY` | 否 | 网络搜索功能，留空则 web_search 不可用 |
| `REDIS_URL` | 否 | 默认 `redis://localhost:6379/0` |
| `API_KEY` | 否 | 接口鉴权，留空则不启用 |
| `LANGSMITH_API_KEY` | 否 | LangSmith 监控，留空则不启用 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传 PDF 文件（最大 50MB），自动解析、切片、向量化入库 |
| POST | `/ask` | 非流式问答 |
| POST | `/ask/stream` | SSE 流式问答 |

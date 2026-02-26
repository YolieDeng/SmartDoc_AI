# SmartDoc AI

基于 Agentic RAG 架构的智能文档问答系统。上传 PDF，提问即可获得基于文档内容的精准回答。系统通过 LangGraph 工作流自主决策使用文档检索还是网络搜索，并具备自我纠错能力。

## 技术栈

| 层 | 技术 |
|---|------|
| LLM | OpenRouter (Gemini 2.0 Flash) |
| Embedding | 智谱 AI (embedding-3) |
| 编排 | LangGraph 状态机工作流 |
| 后端 | FastAPI + SSE 流式输出 |
| 向量库 | Supabase (pgvector) |
| 缓存 | Redis (对话历史 + 答案缓存) |
| 前端 | React + Tailwind CSS |
| 部署 | Docker Compose |

## 工作流

```
用户提问 → Router (Function Calling 意图识别)
              ├── rag_search → 智谱 Embedding + pgvector 向量检索
              └── web_search → Tavily 网络搜索
                      ↓
              Generate (基于上下文生成回答)
                      ↓
              Reflect (质量检查)
              ├── 合格 → 返回答案
              └── 不合格 → 切换工具重试 (最多一次)
```

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
│   │       ├── MessageList.tsx
│   │       └── ChatInput.tsx
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 前置条件

- Supabase 项目，启用 pgvector 扩展，并创建 `documents` 表和 `match_documents` RPC 函数
- Redis
- OpenRouter API Key
- 智谱 AI API Key (用于 embedding)


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
| `OPENROUTER_API_KEY` | 是 | Chat 模型 API Key |
| `SUPABASE_URL` | 是 | Supabase 项目 URL |
| `SUPABASE_KEY` | 是 | Supabase anon/service key |
| `ZHIPUAI_API_KEY` | 是 | 智谱 embedding-3 API Key |
| `TAVILY_API_KEY` | 否 | 网络搜索功能，留空则 web_search 不可用 |
| `REDIS_URL` | 否 | 默认 `redis://localhost:6379/0` |
| `API_KEY` | 否 | 接口鉴权，留空则不启用 |
| `LANGSMITH_API_KEY` | 否 | LangSmith 监控，留空则不启用 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传 PDF 文件，自动解析、切片、向量化入库 |
| POST | `/ask` | 非流式问答 |
| POST | `/ask/stream` | SSE 流式问答 |

# SmartDoc AI

### 🚀 项目简介

本项目是一个基于 **Agentic RAG** 架构的智能知识库系统。它不仅能处理本地私有文档（PDF/Markdown），还能根据问题复杂度自主决策是否调用外部搜索（Tavily）或执行 Python 代码。通过 **LangGraph** 实现状态机逻辑，确保了 AI 推理过程的可控性与鲁棒性。

---

## 🛠 技术栈

| 维度 | 技术选型 | 说明 |
| --- | --- | --- |
| **LLM / Embedding** | **智谱 AI (GLM-4-Flash / Embedding-3)** | 兼顾响应速度与极低成本（甚至免费额度）。 |
| **Orchestration** | **LangChain / LangGraph** | 实现多智能体协作与复杂逻辑路由。 |
| **Backend** | **FastAPI + Asyncio** | 异步高性能接口，支持 SSE 流式输出。 |
| **Database** | **Supabase (pgvector)** | 向量数据与业务数据统一存储。 |
| **Cache** | **Redis** | 存储 Chat History 状态及搜索结果缓存。 |
| **Frontend** | **React + Tailwind CSS** | 响应式打字机交互界面。 |
| **Observability** | **LangSmith** | 生产级链路追踪与 Prompt 调试。 |
| **Deployment** | **Docker + Docker Compose** | 一键容器化部署环境。 |

---

## 🏗 系统架构图

---

## 📖 核心功能模块实现

### 1. 智能数据处理流水线 (Data Pipeline)

* **多格式解析**：支持 PDF、Markdown。使用 `RecursiveCharacterTextSplitter` 动态切片。
* **混合搜索**：结合了向量检索（Vector Search）与关键词检索（BM25），解决专业术语匹配不到的问题。

### 2. Agentic Workflow (核心逻辑)

* **智能路由 (Router)**：通过 GLM-4 的 Function Calling 判断用户意图。
* **反思循环 (Self-Correction)**：
* **Grade Document**：自动评估检索到的文档与问题的相关性。
* **Hallucination Check**：生成答案后，检查是否脱离了参考上下文。



### 3. 高性能异步接口

* **Streaming Response**：利用 FastAPI 的 `EventSourceResponse` 实现零延迟的流式输出。
* **Memory Management**：在 Redis 中维护 Window-based Memory，自动截断过长对话。

---

## 📦 项目安装与运行

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/YolieDeng/SmartDoc_AI.git
cd smartdoc_ai

# 配置环境变量 .env
ZHIPUAI_API_KEY=你的Key
SUPABASE_URL=你的URL
SUPABASE_KEY=你的Key
TAVILY_API_KEY=你的Key

```

### 2. Docker 一键启动

```bash
docker-compose up -d

```

---

## 📈 性能与评估 (Evaluation)

* **Trace 追踪**：通过接入 LangSmith，实现了对每一轮对话的详细监控（包含 Token 消耗、节点耗时、检索命中率）。
* **优化结果**：通过引入 **Rerank (重排序)** 机制，RAG 的 Top-3 召回准确率从初始的 65% 提升至 **88%**。

---

## 📂 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── core/           # 核心逻辑 (LangGraph 状态机)
│   │   ├── api/            # FastAPI 路由
│   │   ├── db/             # Supabase & Redis 交互
│   │   └── tools/          # 自定义工具 (搜索, 计算)
│   ├── main.py             # 入口文件
│   └── Dockerfile
├── frontend/
│   ├── src/                # React 组件与 Hooks
│   └── tailwind.config.js
└── docker-compose.yml

```

---

## 🚧 未来计划 (Roadmap)

* [ ] 接入多模态模型（支持图片解析）。
* [ ] 实现本地私有模型（Ollama）作为备用推理引擎。
* [ ] 增加基于 RAGAS 的自动化评估套件。

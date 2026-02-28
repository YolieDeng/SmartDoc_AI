import json

import httpx
from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.agent.tools import rag_search, web_search
from app.core.config import get_settings

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# Router 使用的 Function Calling 工具定义
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "搜索本地上传的文档库，适用于公司内部制度、产品文档等私有数据问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网，适用于新闻、实时信息、通用知识等需要联网的问题",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

# 判定回答质量不合格的关键词
UNCERTAIN_KEYWORDS = [
    "不知道", "未找到", "无法回答", "没有相关",
    "无法确定", "不确定", "抱歉", "未提及",
]

# 用户明确要求联网搜索的关键词
WEB_SEARCH_KEYWORDS = [
    "上网查", "联网查", "联网搜", "网上搜", "网上查",
    "搜索一下", "百度", "谷歌", "google",
    "最新", "今天", "今日", "实时",
]


def _get_headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }


# ── 节点函数 ──


async def route_node(state: AgentState) -> dict:
    """Router：默认走 rag_search，用户明确要求联网时走 web_search。"""
    question = state["question"].lower()
    if any(kw in question for kw in WEB_SEARCH_KEYWORDS):
        return {"tool_name": "web_search"}
    return {"tool_name": "rag_search"}


async def tool_node(state: AgentState) -> dict:
    """执行 Router 选择的工具。"""
    question = state["question"]
    if state["tool_name"] in ("web", "web_search"):
        result = await web_search(question)
    else:
        result = await rag_search(question)
    return {"context": result["context"], "sources": result["sources"]}


async def generate_node(state: AgentState) -> dict:
    """基于上下文生成回答。"""
    context = state.get("context", "")
    if not context:
        return {"answer": "未找到相关信息。"}

    history = state.get("history", [])
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的问答助手。你必须严格根据下面提供的参考资料回答用户问题。"
                "回答必须直接引用参考资料中的原文信息，不得添加、推测或编造任何参考资料中没有的内容。"
                "如果参考资料中没有相关信息，请明确回复'参考资料中未提及相关信息'。"
            ),
        },
    ]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": (
            f"以下是参考资料：\n\n{context}\n\n---\n\n"
            f"用户问题：{state['question']}\n\n"
            f"请严格根据以上参考资料回答，直接引用原文中的信息。"
        ),
    })

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            OPENROUTER_CHAT_URL,
            json={
                "model": get_settings().openrouter_model,
                "messages": messages,
                "temperature": 0,
            },
            headers=_get_headers(),
            timeout=60,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]

    return {"answer": answer}


def reflect_edge(state: AgentState) -> str:
    """反思：检查回答质量，决定是否重试。"""
    answer = state.get("answer", "")
    has_uncertainty = any(kw in answer for kw in UNCERTAIN_KEYWORDS)

    if not has_uncertainty or state.get("retried", False):
        return "end"
    return "retry"


async def switch_tool_node(state: AgentState) -> dict:
    """切换工具并标记已重试。"""
    current = state.get("tool_name", "rag_search")
    new_tool = "web_search" if current in ("rag", "rag_search") else "rag_search"
    return {"tool_name": new_tool, "retried": True}


# ── 构建 Graph ──


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("route", route_node)
    g.add_node("tool", tool_node)
    g.add_node("generate", generate_node)
    g.add_node("switch_tool", switch_tool_node)

    g.set_entry_point("route")
    g.add_edge("route", "tool")
    g.add_edge("tool", "generate")
    g.add_conditional_edges(
        "generate",
        reflect_edge,
        {"end": END, "retry": "switch_tool"},
    )
    g.add_edge("switch_tool", "tool")

    return g.compile()


# 单例
agent_graph = build_graph()

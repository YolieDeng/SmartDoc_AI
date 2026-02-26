import json

import httpx
from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.agent.tools import rag_search, web_search
from app.core.config import get_settings

ZHIPU_CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

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
    "无法确定", "不确定", "抱歉",
]


def _get_headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json",
    }


# ── 节点函数 ──


async def route_node(state: AgentState) -> dict:
    """Router：用 GLM-4 Function Calling 判断该用哪个工具。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个智能路由器。根据用户问题判断应该使用哪个工具。"
                "如果问题涉及用户上传的文档、公司内部资料，使用 rag_search。"
                "如果问题涉及新闻、实时信息、通用知识，使用 web_search。"
            ),
        },
        {"role": "user", "content": state["question"]},
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ZHIPU_CHAT_URL,
            json={
                "model": "glm-4-flash",
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
            },
            headers=_get_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]["message"]

    tool_calls = choice.get("tool_calls", [])
    if tool_calls:
        return {"tool_name": tool_calls[0]["function"]["name"]}
    # 默认走 RAG
    return {"tool_name": "rag"}


async def tool_node(state: AgentState) -> dict:
    """执行 Router 选择的工具。"""
    question = state["question"]
    if state["tool_name"] == "web":
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
                "你是一个专业的问答助手。请根据参考资料回答用户问题。"
                "如果参考资料中没有相关信息，请如实说明。不要编造。"
            ),
        },
    ]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": f"参考资料：\n{context}\n\n用户问题：{state['question']}",
    })

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ZHIPU_CHAT_URL,
            json={"model": "glm-4-flash", "messages": messages},
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
    current = state.get("tool_name", "rag")
    new_tool = "web" if current == "rag" else "rag"
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

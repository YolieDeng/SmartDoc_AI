import json
from collections.abc import AsyncGenerator

import httpx

from app.agent.graph import agent_graph
from app.agent.tools import rag_search, web_search
from app.core.config import get_settings
from app.services.session_service import (
    append_history,
    get_cached_answer,
    get_history,
    set_cached_answer,
)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "你是一个专业的问答助手。请根据参考资料回答用户问题。"
    "如果参考资料中没有相关信息，请如实说明。不要编造。"
)


# ── 非流式问答 ──


async def ask(question: str, session_id: str | None = None) -> dict:
    """非流式问答：通过 agent graph 智能调度工具后生成回答。"""
    # 缓存命中
    if session_id is None:
        cached = await get_cached_answer(question)
        if cached:
            return {"answer": cached, "sources": [], "cached": True}

    history = await get_history(session_id) if session_id else []

    # 运行 agent graph
    state = await agent_graph.ainvoke({
        "question": question,
        "history": history,
        "tool_name": "",
        "context": "",
        "sources": [],
        "answer": "",
        "retried": False,
    })

    answer = state.get("answer", "")
    sources = state.get("sources", [])

    # 写入缓存和对话历史
    await set_cached_answer(question, answer)
    if session_id:
        await append_history(session_id, question, answer)

    return {
        "answer": answer,
        "sources": sources,
        "tool": state.get("tool_name", ""),
    }


# ── 流式问答 ──


async def ask_stream(
    question: str, session_id: str | None = None
) -> AsyncGenerator[str, None]:
    """流式问答：先通过 graph 路由+检索，再流式生成回答。"""
    history = await get_history(session_id) if session_id else []

    # 1. 运行 route 节点获取工具选择
    route_state = await agent_graph.ainvoke({
        "question": question,
        "history": history,
        "tool_name": "",
        "context": "",
        "sources": [],
        "answer": "",
        "retried": False,
    })

    tool_name = route_state.get("tool_name", "rag")
    context = route_state.get("context", "")
    sources = route_state.get("sources", [])
    answer_from_graph = route_state.get("answer", "")

    # 通知前端使用了哪个工具
    yield _sse_data({"type": "tool", "name": tool_name})

    if sources:
        yield _sse_data({"type": "sources", "content": sources})

    if not context:
        yield _sse_data({
            "type": "error",
            "content": "未找到相关信息。",
        })
        yield _sse_data({"type": "done"})
        return

    # 2. 流式生成回答
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": f"参考资料：\n{context}\n\n用户问题：{question}",
    })

    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    full_answer = ""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            OPENROUTER_CHAT_URL,
            json={
                "model": settings.openrouter_model,
                "messages": messages,
                "stream": True,
            },
            headers=headers,
            timeout=60,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_answer += content
                    yield _sse_data({"type": "token", "content": content})

    # 写入缓存和对话历史
    await set_cached_answer(question, full_answer)
    if session_id:
        await append_history(session_id, question, full_answer)

    yield _sse_data({"type": "done"})


def _sse_data(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)

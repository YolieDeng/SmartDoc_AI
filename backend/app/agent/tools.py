import asyncio

import httpx
from tavily import TavilyClient

from app.core.config import get_settings
from app.db.supabase_client import get_supabase

OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
TOP_K = 3


async def rag_search(question: str) -> dict:
    """本地文档向量检索，返回 {context, sources}。"""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    # 向量化
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            OPENROUTER_EMBED_URL,
            json={"model": settings.openrouter_embed_model, "input": [question]},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        embedding = resp.json()["data"][0]["embedding"]

    # 检索
    matches = await asyncio.to_thread(_match_documents, embedding, TOP_K)
    if not matches:
        return {"context": "", "sources": []}

    sources = [m["content"] for m in matches]
    context = "\n\n---\n\n".join(sources)
    return {"context": context, "sources": sources}


async def web_search(question: str) -> dict:
    """Tavily 网络搜索，返回 {context, sources}。"""
    settings = get_settings()
    if not settings.tavily_api_key:
        return {"context": "", "sources": []}
    client = TavilyClient(api_key=settings.tavily_api_key)
    result = await asyncio.to_thread(
        client.search, question, max_results=3
    )
    results = result.get("results", [])
    if not results:
        return {"context": "", "sources": []}

    sources = [r.get("content", "") for r in results]
    context = "\n\n---\n\n".join(sources)
    return {"context": context, "sources": sources}


def _match_documents(query_embedding: list[float], top_k: int) -> list[dict]:
    """调用 Supabase RPC 函数进行向量相似度匹配。"""
    sb = get_supabase()
    result = sb.rpc(
        "match_documents",
        {"query_embedding": query_embedding, "match_count": top_k},
    ).execute()
    return result.data or []

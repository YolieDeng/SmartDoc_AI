import asyncio
import tempfile
from pathlib import Path

import httpx
from fastapi import UploadFile
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.db.supabase_client import get_supabase

# 切片参数
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


async def process_pdf(file: UploadFile) -> int:
    """完整流水线：保存 → 解析切片 → 向量化 → 入库，返回 chunk 数量。"""
    settings = get_settings()

    # 1. 保存临时文件（PyMuPDFLoader 需要文件路径）
    suffix = Path(file.filename or "doc.pdf").suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.close()

        # 2. 解析 + 切片（CPU 密集，放到线程池）
        chunks = await asyncio.to_thread(_parse_and_split, tmp.name)
        if not chunks:
            return 0

        # 3. 批量向量化
        texts = [c.page_content for c in chunks]
        embeddings = await _batch_embed(texts, settings)

        # 4. 批量入库
        rows = [
            {
                "content": chunks[i].page_content,
                "metadata": chunks[i].metadata,
                "embedding": embeddings[i],
            }
            for i in range(len(chunks))
        ]
        await asyncio.to_thread(_batch_insert, rows)

        return len(chunks)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


# ── 内部函数 ──────────────────────────────────────────────


def _parse_and_split(file_path: str) -> list:
    """解析 PDF 并切片。"""
    docs = PyMuPDFLoader(file_path).load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(docs)


async def _batch_embed(texts: list[str], settings) -> list[list[float]]:
    """分批并发调用 OpenRouter embedding 接口。"""
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    batches = [texts[i : i + settings.embedding_batch_size] for i in range(0, len(texts), settings.embedding_batch_size)]

    async def _embed_one(client: httpx.AsyncClient, batch: list[str]) -> list[list[float]]:
        resp = await client.post(
            OPENROUTER_EMBED_URL,
            json={"model": settings.openrouter_embed_model, "input": batch},
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_embed_one(client, b) for b in batches])
    return [vec for batch_result in results for vec in batch_result]


def _batch_insert(rows: list[dict], batch_size: int = 500) -> None:
    """分批插入 Supabase documents 表。"""
    sb = get_supabase()
    for i in range(0, len(rows), batch_size):
        sb.table("documents").insert(rows[i : i + batch_size]).execute()

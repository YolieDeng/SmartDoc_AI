import hashlib
import json
import logging

from app.db.redis_client import get_redis

logger = logging.getLogger(__name__)

HISTORY_MAX_MESSAGES = 10  # 5 轮（user + assistant 各一条）
HISTORY_TTL = 3600  # 1 小时
CACHE_TTL = 1800  # 30 分钟


def _history_key(session_id: str) -> str:
    return f"session:{session_id}:history"


def _cache_key(question: str) -> str:
    h = hashlib.md5(question.strip().lower().encode()).hexdigest()
    return f"cache:answer:{h}"


async def get_history(session_id: str) -> list[dict]:
    """获取对话历史，返回 [{role, content}, ...]。"""
    try:
        r = await get_redis()
        raw = await r.lrange(_history_key(session_id), 0, -1)
        return [json.loads(item) for item in raw]
    except Exception:
        logger.warning("Redis 不可用，跳过对话历史读取")
        return []


async def append_history(
    session_id: str, question: str, answer: str
) -> None:
    """追加一轮对话并裁剪到最近 N 条。"""
    try:
        r = await get_redis()
        key = _history_key(session_id)
        pipe = r.pipeline()
        pipe.rpush(key, json.dumps({"role": "user", "content": question}))
        pipe.rpush(key, json.dumps({"role": "assistant", "content": answer}))
        pipe.ltrim(key, -HISTORY_MAX_MESSAGES, -1)
        pipe.expire(key, HISTORY_TTL)
        await pipe.execute()
    except Exception:
        logger.warning("Redis 不可用，跳过对话历史写入")


async def get_cached_answer(question: str) -> str | None:
    """查询缓存，命中返回答案字符串，未命中返回 None。"""
    try:
        r = await get_redis()
        return await r.get(_cache_key(question))
    except Exception:
        logger.warning("Redis 不可用，跳过缓存读取")
        return None


async def set_cached_answer(question: str, answer: str) -> None:
    """缓存答案。"""
    try:
        r = await get_redis()
        await r.set(_cache_key(question), answer, ex=CACHE_TTL)
    except Exception:
        logger.warning("Redis 不可用，跳过缓存写入")

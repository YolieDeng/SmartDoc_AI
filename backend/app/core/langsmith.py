import os

from app.core.config import get_settings


def setup_langsmith() -> None:
    """根据配置设置 LangSmith 环境变量，启用 tracing。"""
    settings = get_settings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        os.environ.pop("LANGSMITH_TRACING", None)
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

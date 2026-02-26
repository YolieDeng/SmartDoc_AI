from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    zhipuai_api_key: str
    supabase_url: str
    supabase_key: str

    # 向量化批次大小
    embedding_batch_size: int = 64

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

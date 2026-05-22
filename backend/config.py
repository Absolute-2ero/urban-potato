from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    # 数据库
    postgres_dsn: str = "postgresql://dietsearch:dev_password@localhost:5432/dietsearch"
    sqlite_path: str = "data/food_db.sqlite"

    # 缓存
    redis_url: str = "redis://localhost:6379/0"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    es_index_name: str = "restaurants"

    # LLM（DeepSeek，兼容 OpenAI SDK）
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    # 别名（food_service 用此字段）
    deepseek_api_key: str = ""

    # 高德地图
    gaode_api_key: str = ""

    # Session
    session_secret: str = "dev-secret-change-in-production-please"
    session_max_age: int = 14 * 24 * 3600   # 14 天

    # CORS（逗号分隔的 Origin 列表）
    cors_origins_str: str = "http://localhost:5173,http://localhost:3000"

    # IR
    ranking_config_path: str = "config/ranking.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]


@lru_cache
def get_config() -> Config:
    return Config()


cfg = get_config()

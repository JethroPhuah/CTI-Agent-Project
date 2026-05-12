"""Centralized config. Pulls from environment with safe defaults."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (vLLM serving Qwen3 via OpenAI-compatible API)
    llm_base_url: str = Field(default="http://localhost:8000/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="EMPTY", alias="LLM_API_KEY")
    llm_model: str = Field(default="Qwen/Qwen3-30B-A3B-FP8", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_timeout: int = Field(default=480, alias="LLM_TIMEOUT")

    # Embeddings
    embedding_model: str = Field(
        default="sentence-transformers/multi-qa-mpnet-base-dot-v1",
        alias="EMBEDDING_MODEL",
    )
    embedding_dim: int = Field(default=768, alias="EMBEDDING_DIM")

    # Milvus
    milvus_host: str = Field(default="localhost", alias="MILVUS_HOST")
    milvus_port: int = Field(default=19530, alias="MILVUS_PORT")
    milvus_collection: str = Field(default="cti_reports", alias="MILVUS_COLLECTION")

    # Elasticsearch
    elasticsearch_host: str = Field(default="localhost", alias="ELASTICSEARCH_HOST")
    elasticsearch_port: int = Field(default=9200, alias="ELASTICSEARCH_PORT")
    elasticsearch_index: str = Field(default="cti_reports", alias="ELASTICSEARCH_INDEX")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="cti_password_123", alias="NEO4J_PASSWORD")

    # Postgres
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="cti", alias="POSTGRES_USER")
    postgres_password: str = Field(default="cti_password_123", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="cti", alias="POSTGRES_DB")

    # External enrichment APIs (optional)
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    virustotal_api_key: str = Field(default="", alias="VIRUSTOTAL_API_KEY")
    abuseipdb_api_key: str = Field(default="", alias="ABUSEIPDB_API_KEY")
    recordedfuture_api_key: str = Field(default="", alias="RECORDEDFUTURE_API_KEY")

    # MCP server URLs (used by agent backend)
    retrieval_mcp_url: str = Field(
        default="http://localhost:8101/sse", alias="RETRIEVAL_MCP_URL"
    )
    search_mcp_url: str = Field(
        default="http://localhost:8102/sse", alias="SEARCH_MCP_URL"
    )
    enrichment_mcp_url: str = Field(
        default="http://localhost:8103/sse", alias="ENRICHMENT_MCP_URL"
    )

    # RSS
    rss_feeds: str = Field(
        default="https://feeds.feedburner.com/TheHackersNews,https://www.bleepingcomputer.com/feed/,https://krebsonsecurity.com/feed/",
        alias="RSS_FEEDS",
    )

    # Agent
    max_validation_retries: int = Field(default=2, alias="MAX_VALIDATION_RETRIES")

    @property
    def rss_feed_list(self) -> List[str]:
        return [u.strip() for u in self.rss_feeds.split(",") if u.strip()]

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

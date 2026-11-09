from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # HubSpot
    HUBSPOT_ACCESS_TOKEN: str = ""

    # LLM & Embeddings
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Neo4j Graph DB
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password123"

    # Qdrant Vector DB
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "dealcraft_deal_intel"

    # Redis Working Memory
    REDIS_URL: str = "redis://localhost:6379/0"

    # Raw Data Lake
    RAW_DATA_LAKE_PATH: str = "./data/raw"

    @property
    def raw_lake_dir(self) -> Path:
        p = Path(self.RAW_DATA_LAKE_PATH)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

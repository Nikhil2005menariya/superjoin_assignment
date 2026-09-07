from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    max_upload_size_mb: int = 200
    log_level: str = "INFO"
    data_dir: str = "/app/data"
    uploads_dir: str = "/app/uploads"
    db_path: str = "/app/data/knowledge.db"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

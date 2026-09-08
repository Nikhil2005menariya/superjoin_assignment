from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM provider: "groq" or "bedrock"
    llm_provider: str = "groq"
    # Groq (3-key rotation)
    groq_api_key: str = ""
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    max_upload_size_mb: int = 200
    log_level: str = "INFO"
    data_dir: str = "/app/data"
    pages_dir: str = "/app/data/pages"
    uploads_dir: str = "/app/uploads"
    db_path: str = "/app/data/knowledge.db"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

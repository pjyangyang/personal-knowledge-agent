from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/knowledge.db"
    storage_dir: Path = Path("data/uploads")
    qdrant_path: Path = Path("data/qdrant")
    model_cache_dir: Path = Path("data/models")
    max_upload_size_mb: int = 100
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512
    vector_collection: str = "document_chunks"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    ocr_enabled: bool = True
    ocr_languages: str = "chi_sim+eng"
    ocr_dpi: int = 200

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.qdrant_path.mkdir(parents=True, exist_ok=True)
settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)

# PyMuPDF discovers Tesseract's language data through TESSDATA_PREFIX on Windows.
if "TESSDATA_PREFIX" not in os.environ and os.environ.get("CONDA_PREFIX"):
    tessdata = Path(os.environ["CONDA_PREFIX"]) / "share" / "tessdata"
    if tessdata.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata)

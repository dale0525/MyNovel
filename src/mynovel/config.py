from pathlib import Path

from pydantic import BaseModel


class AppConfig(BaseModel):
    data_dir: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str

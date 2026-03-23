from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_vlm_model: str = "llava"
    ollama_llm_model: str = "llama3.2"

    pexels_api_key: str = ""

    jobs_dir: Path = Path("./jobs")
    music_dir: Path = Path("./music")
    upload_max_size_mb: int = 500

    keyframe_interval_sec: float = 2.0
    whisper_model_size: str = "base"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def ensure_dirs(self) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

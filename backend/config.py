import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout_turno: float
    max_rondas: int
    n_mensajes: int


def load_settings() -> Settings:
    return Settings(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        timeout_turno=float(os.getenv("TIMEOUT_TURNO", "30")),
        max_rondas=int(os.getenv("MAX_RONDAS", "3")),
        n_mensajes=int(os.getenv("N_MENSAJES", "4")),
    )

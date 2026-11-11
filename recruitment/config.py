"""Configuração centralizada; nunca registrar a chave ou os relatos em logs."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_path: Path
    demo_mode: bool
    api_key: str
    text_model: str
    transcription_model: str
    retention_days: int
    controller: str
    privacy_contact: str


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    retention = int(os.getenv("DATA_RETENTION_DAYS", "30"))
    if retention < 1:
        raise ValueError("DATA_RETENTION_DAYS deve ser um inteiro maior que zero.")
    path = Path(os.getenv("DATABASE_PATH", "data/interviews.db"))
    return Settings(
        database_path=path if path.is_absolute() else ROOT / path,
        demo_mode=os.getenv("DEMO_MODE", "true").lower() in {"true", "1", "yes"},
        api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        text_model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
        transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-transcribe"),
        retention_days=retention,
        controller=os.getenv("DATA_CONTROLLER", "Organização responsável pelo teste local"),
        privacy_contact=os.getenv("PRIVACY_CONTACT", "responsavel@example.com"),
    )

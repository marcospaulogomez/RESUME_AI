"""Contrato de entrada compartilhável pelo Streamlit e futuros adaptadores.

Um adaptador futuro do WhatsApp converterá mensagens para Answer e chamará o
mesmo InterviewService. Identidade, webhooks e mídia ficam no adaptador.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Answer:
    turn_id: int  # Identifica a pergunta esperada e impede resposta duplicada.
    text: str
    source: str = "text"
    transcript: str | None = None
    audio_seconds: float | None = None

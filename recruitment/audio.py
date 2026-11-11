"""Validação local de WAV, sem FFmpeg ou dependências de áudio nativas."""

import io
import wave

MAX_AUDIO_SECONDS = 240
MAX_AUDIO_BYTES = 10 * 1024 * 1024


def validate_wav(data: bytes) -> float:
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Envie uma gravação WAV de até 10 MB e 4 minutos.")
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            if (not frames or not rate or audio.getnchannels() not in {1, 2}
                    or audio.getsampwidth() not in {1, 2, 3, 4}):
                raise ValueError("A gravação está vazia ou tem formato inválido.")
            duration = frames / rate
            if duration > MAX_AUDIO_SECONDS:
                raise ValueError("O áudio ultrapassa 4 minutos. Grave uma resposta mais curta.")
            expected = frames * audio.getnchannels() * audio.getsampwidth()
            if len(audio.readframes(frames)) != expected:
                raise ValueError("O áudio está incompleto. Grave novamente.")
            return duration
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("Não foi possível ler o WAV. Grave novamente pelo microfone.") from exc

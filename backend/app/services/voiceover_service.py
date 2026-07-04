import requests
from typing import Any

from app.config import settings
from app.utils.http import compact_error_text
from app.utils.logging import get_logger

logger = get_logger(__name__)
ELEVENLABS_TTS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

VOICE_MAP = {
    "bella": "XJa38TJgDqYhj5mYbSJA",
    "hank": "6F5Zhi321D3Oq7v1oNT4",
    "male": "EXAVITQu4vr4xnSDxMaL",
    "female": "21m00Tcm4TlvDq8ikWAM",
}
MAX_TTS_CHARACTERS = 1800


def _resolve_voice_id(voice: str) -> str:
    return VOICE_MAP.get(voice.lower(), voice)


def _build_headers() -> dict[str, str]:
    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured. Add it to backend/.env to enable voiceover.")
    return {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }


def _build_payload(text: str) -> dict[str, Any]:
    return {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
        },
    }


def _prepare_narration_text(text: str) -> str:
    clean_text = " ".join(text.strip().split())
    if not clean_text:
        raise RuntimeError("Voiceover text cannot be empty.")
    if len(clean_text) > MAX_TTS_CHARACTERS:
        logger.info("Trimming voiceover text from %s to %s characters", len(clean_text), MAX_TTS_CHARACTERS)
        return clean_text[:MAX_TTS_CHARACTERS].rsplit(" ", 1)[0].strip()
    return clean_text


def generate_voiceover(text: str, voice: str = "bella", language: str = "English") -> bytes:
    clean_text = _prepare_narration_text(text)

    voice_id = _resolve_voice_id(voice)
    url = ELEVENLABS_TTS_URL_TEMPLATE.format(voice_id=voice_id)
    logger.info("Generating ElevenLabs voiceover for %s characters in %s", len(clean_text), language)

    try:
        response = requests.post(
            url,
            json=_build_payload(clean_text),
            headers=_build_headers(),
            timeout=settings.elevenlabs_request_timeout_seconds,
        )
    except requests.Timeout as exc:
        logger.warning("ElevenLabs request timed out for language %s", language)
        raise RuntimeError("Voiceover generation timed out. Please retry later.") from exc
    except requests.RequestException as exc:
        logger.warning("ElevenLabs network error: %s", exc.__class__.__name__)
        raise RuntimeError("Voiceover network error. Check internet/API access.") from exc
    
    if response.status_code != 200:
        logger.warning("ElevenLabs API error: %s", compact_error_text(response))
        raise RuntimeError(f"Voiceover generation failed: HTTP {response.status_code}")

    return response.content

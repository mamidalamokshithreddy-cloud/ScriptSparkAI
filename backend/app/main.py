# === FILE: backend/app/main.py ===
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models.prompt import StoryPrompt
from app.models.media import VoiceoverRequest
from app.services.poster_generator import generate_poster
from app.services.story_generator import generate_story
from app.services.voiceover_service import generate_voiceover
from app.utils.logging import configure_logging, get_logger
from app.utils.tracing import RequestTracingMiddleware

configure_logging()
logger = get_logger(__name__)

API_PREFIX = "/api"
SERVICE_NAME = "scriptspark-api"
STREAM_AUDIO_MEDIA_TYPE = "audio/mpeg"
STREAM_CHUNK_SIZE = 64 * 1024


app = FastAPI(
    title="ScriptSpark API",
    description="Story generation, poster creation, and voiceover with multi-language support.",
    version="1.0.0",
)

app.add_middleware(RequestTracingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _service_unavailable(exc: RuntimeError) -> HTTPException:
    logger.warning("Request failed: %s", exc)
    return HTTPException(status_code=503, detail=str(exc))


def _stream_bytes(data: bytes, chunk_size: int = STREAM_CHUNK_SIZE):
    for index in range(0, len(data), chunk_size):
        yield data[index : index + chunk_size]


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}

@app.get("/api/story/status")
async def story_status() -> dict[str, Any]:
    return {
        "ai_generation_enabled": settings.ENABLE_AI_GENERATION,
        "gemini_model": settings.GEMINI_MODEL,
        "google_api_key_configured": bool(settings.GOOGLE_API_KEY),
        "local_fallback_enabled": settings.ENABLE_LOCAL_STORY_FALLBACK,
        "rag_enabled": settings.ENABLE_RAG,
        "response_cache_enabled": settings.ENABLE_RESPONSE_CACHE,
        "response_cache_ttl_seconds": settings.RESPONSE_CACHE_TTL_SECONDS,
        "rag_cache_ttl_seconds": settings.RAG_CACHE_TTL_SECONDS,
        "gemini_retry_attempts": settings.GEMINI_RETRY_ATTEMPTS,
        "gemini_timeout_seconds": settings.GEMINI_REQUEST_TIMEOUT_SECONDS,
    }

@app.post("/api/story/generate")
async def story_generation(prompt: StoryPrompt) -> dict[str, Any]:
    try:
        return generate_story(prompt)
    except RuntimeError as exc:
        raise _service_unavailable(exc) from exc

@app.post("/api/story/poster")
async def poster_api(data: dict[str, Any]) -> dict[str, Any]:
    return generate_poster(
        text=data.get("text", ""),
        language=data.get("language", "en"),
    )

@app.post("/api/story/voiceover")
async def voiceover_endpoint(data: VoiceoverRequest) -> StreamingResponse:
    try:
        audio_bytes = generate_voiceover(data.text, data.voice, data.language)
        return StreamingResponse(_stream_bytes(audio_bytes), media_type=STREAM_AUDIO_MEDIA_TYPE)
    except RuntimeError as exc:
        raise _service_unavailable(exc) from exc

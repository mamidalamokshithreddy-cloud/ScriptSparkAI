import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

TRUE_VALUES = {"1", "true", "yes", "on"}
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173,"
    "https://script-spark-4sn7oisgr-mokshith2.vercel.app"
)


def _get_optional_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _get_bool(name: str, default: bool = False) -> bool:
    raw_default = "true" if default else "false"
    return os.getenv(name, raw_default).strip().lower() in TRUE_VALUES


def _get_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return max(minimum, int(raw_value))
    except ValueError:
        return default


def _get_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return max(minimum, float(raw_value))
    except ValueError:
        return default


def _get_csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    google_api_key: Optional[str]
    elevenlabs_api_key: Optional[str]
    midjourney_api_key: Optional[str]
    gemini_model: str
    enable_ai_generation: bool
    enable_rag: bool
    enable_local_story_fallback: bool
    gemini_quota_cooldown_seconds: int
    gemini_request_timeout_seconds: int
    gemini_max_output_tokens: int
    gemini_retry_attempts: int
    gemini_retry_backoff_seconds: float
    enable_response_cache: bool
    response_cache_ttl_seconds: int
    rag_cache_ttl_seconds: int
    elevenlabs_request_timeout_seconds: int
    allowed_origins: list[str]
    vectorstore_path: str
    vectorstore_docs_path: str
    rag_embedding_model: str
    rag_candidate_k: int
    rag_top_k: int
    rag_min_similarity: float
    rag_max_context_chars: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            google_api_key=_get_optional_str("GOOGLE_API_KEY"),
            elevenlabs_api_key=_get_optional_str("ELEVENLABS_API_KEY"),
            midjourney_api_key=_get_optional_str("MIDJOURNEY_API_KEY"),
            gemini_model=_get_str("GEMINI_MODEL", "gemini-2.5-flash"),
            enable_ai_generation=_get_bool("ENABLE_AI_GENERATION", False),
            enable_rag=_get_bool("ENABLE_RAG", False),
            enable_local_story_fallback=_get_bool("ENABLE_LOCAL_STORY_FALLBACK", True),
            gemini_quota_cooldown_seconds=_get_int("GEMINI_QUOTA_COOLDOWN_SECONDS", 300),
            gemini_request_timeout_seconds=_get_int("GEMINI_REQUEST_TIMEOUT_SECONDS", 45),
            gemini_max_output_tokens=_get_int("GEMINI_MAX_OUTPUT_TOKENS", 8192, minimum=2048),
            gemini_retry_attempts=_get_int("GEMINI_RETRY_ATTEMPTS", 2),
            gemini_retry_backoff_seconds=_get_float("GEMINI_RETRY_BACKOFF_SECONDS", 0.8),
            enable_response_cache=_get_bool("ENABLE_RESPONSE_CACHE", True),
            response_cache_ttl_seconds=_get_int("RESPONSE_CACHE_TTL_SECONDS", 900),
            rag_cache_ttl_seconds=_get_int("RAG_CACHE_TTL_SECONDS", 1800),
            elevenlabs_request_timeout_seconds=_get_int("ELEVENLABS_REQUEST_TIMEOUT_SECONDS", 60),
            allowed_origins=_get_csv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
            vectorstore_path=_get_str("VECTORSTORE_PATH", "data/telangana_facts/index.faiss"),
            vectorstore_docs_path=_get_str("VECTORSTORE_DOCS_PATH", "data/telangana_facts/docs.json"),
            rag_embedding_model=_get_str("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            rag_candidate_k=_get_int("RAG_CANDIDATE_K", 20),
            rag_top_k=_get_int("RAG_TOP_K", 5),
            rag_min_similarity=float(_get_str("RAG_MIN_SIMILARITY", "0.15")),
            rag_max_context_chars=_get_int("RAG_MAX_CONTEXT_CHARS", 4000, minimum=500),
            log_level=_get_str("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def GOOGLE_API_KEY(self) -> Optional[str]:
        return self.google_api_key

    @property
    def ELEVENLABS_API_KEY(self) -> Optional[str]:
        return self.elevenlabs_api_key

    @property
    def MIDJOURNEY_API_KEY(self) -> Optional[str]:
        return self.midjourney_api_key

    @property
    def GEMINI_MODEL(self) -> str:
        return self.gemini_model

    @property
    def ENABLE_AI_GENERATION(self) -> bool:
        return self.enable_ai_generation

    @property
    def ENABLE_RAG(self) -> bool:
        return self.enable_rag

    @property
    def ENABLE_LOCAL_STORY_FALLBACK(self) -> bool:
        return self.enable_local_story_fallback

    @property
    def GEMINI_QUOTA_COOLDOWN_SECONDS(self) -> int:
        return self.gemini_quota_cooldown_seconds

    @property
    def GEMINI_REQUEST_TIMEOUT_SECONDS(self) -> int:
        return self.gemini_request_timeout_seconds

    @property
    def GEMINI_MAX_OUTPUT_TOKENS(self) -> int:
        return self.gemini_max_output_tokens

    @property
    def GEMINI_RETRY_ATTEMPTS(self) -> int:
        return self.gemini_retry_attempts

    @property
    def GEMINI_RETRY_BACKOFF_SECONDS(self) -> float:
        return self.gemini_retry_backoff_seconds

    @property
    def ENABLE_RESPONSE_CACHE(self) -> bool:
        return self.enable_response_cache

    @property
    def RESPONSE_CACHE_TTL_SECONDS(self) -> int:
        return self.response_cache_ttl_seconds

    @property
    def RAG_CACHE_TTL_SECONDS(self) -> int:
        return self.rag_cache_ttl_seconds

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        return self.allowed_origins

    @property
    def VECTORSTORE_PATH(self) -> str:
        return self.vectorstore_path

    @property
    def VECTORSTORE_DOCS_PATH(self) -> str:
        return self.vectorstore_docs_path

    @property
    def RAG_EMBEDDING_MODEL(self) -> str:
        return self.rag_embedding_model

    @property
    def RAG_CANDIDATE_K(self) -> int:
        return self.rag_candidate_k

    @property
    def RAG_TOP_K(self) -> int:
        return self.rag_top_k

    @property
    def RAG_MIN_SIMILARITY(self) -> float:
        return self.rag_min_similarity

    @property
    def RAG_MAX_CONTEXT_CHARS(self) -> int:
        return self.rag_max_context_chars


settings = Settings.from_env()

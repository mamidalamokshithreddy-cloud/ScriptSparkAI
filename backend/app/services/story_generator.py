# === FILE: backend/app/services/story_generator.py ===
import hashlib
import importlib
import json
import os
import time
from functools import lru_cache
from typing import Any, Callable, Optional, TypeVar

import requests

from app.models.prompt import StoryPrompt
from app.services.rag_service import build_structured_context, retrieve_ranked_context
from app.utils.formatter import format_story
from app.config import settings
from app.utils.cache import TTLCache
from app.utils.http import parse_json_response
from app.utils.logging import get_logger
from app.utils.tracing import current_request_id

logger = get_logger(__name__)
_quota_blocked_until = 0.0
_http_session = requests.Session()
_story_response_cache: TTLCache[str, dict[str, Any]] = TTLCache(
    ttl_seconds=settings.RESPONSE_CACHE_TTL_SECONDS,
    max_size=64,
)
GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_THEMES = "character, conflict, transformation"
FALLBACK_THEMES = "hope, conflict, transformation"
SCREENPLAY_STYLE_REFERENCES = "Chai Bisket intimacy, Aha Originals emotional clarity, Netflix short-film visual discipline"
GENERATION_MODE = "single_llm_film_preproduction_package"
UI_SCHEMA = "phase09"
SCENE_FIELD_NAMES = [
    "location",
    "time",
    "characters",
    "visual_description",
    "character_action",
    "dialogue",
    "emotional_shift",
    "camera_suggestion",
    "lighting",
    "background_music",
    "color_palette",
    "shot_list",
    "production_note",
]
VOICEOVER_MAX_WORDS = 140
TRANSIENT_STATUS_CODES = {408, 500, 502, 503, 504}
GEMINI_REQUIRED_ENV_VARS = [
    "GOOGLE_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_REQUEST_TIMEOUT_SECONDS",
    "GEMINI_MAX_OUTPUT_TOKENS",
    "GEMINI_RETRY_ATTEMPTS",
    "GEMINI_RETRY_BACKOFF_SECONDS",
]
T = TypeVar("T")


def _raw_response_body(response: requests.Response, limit: int = 4000) -> str:
    return response.text[:limit]


def _log_gemini_response(response: requests.Response, attempt: int) -> None:
    logger.info(
        "request_id=%s Gemini HTTP response attempt=%s status=%s headers=%s raw_body=%s",
        current_request_id(),
        attempt,
        response.status_code,
        dict(response.headers),
        _raw_response_body(response),
    )


class StoryGenerationServiceError(RuntimeError):
    def __init__(self, message: str, request_id: Optional[str] = None, dependency: Optional[str] = None) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.dependency = dependency

    def to_detail(self) -> dict[str, Any]:
        return {
            "error": "story_generation_unavailable",
            "message": str(self),
            "request_id": self.request_id,
            "dependency": self.dependency,
        }


def _run_generation_step(step_name: str, dependency: str, action: Callable[[], T]) -> T:
    request_id = current_request_id()
    logger.info("request_id=%s generate_story step=%s status=start", request_id, step_name)
    try:
        result = action()
    except StoryGenerationServiceError:
        logger.exception("request_id=%s generate_story step=%s dependency=%s status=failed", request_id, step_name, dependency)
        raise
    except Exception as exc:
        logger.exception("request_id=%s generate_story step=%s dependency=%s status=failed", request_id, step_name, dependency)
        raise StoryGenerationServiceError(
            f"{exc.__class__.__name__}: {exc}",
            request_id=request_id,
            dependency=dependency,
        ) from exc
    logger.info("request_id=%s generate_story step=%s status=complete", request_id, step_name)
    return result


def _validate_generation_settings() -> None:
    dependency_modules = [
        "app.services.rag_service",
        "app.utils.http",
        "app.utils.cache",
        "app.utils.formatter",
        "requests",
    ]
    for module_name in dependency_modules:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            logger.exception(
                "request_id=%s dependency import verification failed module=%s",
                current_request_id(),
                module_name,
            )
            raise StoryGenerationServiceError(
                f"Story generation dependency could not be imported: {module_name}",
                request_id=current_request_id(),
                dependency=module_name,
            ) from exc
    logger.info(
        "request_id=%s dependency import verification complete modules=%s gemini_client=requests.Session",
        current_request_id(),
        dependency_modules,
    )

    if not settings.ENABLE_AI_GENERATION:
        return

    missing_env_vars = [name for name in GEMINI_REQUIRED_ENV_VARS if not os.getenv(name)]
    invalid_settings: list[str] = []
    if not settings.GOOGLE_API_KEY:
        invalid_settings.append("GOOGLE_API_KEY")
    if not settings.GEMINI_MODEL:
        invalid_settings.append("GEMINI_MODEL")
    if settings.GEMINI_REQUEST_TIMEOUT_SECONDS <= 0:
        invalid_settings.append("GEMINI_REQUEST_TIMEOUT_SECONDS")
    if settings.GEMINI_MAX_OUTPUT_TOKENS <= 0:
        invalid_settings.append("GEMINI_MAX_OUTPUT_TOKENS")
    if settings.GEMINI_RETRY_ATTEMPTS <= 0:
        invalid_settings.append("GEMINI_RETRY_ATTEMPTS")
    if settings.GEMINI_RETRY_BACKOFF_SECONDS < 0:
        invalid_settings.append("GEMINI_RETRY_BACKOFF_SECONDS")

    if missing_env_vars or invalid_settings:
        logger.error(
            "request_id=%s Gemini settings validation failed missing_env_vars=%s invalid_settings=%s",
            current_request_id(),
            missing_env_vars,
            invalid_settings,
        )
        raise StoryGenerationServiceError(
            "Gemini configuration is incomplete.",
            request_id=current_request_id(),
            dependency="Gemini client",
        )


def _local_story_fallback(prompt: StoryPrompt, reason: str) -> dict[str, Any]:
    themes = ", ".join(prompt.themes or []) or FALLBACK_THEMES
    genre = prompt.genre or "Drama"
    language = prompt.language or "English"
    seed = prompt.prompt.strip() or "A creator searches for a powerful story idea."

    return {
        "title": f"Local Draft ({genre})",
        "genre": genre,
        "language": language,
        "logline": f"A grounded short film about how one personal memory keeps {themes} alive.",
        "summary": (
            f"Inspired by '{seed}', this local draft follows a storyteller who turns a forgotten memory "
            "into a shared emotional responsibility across three intimate scenes."
        ),
        "characters": [
            {
                "name": "The Storyteller",
                "role": "A young person trying to preserve a memory before it disappears.",
                "arc": "Moves from curiosity to responsibility.",
            },
            {
                "name": "The Elder",
                "role": "A family voice who tests whether the story is being handled truthfully.",
                "arc": "Moves from caution to quiet trust.",
            },
        ],
        "character_profiles": [
            {
                "name": "The Storyteller",
                "age_range": "20s",
                "motivation": "Protect a fading memory from becoming decoration.",
                "conflict": "Unsure whether they are honoring the truth or performing it.",
                "visual_identity": "Simple cotton clothes, notebook, observant eyes.",
            },
            {
                "name": "The Elder",
                "age_range": "60s",
                "motivation": "Keep painful memories from being flattened into slogans.",
                "conflict": "Wants remembrance, but fears careless storytelling.",
                "visual_identity": "Weathered hands, old photographs, restrained expressions.",
            },
        ],
        "themes": prompt.themes or [theme.strip() for theme in FALLBACK_THEMES.split(",")],
        "tone": "Intimate, rooted, hopeful, emotionally restrained",
        "target_audience": "Telugu short-film audiences, young creators, family drama viewers",
        "estimated_runtime": f"{prompt.length_minutes or 5} minutes",
        "scene_count": 3,
        "scenes": [
            {
                "scene_number": 1,
                "location": "A narrow old-town lane outside a small tea stall",
                "time": "Early morning, just before the first bus arrives",
                "characters": ["A determined young storyteller", "A tea stall owner", "Two curious neighbors"],
                "visual_description": (
                    f"Steam rises from steel tumblers as the village slowly wakes. A faded wall poster hints at {themes}, "
                    "and the air carries the feeling that an ordinary day is about to become personal."
                ),
                "character_action": (
                    f"The storyteller unfolds a notebook and reads the first line inspired by: {seed}"
                ),
                "dialogue": '"If we forget this story today, tomorrow it will forget us."',
                "emotional_shift": "Private curiosity turns into shared attention.",
                "camera_suggestion": "Begin on a close-up of boiling chai, then slowly push toward the open notebook.",
                "lighting": "Soft amber sunrise mixed with tea-stall firelight.",
                "background_music": "Low flute phrase over natural street ambience.",
                "color_palette": ["chai brown", "sunrise gold", "faded poster red"],
                "shot_list": ["Close-up of boiling chai", "Push-in toward notebook", "Reaction shots around the stall"],
                "production_note": "Use real street ambience and minimal extras to keep the moment intimate.",
                "description": (
                    "A narrow old-town lane outside a small tea stall, early morning.\n\n"
                    f"Steam rises from steel tumblers as a young storyteller opens a notebook inspired by: {seed}\n\n"
                    '"If we forget this story today, tomorrow it will forget us."\n\n'
                    "Curiosity around the stall turns into shared attention."
                ),
            },
            {
                "scene_number": 2,
                "location": "A family courtyard with drying clothes and festival lights",
                "time": "Late afternoon",
                "characters": ["The storyteller", "An elder relative", "A quiet child"],
                "visual_description": "Warm sunlight cuts across the courtyard while old photographs sit on a plastic chair.",
                "character_action": "The elder challenges the storyteller to separate memory from pride, and truth from performance.",
                "dialogue": '"A story is not alive because it is loud. It is alive because someone carries it carefully."',
                "emotional_shift": "Confidence becomes responsibility.",
                "camera_suggestion": "Hold a steady two-shot, then cut to the child's silent reaction.",
                "lighting": "Late-afternoon side light with warm shadows.",
                "background_music": "Sparse strings with distant household sounds.",
                "color_palette": ["courtyard cream", "turmeric yellow", "photo sepia"],
                "shot_list": ["Static two-shot", "Insert of old photograph", "Cutaway to child listening"],
                "production_note": "Let silence hold after the elder's line before cutting away.",
                "description": (
                    "A family courtyard in late afternoon.\n\n"
                    "An elder challenges the storyteller to separate memory from pride, and truth from performance.\n\n"
                    '"A story is not alive because it is loud. It is alive because someone carries it carefully."\n\n'
                    "Confidence becomes responsibility."
                ),
            },
            {
                "scene_number": 3,
                "location": "An open-air community stage",
                "time": "Night, under tube lights and phone flashlights",
                "characters": ["The storyteller", "The child", "The gathered community"],
                "visual_description": "Faces glow in the half-light as the final words land without music or decoration.",
                "character_action": "The storyteller stops performing and simply speaks the truth of the memory.",
                "dialogue": '"This is not my ending. This is where we begin remembering."',
                "emotional_shift": "A personal mission becomes a communal promise.",
                "camera_suggestion": "End on a wide shot as phone lights rise one by one across the crowd.",
                "lighting": "Tube lights, phone flashlights, and soft stage spill.",
                "background_music": "Restrained percussion fading into crowd silence.",
                "color_palette": ["night blue", "tube-light white", "festival red"],
                "shot_list": ["Wide crowd frame", "Medium close-up on storyteller", "Final wide as phone lights rise"],
                "production_note": "Avoid melodrama; let the community reaction stay quiet and believable.",
                "description": (
                    "An open-air community stage at night.\n\n"
                    "The storyteller stops performing and speaks plainly to the gathered community.\n\n"
                    '"This is not my ending. This is where we begin remembering."\n\n'
                    "A personal mission becomes a communal promise as phone lights rise across the crowd."
                ),
            },
        ],
        "voiceover": {
            "style": "Warm, reflective, understated Telugu short-film narration",
            "sample": "Some stories do not ask for applause. They only ask to be remembered.",
            "narration_text": (
                "Some stories do not ask for applause. They wait quietly in tea stalls, courtyards, and old lanes. "
                "When one young voice chooses to remember, a private memory becomes a promise shared by everyone."
            ),
        },
        "screenplay": (
            "TITLE: Local Draft\n\n"
            "A grounded three-scene short film about memory, responsibility, and community remembrance."
        ),
        "scene_breakdown": [
            {"scene_number": 1, "purpose": "Hook the audience through a public place and a private memory."},
            {"scene_number": 2, "purpose": "Test the moral responsibility of telling the story."},
            {"scene_number": 3, "purpose": "Turn personal remembrance into a community promise."},
        ],
        "dialogues": [
            {"speaker": "The Storyteller", "line": "If we forget this story today, tomorrow it will forget us."},
            {"speaker": "The Elder", "line": "A story is alive because someone carries it carefully."},
        ],
        "shot_list": [
            "Close-up inserts of objects that hold memory",
            "Observational medium shots for family conflict",
            "Wide final frame showing community participation",
        ],
        "camera_suggestions": [
            "Use handheld intimacy for personal beats.",
            "Use slow push-ins only when a character realizes something.",
        ],
        "lighting_suggestions": [
            "Favor motivated practical light from tea stalls, homes, and stage fixtures.",
            "Keep the final scene textured instead of glossy.",
        ],
        "background_music_suggestions": [
            "Use sparse flute and muted percussion.",
            "Let ambient village sound carry emotional transitions.",
        ],
        "production_notes": [
            "Shoot with real locations where possible.",
            "Keep performance understated and dialogue conversational.",
            "Use props with visible age: notebooks, photographs, posters, steel tumblers.",
        ],
        "poster_prompt": (
            "A cinematic Telugu short-film poster: a young storyteller holding an old notebook near a tea stall, "
            "warm practical lights, emotional realism, festival colors in the distance."
        ),
        "background_music": "Soft flute, muted mridangam pulse, sparse strings, natural village ambience",
        "camera_style": "Handheld intimacy, slow push-ins, observational close-ups, natural light",
        "color_palette": ["warm amber", "dusty teal", "festival red", "soft tungsten"],
        "metadata": {
            "source": "local_fallback",
            "reason": reason,
            "ui_schema": UI_SCHEMA,
            "generation_mode": GENERATION_MODE,
            "request_id": current_request_id(),
            "cache": "bypass",
        },
    }


def _get_retry_after() -> Optional[int]:
    now = time.time()
    if now >= _quota_blocked_until:
        return None
    return int(_quota_blocked_until - now)


def _set_quota_cooldown() -> None:
    global _quota_blocked_until
    _quota_blocked_until = time.time() + settings.GEMINI_QUOTA_COOLDOWN_SECONDS


def _build_context(prompt: StoryPrompt) -> tuple[str, list[dict[str, Any]]]:
    if not prompt.use_real_world_context:
        return "", []
    context_docs = retrieve_ranked_context(prompt.prompt)
    return build_structured_context(context_docs), context_docs


def _scene_count(length_minutes: Optional[int]) -> int:
    return max(3, min(6, int(length_minutes or 5)))


def _themes_key(themes: Optional[list[str]]) -> str:
    return ", ".join(themes or [])


@lru_cache(maxsize=256)
def _build_writer_prompt_cached(
    prompt_text: str,
    genre: str,
    length_minutes: int,
    language: str,
    themes_key: str,
    context: str,
) -> str:
    themes = themes_key or DEFAULT_THEMES
    scene_count = _scene_count(length_minutes)
    return f"""
You are ScriptSpark, an AI Film Pre-Production Assistant and award-winning Telugu short-film writer.
Style target: {SCREENPLAY_STYLE_REFERENCES}.
Language: {language}. Genre: {genre}. Runtime: {length_minutes} minutes. Themes: {themes}. Scenes: exactly {scene_count}.
Idea: {prompt_text}

Rules:
- Return valid JSON only.
- Generate the full pre-production package in ONE response: story, logline, characters, profiles, scenes, dialogue, voiceover, poster, shot list, camera, lighting, music, palette, notes.
- Voiceover narration must be under {VOICEOVER_MAX_WORDS} words and ready for ElevenLabs.
- Keep scene text cinematic and specific; no placeholders, no "Opening/Middle/Ending", no explanations.
- If context is thin, write fiction and do not invent factual claims.
- Use context only for factual details.

Context:
{context or 'No retrieval context available.'}

Return only valid JSON with this exact shape:
{{
  "title": "A strong cinematic title",
  "genre": "{genre}",
  "language": "{language}",
  "logline": "One sentence hook for the short film",
  "summary": "A concise 3-5 sentence story summary",
  "characters": [
    {{
      "name": "Character name",
      "role": "Narrative role",
      "arc": "Emotional change across the film"
    }}
  ],
  "character_profiles": [
    {{
      "name": "Character name",
      "age_range": "Age range",
      "motivation": "What they want",
      "conflict": "What blocks them",
      "visual_identity": "Costume/props/body language"
    }}
  ],
  "themes": ["Theme"],
  "tone": "Precise tonal description",
  "target_audience": "Who this short film is for",
  "estimated_runtime": "{length_minutes} minutes",
  "scene_count": {scene_count},
  "scenes": [
    {{
      "scene_number": 1,
      "location": "Specific location, not generic",
      "time": "Specific time of day or moment",
      "characters": ["Character name or role"],
      "visual_description": "Concrete cinematic visual detail",
      "character_action": "Specific action that moves the story",
      "dialogue": "Natural screenplay dialogue with speaker names if needed",
      "emotional_shift": "What changes emotionally in this scene",
      "camera_suggestion": "One practical camera/framing suggestion",
      "lighting": "Specific lighting direction",
      "background_music": "Scene-specific music or ambience direction",
      "color_palette": ["Scene color", "Accent color"],
      "shot_list": ["Shot 1", "Shot 2"],
      "production_note": "Practical note for shooting this scene"
    }}
  ],
  "scene_breakdown": [
    {{"scene_number": 1, "purpose": "Narrative purpose", "conflict": "Scene conflict", "turning_point": "What changes"}}
  ],
  "dialogues": [
    {{"scene_number": 1, "speaker": "Character", "line": "Performable dialogue line"}}
  ],
  "voiceover": {{
    "style": "Narration style if voiceover is used",
    "sample": "One short sample voiceover line",
    "narration_text": "Final narration script for text-to-speech, under {VOICEOVER_MAX_WORDS} words"
  }},
  "screenplay": "Concise screenplay text with scene headings, action, and dialogue",
  "poster_prompt": "Detailed cinematic poster prompt for this exact story",
  "shot_list": ["Overall shot suggestion"],
  "camera_suggestions": ["Overall camera suggestion"],
  "lighting_suggestions": ["Overall lighting suggestion"],
  "background_music_suggestions": ["Overall music suggestion"],
  "production_notes": ["Practical production note"],
  "background_music": "Music direction and instrumentation",
  "camera_style": "Overall cinematography language",
  "color_palette": ["Primary color", "Secondary color", "Accent color"],
  "metadata": {{
    "format": "screenplay_treatment",
    "grounding_note": "How factual context was handled"
  }}
}}
"""


def _build_writer_prompt(prompt: StoryPrompt, context: str) -> str:
    return _build_writer_prompt_cached(
        prompt_text=prompt.prompt.strip(),
        genre=prompt.genre or "Drama",
        length_minutes=int(prompt.length_minutes or 5),
        language=prompt.language or "English",
        themes_key=_themes_key(prompt.themes),
        context=context,
    )


def _build_gemini_payload(writer_prompt: str) -> dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [{"text": writer_prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": settings.GEMINI_MAX_OUTPUT_TOKENS,
        },
    }


def _extract_gemini_text(data: dict[str, Any]) -> str:
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Unexpected Gemini response shape.") from exc
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned an empty story.")
    return text


def _infer_scene_lighting(scene: dict[str, Any]) -> str:
    time_value = str(scene.get("time") or "").lower()
    if "night" in time_value:
        return "Practical night lighting with festival bulbs, phone light, or household spill."
    if "morning" in time_value:
        return "Soft morning light with warm highlights and gentle natural shadows."
    if "afternoon" in time_value or "golden" in time_value:
        return "Warm golden-hour light with textured shadows and natural contrast."
    return "Naturalistic practical lighting shaped around the emotional beat."


def _complete_story_design_fields(story: dict[str, Any]) -> dict[str, Any]:
    overall_music = story.get("background_music") or "Restrained cinematic ambience rooted in the scene location."
    overall_palette = story.get("color_palette") or ["warm natural light", "earth tones", "festival accents"]
    completed_scenes: list[dict[str, Any]] = []
    derived_shots: list[str] = []
    derived_notes: list[str] = []
    for scene in story.get("scenes", []):
        if not isinstance(scene, dict):
            completed_scenes.append(scene)
            continue
        scene_copy = dict(scene)
        scene_copy["lighting"] = scene_copy.get("lighting") or _infer_scene_lighting(scene_copy)
        scene_copy["background_music"] = scene_copy.get("background_music") or overall_music
        scene_copy["color_palette"] = scene_copy.get("color_palette") or overall_palette
        if isinstance(scene_copy.get("shot_list"), list):
            derived_shots.extend(str(shot) for shot in scene_copy["shot_list"] if str(shot).strip())
        if scene_copy.get("production_note"):
            derived_notes.append(str(scene_copy["production_note"]))
        completed_scenes.append(scene_copy)
    story["scenes"] = completed_scenes
    story["background_music"] = overall_music
    story["color_palette"] = overall_palette
    story["shot_list"] = story.get("shot_list") or derived_shots
    story["production_notes"] = story.get("production_notes") or derived_notes
    story["camera_suggestions"] = story.get("camera_suggestions") or [
        scene.get("camera_suggestion") for scene in completed_scenes if isinstance(scene, dict) and scene.get("camera_suggestion")
    ]
    story["lighting_suggestions"] = story.get("lighting_suggestions") or [
        scene.get("lighting") for scene in completed_scenes if isinstance(scene, dict) and scene.get("lighting")
    ]
    story["background_music_suggestions"] = story.get("background_music_suggestions") or [
        scene.get("background_music") for scene in completed_scenes if isinstance(scene, dict) and scene.get("background_music")
    ]
    return story


def _story_cache_key(prompt: StoryPrompt, structured_context: str) -> str:
    payload = {
        "prompt": prompt.prompt.strip(),
        "genre": prompt.genre,
        "length_minutes": prompt.length_minutes,
        "language": prompt.language,
        "themes": prompt.themes,
        "use_real_world_context": prompt.use_real_world_context,
        "context_hash": hashlib.sha256(structured_context.encode("utf-8")).hexdigest(),
        "model": settings.GEMINI_MODEL,
        "schema": UI_SCHEMA,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sleep_before_retry(attempt: int) -> None:
    delay = settings.GEMINI_RETRY_BACKOFF_SECONDS * (2 ** max(0, attempt - 1))
    if delay > 0:
        time.sleep(delay)


def _call_gemini(writer_prompt: str) -> str:
    url = GEMINI_API_URL_TEMPLATE.format(model=settings.GEMINI_MODEL)
    payload = _build_gemini_payload(writer_prompt)
    last_error: Optional[requests.RequestException] = None

    for attempt in range(1, settings.GEMINI_RETRY_ATTEMPTS + 1):
        try:
            response = _http_session.post(
                url,
                params={"key": settings.GOOGLE_API_KEY},
                json=payload,
                timeout=settings.GEMINI_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            last_error = exc
            logger.warning(
                "request_id=%s Gemini timeout attempt=%s/%s timeout=%ss",
                current_request_id(),
                attempt,
                settings.GEMINI_RETRY_ATTEMPTS,
                settings.GEMINI_REQUEST_TIMEOUT_SECONDS,
            )
            if attempt < settings.GEMINI_RETRY_ATTEMPTS:
                _sleep_before_retry(attempt)
                continue
            raise StoryGenerationServiceError(
                f"Gemini request timed out after {settings.GEMINI_REQUEST_TIMEOUT_SECONDS} seconds.",
                request_id=current_request_id(),
                dependency="Gemini client",
            ) from exc
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "request_id=%s Gemini network error attempt=%s/%s type=%s",
                current_request_id(),
                attempt,
                settings.GEMINI_RETRY_ATTEMPTS,
                exc.__class__.__name__,
            )
            if attempt < settings.GEMINI_RETRY_ATTEMPTS:
                _sleep_before_retry(attempt)
                continue
            raise StoryGenerationServiceError(
                f"Gemini network error: {exc.__class__.__name__}: {exc}",
                request_id=current_request_id(),
                dependency="Gemini client",
            ) from exc

        _log_gemini_response(response, attempt)
        response_body = _raw_response_body(response)

        if response.status_code == 429:
            _set_quota_cooldown()
            logger.warning(
                "request_id=%s Gemini quota exhausted for model %s status=%s headers=%s raw_body=%s",
                current_request_id(),
                settings.GEMINI_MODEL,
                response.status_code,
                dict(response.headers),
                response_body,
            )
            raise StoryGenerationServiceError(
                f"Gemini quota exhausted. HTTP {response.status_code}. Response body: {response_body}",
                request_id=current_request_id(),
                dependency="Gemini client",
            )

        if response.status_code in TRANSIENT_STATUS_CODES and attempt < settings.GEMINI_RETRY_ATTEMPTS:
            logger.warning(
                "request_id=%s Gemini transient HTTP %s attempt=%s/%s headers=%s raw_body=%s",
                current_request_id(),
                response.status_code,
                attempt,
                settings.GEMINI_RETRY_ATTEMPTS,
                dict(response.headers),
                response_body,
            )
            _sleep_before_retry(attempt)
            continue

        if response.status_code >= 400:
            logger.warning(
                "request_id=%s Gemini API error for model %s status=%s headers=%s raw_body=%s",
                current_request_id(),
                settings.GEMINI_MODEL,
                response.status_code,
                dict(response.headers),
                response_body,
            )
            raise StoryGenerationServiceError(
                f"Gemini API error: HTTP {response.status_code}. Response body: {response_body}",
                request_id=current_request_id(),
                dependency="Gemini client",
            )

        try:
            parsed_response = parse_json_response(response, "Gemini")
            return _extract_gemini_text(parsed_response)
        except Exception as exc:
            logger.exception(
                "request_id=%s Gemini invalid response raw_body=%s",
                current_request_id(),
                response_body,
            )
            raise StoryGenerationServiceError(
                f"Gemini returned an invalid response. Response body: {response_body}",
                request_id=current_request_id(),
                dependency="Gemini client",
            ) from exc

    if last_error is not None:
        raise StoryGenerationServiceError(
            f"Gemini request failed after retries: {last_error.__class__.__name__}: {last_error}",
            request_id=current_request_id(),
            dependency="Gemini client",
        ) from last_error
    raise StoryGenerationServiceError(
        "Gemini request failed after retries.",
        request_id=current_request_id(),
        dependency="Gemini client",
    )


def _fallback_or_raise(prompt: StoryPrompt, reason: str) -> dict[str, Any]:
    if settings.ENABLE_LOCAL_STORY_FALLBACK:
        logger.warning("request_id=%s returning local fallback reason=%s", current_request_id(), reason)
        return _local_story_fallback(prompt, reason)
    raise RuntimeError(reason)


def generate_story(prompt: StoryPrompt) -> dict[str, Any]:
    request_id = current_request_id()
    logger.info(
        "request_id=%s generate_story step=Request received status=complete prompt_chars=%s genre=%s language=%s rag_requested=%s",
        request_id,
        len(prompt.prompt or ""),
        prompt.genre,
        prompt.language,
        prompt.use_real_world_context,
    )

    _run_generation_step("Validate settings", "settings/Gemini client", _validate_generation_settings)

    if not settings.ENABLE_AI_GENERATION:
        return _run_generation_step(
            "Return response",
            "local fallback",
            lambda: _local_story_fallback(
                prompt,
                "AI generation is disabled locally. Set ENABLE_AI_GENERATION=true after fixing Gemini quota/billing.",
            ),
        )

    retry_after = _run_generation_step("Check Gemini quota cooldown", "app.utils.cache", _get_retry_after)
    if retry_after is not None:
        return _run_generation_step(
            "Return response",
            "local fallback",
            lambda: _local_story_fallback(
                prompt,
                f"Gemini quota is cooling down. Retry AI generation in about {retry_after} seconds.",
            ),
        )

    structured_context, context_docs = _run_generation_step(
        "Build RAG context",
        "app.services.rag_service",
        lambda: _build_context(prompt),
    )
    cache_key = _run_generation_step(
        "Build cache key",
        "app.utils.cache",
        lambda: _story_cache_key(prompt, structured_context),
    )

    if settings.ENABLE_RESPONSE_CACHE:
        cached_story = _run_generation_step(
            "Read response cache",
            "app.utils.cache",
            lambda: _story_response_cache.get(cache_key),
        )
        if cached_story is not None:
            cached_copy = _run_generation_step(
                "Format story",
                "app.utils.formatter",
                lambda: json.loads(json.dumps(cached_story, ensure_ascii=False)),
            )
            cached_copy.setdefault("metadata", {})["cache"] = "hit"
            cached_copy["metadata"]["request_id"] = current_request_id()
            logger.info("request_id=%s story response cache hit", current_request_id())
            return _run_generation_step("Return response", "FastAPI response", lambda: cached_copy)

    writer_prompt = _run_generation_step(
        "Build prompt",
        "prompt builder",
        lambda: _build_writer_prompt(prompt, structured_context),
    )
    raw_story_text = _run_generation_step(
        "Call Gemini",
        "Gemini client",
        lambda: _call_gemini(writer_prompt),
    )

    logger.info("request_id=%s json.loads Gemini response status=start", current_request_id())
    try:
        parsed_story = json.loads(raw_story_text)
    except json.JSONDecodeError:
        logger.exception(
            "request_id=%s Gemini returned invalid JSON raw_response=%s",
            current_request_id(),
            raw_story_text[:4000],
        )
        return _run_generation_step(
            "Return response",
            "local fallback",
            lambda: _fallback_or_raise(prompt, "Gemini returned invalid JSON."),
        )
    except Exception as exc:
        logger.exception(
            "request_id=%s Gemini JSON parsing failed raw_response=%s",
            current_request_id(),
            raw_story_text[:4000],
        )
        raise StoryGenerationServiceError(
            "Gemini JSON parsing failed.",
            request_id=current_request_id(),
            dependency="json.loads",
        ) from exc
    logger.info("request_id=%s json.loads Gemini response status=complete", current_request_id())

    story_text = json.dumps(parsed_story, ensure_ascii=False)
    formatted_story = _run_generation_step(
        "Format story",
        "app.utils.formatter",
        lambda: format_story(
            story_text,
            prompt.language,
            metadata={
                "source": "gemini",
                "model": settings.GEMINI_MODEL,
                "ui_schema": UI_SCHEMA,
                "generation_mode": GENERATION_MODE,
                "request_id": current_request_id(),
                "cache": "miss",
                "rag": {
                    "enabled": bool(prompt.use_real_world_context and settings.ENABLE_RAG),
                    "chunks": context_docs,
                },
            },
        ),
    )
    completed_story = _run_generation_step(
        "Complete story design fields",
        "formatter",
        lambda: _complete_story_design_fields(formatted_story),
    )
    if settings.ENABLE_RESPONSE_CACHE:
        _run_generation_step(
            "Write response cache",
            "app.utils.cache",
            lambda: _story_response_cache.set(cache_key, completed_story),
        )
    return _run_generation_step("Return response", "FastAPI response", lambda: completed_story)

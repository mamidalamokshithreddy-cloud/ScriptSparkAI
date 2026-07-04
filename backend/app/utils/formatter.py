# app/utils/formatter.py
import json
import re
from typing import Any, Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)

TOP_LEVEL_DEFAULTS: dict[str, Any] = {
    "genre": "",
    "logline": "",
    "summary": "",
    "characters": [],
    "character_profiles": [],
    "themes": [],
    "tone": "",
    "target_audience": "",
    "estimated_runtime": "",
    "scene_count": 0,
    "voiceover": {},
    "screenplay": "",
    "scene_breakdown": [],
    "dialogues": [],
    "shot_list": [],
    "camera_suggestions": [],
    "lighting_suggestions": [],
    "background_music_suggestions": [],
    "production_notes": [],
    "poster_prompt": "",
    "background_music": "",
    "camera_style": "",
    "color_palette": [],
}


def _extract_json_block(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]

    return cleaned


def _loads_json(value: str) -> Any:
    parsed = json.loads(value)
    if isinstance(parsed, str):
        return json.loads(parsed)
    return parsed


def _parse_story_json(story_text: str) -> dict[str, Any]:
    candidates = [story_text.strip(), _extract_json_block(story_text)]
    seen: set[str] = set()

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = _loads_json(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            for key in ("story", "screenplay", "data", "response"):
                nested = parsed.get(key)
                if isinstance(nested, dict) and isinstance(nested.get("scenes"), list):
                    return nested
            return parsed

    raise ValueError("Story response was not valid JSON.")


def _first_value(scene: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = scene.get(key)
        if value:
            return value
    return None


def _as_string(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(lines) or None
    return str(value).strip() if value else None


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _scene_description(scene: dict[str, Any]) -> str:
    characters = _as_string_list(_first_value(scene, "characters", "cast"))
    palette = _as_string_list(_first_value(scene, "color_palette", "palette"))
    shot_list = _as_string_list(_first_value(scene, "shot_list", "shots"))
    description_parts = [
        f"Location: {_as_string(_first_value(scene, 'location', 'setting'))}" if _first_value(scene, "location", "setting") else None,
        f"Time: {_as_string(_first_value(scene, 'time', 'time_of_day'))}" if _first_value(scene, "time", "time_of_day") else None,
        f"Characters: {', '.join(characters)}" if characters else None,
        f"Visual Description: {_as_string(_first_value(scene, 'visual_description', 'visual_note', 'visuals'))}" if _first_value(scene, "visual_description", "visual_note", "visuals") else None,
        f"Character Action: {_as_string(_first_value(scene, 'character_action', 'action'))}" if _first_value(scene, "character_action", "action") else None,
        f"Dialogue: {_as_string(scene.get('dialogue'))}" if scene.get("dialogue") else None,
        f"Emotional Shift: {_as_string(_first_value(scene, 'emotional_shift', 'emotional_turn', 'emotion'))}" if _first_value(scene, "emotional_shift", "emotional_turn", "emotion") else None,
        f"Camera Suggestion: {_as_string(_first_value(scene, 'camera_suggestion', 'camera_shot', 'camera'))}" if _first_value(scene, "camera_suggestion", "camera_shot", "camera") else None,
        f"Lighting: {_as_string(scene.get('lighting'))}" if scene.get("lighting") else None,
        f"Background Music: {_as_string(_first_value(scene, 'background_music', 'music'))}" if _first_value(scene, "background_music", "music") else None,
        f"Color Palette: {', '.join(palette)}" if palette else None,
        f"Shot List: {', '.join(shot_list)}" if shot_list else None,
        f"Production Note: {_as_string(_first_value(scene, 'production_note', 'production_notes'))}" if _first_value(scene, "production_note", "production_notes") else None,
    ]
    return "\n\n".join(str(part).strip() for part in description_parts if part)


def _normalize_json_scenes(scenes: Any) -> list[dict[str, Any]]:
    if not isinstance(scenes, list):
        return []

    normalized_scenes: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue

        characters = _as_string_list(_first_value(scene, "characters", "cast"))
        color_palette = _as_string_list(_first_value(scene, "color_palette", "palette"))
        shot_list = _as_string_list(_first_value(scene, "shot_list", "shots"))
        description = _scene_description(scene) or str(scene.get("description", "")).strip()
        if not description:
            continue

        normalized_scenes.append(
            {
                "scene_number": scene.get("scene_number", index),
                "description": description,
                "location": _as_string(_first_value(scene, "location", "setting")),
                "time": _as_string(_first_value(scene, "time", "time_of_day")),
                "characters": characters,
                "visual_description": _as_string(_first_value(scene, "visual_description", "visual_note", "visuals")),
                "character_action": _as_string(_first_value(scene, "character_action", "action")),
                "dialogue": _as_string(scene.get("dialogue")),
                "emotional_shift": _as_string(_first_value(scene, "emotional_shift", "emotional_turn", "emotion")),
                "camera_suggestion": _as_string(_first_value(scene, "camera_suggestion", "camera_shot", "camera")),
                "lighting": _as_string(scene.get("lighting")),
                "background_music": _as_string(_first_value(scene, "background_music", "music")),
                "color_palette": color_palette,
                "shot_list": shot_list,
                "production_note": _as_string(_first_value(scene, "production_note", "production_notes")),
            }
        )
    return normalized_scenes


def _infer_lighting(scene: dict[str, Any]) -> str:
    time_value = str(scene.get("time") or "").lower()
    if "night" in time_value:
        return "Practical night lighting with motivated festival, street, or household sources."
    if "morning" in time_value:
        return "Soft natural morning light with warm highlights and gentle shadows."
    if "afternoon" in time_value or "golden" in time_value:
        return "Warm golden-hour light with textured shadows and natural contrast."
    return "Naturalistic practical lighting shaped around the emotional tone of the scene."


def _complete_scene_design_fields(scenes: list[dict[str, Any]], parsed: dict[str, Any]) -> list[dict[str, Any]]:
    overall_music = parsed.get("background_music") or "Restrained cinematic ambience rooted in the scene location."
    overall_palette = parsed.get("color_palette") or ["warm natural light", "earth tones", "festival accents"]

    completed: list[dict[str, Any]] = []
    for scene in scenes:
        scene_copy = dict(scene)
        scene_copy["lighting"] = scene_copy.get("lighting") or _infer_lighting(scene_copy)
        scene_copy["background_music"] = scene_copy.get("background_music") or overall_music
        scene_copy["color_palette"] = scene_copy.get("color_palette") or overall_palette
        completed.append(scene_copy)
    return completed


def _format_plain_text(story_text: str) -> list[dict[str, Any]]:
    paragraphs = [paragraph.strip() for paragraph in story_text.split("\n") if paragraph.strip()]
    return [
        {
            "scene_number": index,
            "description": paragraph,
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def _build_narration_text(parsed: dict[str, Any], scenes: list[dict[str, Any]]) -> str:
    voiceover = parsed.get("voiceover") if isinstance(parsed.get("voiceover"), dict) else {}
    narration_text = _as_string(voiceover.get("narration_text"))
    if narration_text:
        return narration_text

    summary = _as_string(parsed.get("summary"))
    if summary:
        return summary

    scene_lines = [
        _as_string(scene.get("emotional_shift") or scene.get("description"))
        for scene in scenes[:3]
    ]
    return " ".join(line for line in scene_lines if line)[:1200]


def _normalize_voiceover(parsed: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
    voiceover = parsed.get("voiceover") if isinstance(parsed.get("voiceover"), dict) else {}
    narration_text = _build_narration_text(parsed, scenes)
    return {
        "style": _as_string(voiceover.get("style")) or "Warm, cinematic narration",
        "sample": _as_string(voiceover.get("sample")) or narration_text[:180],
        "narration_text": narration_text,
    }


def format_story(
    story_text: str,
    language: str = "English",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if not story_text:
        return {
            "title": "Untitled",
            "language": language,
            "scenes": [],
            "metadata": metadata or {},
            **TOP_LEVEL_DEFAULTS,
    }

    try:
        parsed = _parse_story_json(story_text)
        normalized_scenes = _normalize_json_scenes(parsed.get("scenes"))

        if normalized_scenes:
            normalized_scenes = _complete_scene_design_fields(normalized_scenes, parsed)
            scene_count = parsed.get("scene_count") or len(normalized_scenes)
            merged_metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
            merged_metadata = {**merged_metadata, **(metadata or {})}
            voiceover = _normalize_voiceover(parsed, normalized_scenes)
            return {
                "title": parsed.get("title") or f"Generated Story ({language})",
                "genre": parsed.get("genre") or TOP_LEVEL_DEFAULTS["genre"],
                "language": parsed.get("language") or language,
                "logline": parsed.get("logline") or TOP_LEVEL_DEFAULTS["logline"],
                "summary": parsed.get("summary") or TOP_LEVEL_DEFAULTS["summary"],
                "characters": parsed.get("characters") or TOP_LEVEL_DEFAULTS["characters"],
                "character_profiles": _as_list(parsed.get("character_profiles")),
                "themes": parsed.get("themes") or TOP_LEVEL_DEFAULTS["themes"],
                "tone": parsed.get("tone") or TOP_LEVEL_DEFAULTS["tone"],
                "target_audience": parsed.get("target_audience") or TOP_LEVEL_DEFAULTS["target_audience"],
                "estimated_runtime": parsed.get("estimated_runtime") or TOP_LEVEL_DEFAULTS["estimated_runtime"],
                "scene_count": scene_count,
                "scenes": normalized_scenes,
                "voiceover": voiceover,
                "screenplay": _as_string(parsed.get("screenplay")) or TOP_LEVEL_DEFAULTS["screenplay"],
                "scene_breakdown": _as_list(parsed.get("scene_breakdown")),
                "dialogues": _as_list(parsed.get("dialogues")),
                "shot_list": _as_list(parsed.get("shot_list")),
                "camera_suggestions": _as_list(parsed.get("camera_suggestions")),
                "lighting_suggestions": _as_list(parsed.get("lighting_suggestions")),
                "background_music_suggestions": _as_list(parsed.get("background_music_suggestions")),
                "production_notes": _as_list(parsed.get("production_notes")),
                "poster_prompt": parsed.get("poster_prompt") or TOP_LEVEL_DEFAULTS["poster_prompt"],
                "background_music": parsed.get("background_music") or TOP_LEVEL_DEFAULTS["background_music"],
                "camera_style": parsed.get("camera_style") or TOP_LEVEL_DEFAULTS["camera_style"],
                "color_palette": parsed.get("color_palette") or TOP_LEVEL_DEFAULTS["color_palette"],
                "metadata": merged_metadata,
            }

        raise ValueError("Story JSON did not contain usable scenes.")
    except ValueError as exc:
        if story_text.lstrip().startswith("{") or "```json" in story_text.lower():
            logger.warning("Invalid structured story response: %s", exc)
            raise
    except TypeError:
        logger.warning("Invalid story response type", exc_info=True)
        raise ValueError("Story response type was invalid.")

    scenes = _format_plain_text(story_text)
    return {
        "title": f"Generated Story ({language})",
        "genre": TOP_LEVEL_DEFAULTS["genre"],
        "language": language,
        "logline": TOP_LEVEL_DEFAULTS["logline"],
        "summary": TOP_LEVEL_DEFAULTS["summary"],
        "characters": TOP_LEVEL_DEFAULTS["characters"],
        "character_profiles": TOP_LEVEL_DEFAULTS["character_profiles"],
        "themes": TOP_LEVEL_DEFAULTS["themes"],
        "tone": TOP_LEVEL_DEFAULTS["tone"],
        "target_audience": TOP_LEVEL_DEFAULTS["target_audience"],
        "estimated_runtime": TOP_LEVEL_DEFAULTS["estimated_runtime"],
        "scene_count": len(scenes),
        "scenes": scenes,
        "voiceover": {
            "style": "Warm, cinematic narration",
            "sample": "",
            "narration_text": " ".join(scene["description"] for scene in scenes[:3])[:1200],
        },
        "screenplay": TOP_LEVEL_DEFAULTS["screenplay"],
        "scene_breakdown": TOP_LEVEL_DEFAULTS["scene_breakdown"],
        "dialogues": TOP_LEVEL_DEFAULTS["dialogues"],
        "shot_list": TOP_LEVEL_DEFAULTS["shot_list"],
        "camera_suggestions": TOP_LEVEL_DEFAULTS["camera_suggestions"],
        "lighting_suggestions": TOP_LEVEL_DEFAULTS["lighting_suggestions"],
        "background_music_suggestions": TOP_LEVEL_DEFAULTS["background_music_suggestions"],
        "production_notes": TOP_LEVEL_DEFAULTS["production_notes"],
        "poster_prompt": TOP_LEVEL_DEFAULTS["poster_prompt"],
        "background_music": TOP_LEVEL_DEFAULTS["background_music"],
        "camera_style": TOP_LEVEL_DEFAULTS["camera_style"],
        "color_palette": TOP_LEVEL_DEFAULTS["color_palette"],
        "metadata": metadata or {},
    }

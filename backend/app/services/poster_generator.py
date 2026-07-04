# === FILE: backend/app/services/poster_generator.py ===
from typing import Any

POSTER_PLACEHOLDER_URL = "https://dummyimage.com/600x400/000/fff&text=Generated+Poster"


def generate_poster(text: str, language: str = "en") -> dict[str, Any]:
    return {
        "poster_url": POSTER_PLACEHOLDER_URL,
        "metadata": {
            "source": "placeholder",
            "language": language,
            "prompt_length": len(text.strip()),
        },
    }

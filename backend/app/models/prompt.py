from typing import List, Optional

from pydantic import BaseModel, Field, validator

class StoryPrompt(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=3000)
    genre: Optional[str] = Field(default="Drama", max_length=80)
    length_minutes: Optional[int] = Field(default=5, ge=1, le=30)
    language: Optional[str] = Field(default="English", max_length=50)
    themes: Optional[List[str]] = Field(default_factory=list, max_items=12)
    use_real_world_context: Optional[bool] = True

    @validator("prompt", "genre", "language")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if isinstance(value, str) else value

    @validator("themes", pre=True, always=True)
    def normalize_themes(cls, value: Optional[List[str]]) -> List[str]:
        if not value:
            return []
        return [theme.strip() for theme in value if isinstance(theme, str) and theme.strip()]

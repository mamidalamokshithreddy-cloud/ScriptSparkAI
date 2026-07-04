from pydantic import BaseModel
from pydantic import Field, validator

class MediaGenerationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    language: str = Field(default="Telugu", max_length=50)

class PosterResponse(BaseModel):
    url: str

class VoiceoverRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    voice: str = Field(default="bella", min_length=1, max_length=100)
    language: str = Field(default="English", max_length=50)

    @validator("text", "voice", "language")
    def strip_text(cls, value: str) -> str:
        return value.strip()

class VoiceoverResponse(BaseModel):
    audio_url: str
    voice: str
    language: str
    text: str

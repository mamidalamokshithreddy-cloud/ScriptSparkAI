from pydantic import BaseModel
from typing import List

class Scene(BaseModel):
    title: str
    narration: str
    dialogues: List[str]

class Character(BaseModel):
    name: str
    bio: str

class StoryResponse(BaseModel):
    title: str
    genre: str
    characters: List[Character]
    scenes: List[Scene]
    length_minutes: int
    source_facts: List[str]

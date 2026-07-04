from fastapi import APIRouter
from app.models.prompt import StoryPromptRequest
from app.models.story import StoryResponse
from app.services.story_generator import generate_story, parse_story

story_router = APIRouter()

@story_router.post("/generate", response_model=StoryResponse)
def generate_story_route(payload: StoryPromptRequest):
    story_text, facts = generate_story(payload, payload.use_real_world_context)
    return parse_story(story_text, facts, payload)

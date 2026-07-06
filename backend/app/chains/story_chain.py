from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.utils.logging import get_logger
from app.utils.tracing import current_request_id

ModelCaller = Callable[[str], str]
logger = get_logger(__name__)


def _prompt_value_to_text(prompt_value: ChatPromptValue) -> str:
    return prompt_value.to_string()


def build_story_chain(model_caller: ModelCaller) -> Any:
    prompt = ChatPromptTemplate.from_messages([("user", "{writer_prompt}")])
    return (
        {"writer_prompt": RunnablePassthrough()}
        | prompt
        | RunnableLambda(_prompt_value_to_text)
        | RunnableLambda(model_caller)
        | JsonOutputParser()
    )


def run_story_chain(writer_prompt: str, model_caller: ModelCaller) -> dict[str, Any]:
    logger.info("request_id=%s START run_story_chain.invoke prompt_chars=%s", current_request_id(), len(writer_prompt))
    try:
        parsed = build_story_chain(model_caller).invoke(writer_prompt)
    except Exception:
        logger.exception("request_id=%s run_story_chain.invoke failed", current_request_id())
        raise
    if not isinstance(parsed, dict):
        raise ValueError("Story LCEL chain returned non-object JSON.")
    logger.info("request_id=%s END run_story_chain.invoke keys=%s", current_request_id(), list(parsed.keys()))
    return parsed


def run_story_chain_as_text(writer_prompt: str, model_caller: ModelCaller) -> str:
    return json.dumps(run_story_chain(writer_prompt, model_caller), ensure_ascii=False)

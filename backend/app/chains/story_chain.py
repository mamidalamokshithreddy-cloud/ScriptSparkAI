from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

ModelCaller = Callable[[str], str]


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
    parsed = build_story_chain(model_caller).invoke(writer_prompt)
    if not isinstance(parsed, dict):
        raise ValueError("Story LCEL chain returned non-object JSON.")
    return parsed


def run_story_chain_as_text(writer_prompt: str, model_caller: ModelCaller) -> str:
    return json.dumps(run_story_chain(writer_prompt, model_caller), ensure_ascii=False)

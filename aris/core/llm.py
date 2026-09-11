from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from openai import OpenAI


DEFAULT_MODEL = "gpt-5.4-mini"


@dataclass(frozen=True)
class LLMResult:
    text: str
    meta: Dict[str, Any]


def generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
) -> LLMResult:
    client = OpenAI()

    if system:
        input_payload = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
    else:
        input_payload = prompt

    response = client.responses.create(
        model=model,
        input=input_payload,
    )

    usage = getattr(response, "usage", None)

    meta = {
        "provider": "openai",
        "model": model,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }

    return LLMResult(
        text=response.output_text,
        meta=meta,
    )


def generate_text(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
) -> str:
    return generate(
        prompt,
        model=model,
        system=system,
    ).text

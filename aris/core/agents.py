from dataclasses import dataclass
from typing import Callable, Dict, List

from aris.core.llm import LLMResult, generate


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    handler: Callable[[str], str | LLMResult]


def _echo(prompt: str) -> str:
    return f"EchoAgent received: {prompt}"


def _planner(prompt: str) -> str:
    # Deterministic control-path planner.
    return "\n".join([
        "PLAN:",
        f"1) Clarify objective: {prompt}",
        "2) Identify inputs + constraints",
        "3) Produce checklist + next actions",
    ])


def _analyst(prompt: str) -> LLMResult:
    return generate(
        prompt,
        system=(
            "You are ARIS Analyst, a rigorous analytical agent. "
            "Break problems into evidence, assumptions, risks, tradeoffs, "
            "and recommended next actions. Be concise, structured, and "
            "explicit about uncertainty. Do not invent facts."
        ),
    )


REGISTRY: Dict[str, Agent] = {
    "echo": Agent("echo", "Simple echo agent (dev smoke test).", _echo),
    "planner": Agent("planner", "Deterministic planning stub (no LLM).", _planner),
    "analyst": Agent("analyst", "LLM-backed analytical reasoning agent.", _analyst),
}


def list_agents() -> List[Agent]:
    return sorted(REGISTRY.values(), key=lambda a: a.name)


def get_agent(name: str) -> Agent:
    if name not in REGISTRY:
        raise KeyError(f"Unknown agent: {name}")
    return REGISTRY[name]

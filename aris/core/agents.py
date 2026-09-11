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


def _critic(prompt: str) -> LLMResult:
    return generate(
        prompt,
        system=(
            "You are ARIS Critic, an adversarial review agent. "
            "Evaluate the supplied analysis for unsupported assumptions, "
            "missing evidence, blind spots, overconfidence, contradictions, "
            "security or safety risks, and weak recommendations. "
            "Do not merely restate the analysis. Challenge it. "
            "At the very end, output exactly one machine-readable line in this format: "
            "ARIS_VERDICT: PASS, ARIS_VERDICT: REVISE, or ARIS_VERDICT: FAIL. "
            "Do not use those verdict words elsewhere in the response."
        ),
    )


REGISTRY: Dict[str, Agent] = {
    "echo": Agent("echo", "Simple echo agent (dev smoke test).", _echo),
    "planner": Agent("planner", "Deterministic planning stub (no LLM).", _planner),
    "analyst": Agent("analyst", "LLM-backed analytical reasoning agent.", _analyst),
    "critic": Agent("critic", "Adversarial review and challenge agent.", _critic),
}


def list_agents() -> List[Agent]:
    return sorted(REGISTRY.values(), key=lambda a: a.name)


def get_agent(name: str) -> Agent:
    if name not in REGISTRY:
        raise KeyError(f"Unknown agent: {name}")
    return REGISTRY[name]

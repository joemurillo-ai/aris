from dataclasses import dataclass
from typing import Callable, Dict, List

@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    handler: Callable[[str], str]

def _echo(prompt: str) -> str:
    return f"EchoAgent received: {prompt}"

def _planner(prompt: str) -> str:
    # Minimal deterministic planner stub (you’ll replace with LLM toolchain later)
    return "\n".join([
        "PLAN:",
        f"1) Clarify objective: {prompt}",
        "2) Identify inputs + constraints",
        "3) Produce checklist + next actions",
    ])

REGISTRY: Dict[str, Agent] = {
    "echo": Agent("echo", "Simple echo agent (dev smoke test).", _echo),
    "planner": Agent("planner", "Deterministic planning stub (no LLM).", _planner),
}

def list_agents() -> List[Agent]:
    return sorted(REGISTRY.values(), key=lambda a: a.name)

def get_agent(name: str) -> Agent:
    if name not in REGISTRY:
        raise KeyError(f"Unknown agent: {name}")
    return REGISTRY[name]

"""
planners/escalation.py — критерии эскалации к Groq. Все условия читаются из
уже посчитанных методов RunState (repeated_actions, repeated_errors,
steps_without_progress) — сам EscalationManager не хранит состояние, только
пороги.
"""
from dataclasses import dataclass

from code_agent.state import RunState


@dataclass
class EscalationManager:
    repeated_actions_threshold: int = 3
    repeated_errors_threshold: int = 3
    steps_without_progress_threshold: int = 5

    def should_escalate(self, state: RunState) -> bool:
        return any((
            state.repeated_actions() >= self.repeated_actions_threshold,
            state.repeated_errors() >= self.repeated_errors_threshold,
            state.steps_without_progress() >= self.steps_without_progress_threshold,
        ))

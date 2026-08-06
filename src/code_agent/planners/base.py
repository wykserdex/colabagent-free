from abc import ABC, abstractmethod
from code_agent.models import AgentAction


class Planner(ABC):
    @abstractmethod
    def next_action(self, goal: str, context: dict, tools: list[dict]) -> AgentAction:
        raise NotImplementedError

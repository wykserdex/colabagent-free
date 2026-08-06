"""
tools/base.py — базовый класс инструмента"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from code_agent.models import RiskLevel, ToolResult

ArgumentsT = TypeVar("ArgumentsT", bound=BaseModel)


@dataclass
class ToolContext:
    project_root: Path
    config: Any
    state: Any


class Tool(ABC, Generic[ArgumentsT]):
    name: str
    description: str
    args_model: type[ArgumentsT]
    default_risk: RiskLevel = RiskLevel.SAFE
    
    def parse_arguments(self, arguments: dict[str, Any]) -> ArgumentsT:
        return self.args_model.model_validate(arguments)
    
    def get_risk(self, arguments: ArgumentsT) -> RiskLevel:
        return self.default_risk
    
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        }
    
    @abstractmethod
    def execute(self, arguments: ArgumentsT, context: ToolContext) -> ToolResult:
        raise NotImplementedError

"""
tools/dispatcher.py — диспетчер инструментов
"""
from dataclasses import dataclass
from typing import Any

from code_agent.models import RiskLevel, ToolResult
from code_agent.tools.base import ToolContext
from code_agent.tools.registry import ToolRegistry


@dataclass
class PreparedToolCall:
    tool: Any
    arguments: Any
    risk: RiskLevel
    tool_name: str


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry, context: ToolContext):
        self.registry = registry
        self.context = context
    
    def prepare(self, name: str, raw_arguments: dict) -> PreparedToolCall:
        tool = self.registry.get(name)
        arguments = tool.parse_arguments(raw_arguments)
        risk = tool.get_risk(arguments)
        return PreparedToolCall(tool=tool, arguments=arguments, risk=risk, tool_name=name)
    
    def execute(self, prepared: PreparedToolCall) -> ToolResult:
        return prepared.tool.execute(prepared.arguments, self.context)

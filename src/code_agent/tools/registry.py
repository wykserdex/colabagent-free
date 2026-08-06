"""
tools/registry.py — регистрация инструментов
"""
from code_agent.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Повторная регистрация: {tool.name}")
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Неизвестный инструмент: {name}")
        return self._tools[name]
    
    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

"""
tools/git/status.py + diff.py — фиксированные git-команды, без произвольных аргументов.
"""
from pydantic import BaseModel

from code_agent.infrastructure.output_limiter import limit_output
from code_agent.infrastructure.process_runner import run_process
from code_agent.models import RiskLevel, ToolResult
from code_agent.tools.base import Tool, ToolContext


class GitStatusArgs(BaseModel):
    pass


class GitStatusTool(Tool[GitStatusArgs]):
    name = "git.status"
    description = "Показывает git status --short"
    args_model = GitStatusArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: GitStatusArgs, context: ToolContext) -> ToolResult:
        result = run_process(["git", "status", "--short"], cwd=str(context.project_root))
        if not result.success:
            return ToolResult(success=False, error=result.stderr)
        return ToolResult(success=True, output=limit_output(result.stdout) or "(нет изменений)")

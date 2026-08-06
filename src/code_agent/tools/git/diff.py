from pydantic import BaseModel
from typing import Optional

from code_agent.infrastructure.output_limiter import limit_output
from code_agent.infrastructure.process_runner import run_process
from code_agent.models import RiskLevel, ToolResult
from code_agent.tools.base import Tool, ToolContext


class GitDiffArgs(BaseModel):
    path: Optional[str] = None
    stat_only: bool = False


class GitDiffTool(Tool[GitDiffArgs]):
    name = "git.diff"
    description = "Показывает git diff (--stat или полный, опционально по конкретному пути)"
    args_model = GitDiffArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: GitDiffArgs, context: ToolContext) -> ToolResult:
        command = ["git", "diff"]
        if arguments.stat_only:
            command.append("--stat")
        if arguments.path:
            command += ["--", arguments.path]

        result = run_process(command, cwd=str(context.project_root))
        if not result.success:
            return ToolResult(success=False, error=result.stderr)
        return ToolResult(success=True, output=limit_output(result.stdout) or "(нет изменений)")

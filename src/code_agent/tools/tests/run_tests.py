"""
tools/tests/run_tests.py — запускает pytest. extra_args фильтруются через whitelist,
модель не может передать сюда произвольный флаг (не говоря уже про произвольную команду).
"""
from pydantic import BaseModel, Field

from code_agent.infrastructure.output_limiter import limit_output
from code_agent.infrastructure.process_runner import run_process
from code_agent.models import RiskLevel, ToolResult
from code_agent.tools.base import Tool, ToolContext

_ALLOWED_FLAGS = {"-q", "-v", "-x", "-s"}


def _is_allowed_arg(arg: str) -> bool:
    if arg in _ALLOWED_FLAGS:
        return True
    if arg.startswith("--maxfail=") or arg.startswith("-k") or arg.startswith("--maxfail"):
        return True
    return False


class RunTestsArgs(BaseModel):
    targets: list[str] = Field(default_factory=lambda: ["tests/"])
    extra_args: list[str] = Field(default_factory=list)


class RunTestsTool(Tool[RunTestsArgs]):
    name = "tests.run"
    description = "Запускает pytest по указанным путям с ограниченным набором флагов"
    args_model = RunTestsArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: RunTestsArgs, context: ToolContext) -> ToolResult:
        bad_args = [a for a in arguments.extra_args if not _is_allowed_arg(a)]
        if bad_args:
            return ToolResult(success=False, error=f"Недопустимые аргументы pytest: {bad_args}")

        command = ["python3", "-m", "pytest", *arguments.targets, *arguments.extra_args]
        result = run_process(command, cwd=str(context.project_root), timeout=180)

        output = limit_output(result.stdout + "\n" + result.stderr)
        # exit code 5 у pytest значит "тесты не найдены" — не всегда провал задачи как таковой,
        # но и не полноценный success; сообщаем как есть, пусть planner решает что делать дальше
        return ToolResult(
            success=result.success,
            output=output,
            error="" if result.success else f"pytest завершился с кодом {result.returncode}",
            metadata={"returncode": result.returncode},
        )

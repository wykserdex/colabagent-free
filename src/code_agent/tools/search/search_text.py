"""
tools/search/search_text.py — поиск по тексту через ripgrep (если стоит) с
python-фоллбэком. Модель передаёт СТРУКТУРИРОВАННЫЕ аргументы (query/path/glob),
не готовую shell-команду — process_runner собирает список аргументов сам,
никакой возможности инъекции через query.
"""
import shutil
from pydantic import BaseModel, Field
from typing import Optional

from code_agent.infrastructure.output_limiter import limit_output
from code_agent.infrastructure.process_runner import run_process
from code_agent.models import RiskLevel, ToolResult
from code_agent.safety.path_guard import resolve_project_path, SafetyError
from code_agent.tools.base import Tool, ToolContext


class SearchTextArgs(BaseModel):
    query: str
    path: str = "."
    glob: Optional[str] = None
    max_results: int = Field(default=100, ge=1, le=1000)


class SearchTextTool(Tool[SearchTextArgs]):
    name = "search.search_text"
    description = "Ищет текст/паттерн в файлах проекта (через ripgrep)"
    args_model = SearchTextArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: SearchTextArgs, context: ToolContext) -> ToolResult:
        try:
            search_root = resolve_project_path(context.project_root, arguments.path)
        except SafetyError as e:
            return ToolResult(success=False, error=str(e))

        if shutil.which("rg"):
            command = ["rg", "--line-number", "--no-heading", "--max-count", str(arguments.max_results)]
            if arguments.glob:
                command += ["--glob", arguments.glob]
            command += [arguments.query, str(search_root)]
        else:
            return self._python_fallback(arguments, search_root)

        result = run_process(command, cwd=str(context.project_root))
        # ripgrep возвращает exit code 1 если просто ничего не нашёл (не ошибка выполнения)
        if result.returncode not in (0, 1):
            return ToolResult(success=False, error=result.stderr or "Ошибка поиска")

        output = result.stdout.strip() or "(ничего не найдено)"
        return ToolResult(success=True, output=limit_output(output))

    def _python_fallback(self, arguments: SearchTextArgs, search_root) -> ToolResult:
        import fnmatch
        matches = []
        for path in search_root.rglob("*"):
            if not path.is_file():
                continue
            if arguments.glob and not fnmatch.fnmatch(path.name, arguments.glob):
                continue
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if arguments.query in line:
                            matches.append(f"{path}:{i}:{line.strip()}")
                            if len(matches) >= arguments.max_results:
                                return ToolResult(success=True, output=limit_output("\n".join(matches)))
            except Exception:
                continue
        return ToolResult(success=True, output="\n".join(matches) or "(ничего не найдено)")

"""
tools/code/run_script.py — запуск Python-скрипта
"""
import os
import subprocess
import sys
import signal
from pathlib import Path

from pydantic import BaseModel, Field

from code_agent.infrastructure.output_limiter import limit_output
from code_agent.models import RiskLevel, ToolResult
from code_agent.safety.path_guard import resolve_project_path, SafetyError
from code_agent.tools.base import Tool, ToolContext


class RunScriptArgs(BaseModel):
    path: str
    timeout: int = Field(default=60, ge=1, le=600)
    input_data: str = Field(default="")


def _venv_python(project_root: Path) -> str:
    venv_dir = project_root / ".venv"
    venv_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], capture_output=True, timeout=120)
    return str(venv_python) if venv_python.exists() else sys.executable


class RunScriptTool(Tool[RunScriptArgs]):
    name = "code.run_script"
    description = "Запускает Python-файл"
    args_model = RunScriptArgs
    # Раньше был SAFE — то есть запуск произвольного Python-скрипта
    # классифицировался наравне с чтением файла. Скрипт может делать что
    # угодно в рамках прав процесса, минимум REVIEW.
    default_risk = RiskLevel.REVIEW

    def execute(self, arguments: RunScriptArgs, context: ToolContext) -> ToolResult:
        try:
            project_root = context.project_root.resolve()
            try:
                target = resolve_project_path(project_root, arguments.path)
            except SafetyError as e:
                return ToolResult(
                    success=False,
                    error=str(e),
                    error_type="permission_denied",
                    retryable=False,
                )

            if not target.exists():
                return ToolResult(
                    success=False,
                    error=f"Файл не существует: {arguments.path}",
                    error_type="file_not_found",
                    retryable=False,
                )

            venv_python = _venv_python(project_root)

            # Проверка синтаксиса
            syntax_check = subprocess.run(
                [venv_python, "-m", "py_compile", str(target)],
                capture_output=True, timeout=30, text=True, errors="replace",
            )
            if syntax_check.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Синтаксическая ошибка:\n{syntax_check.stderr}",
                    error_type="syntax_error",
                    retryable=False,
                    stderr=syntax_check.stderr,
                )

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            env["PYTHONUNBUFFERED"] = "1"

            # Запускаем с возможностью убить всю группу процессов
            process = subprocess.Popen(
                [venv_python, str(target)],
                cwd=str(project_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                env=env,
                start_new_session=True,
            )

            try:
                stdout, stderr = process.communicate(
                    input=arguments.input_data,
                    timeout=arguments.timeout
                )
                
                if process.returncode == 0:
                    return ToolResult(
                        success=True,
                        stdout=limit_output(stdout),
                        output=limit_output(stdout) or "Скрипт выполнен успешно",
                        exit_code=process.returncode,
                    )
                else:
                    return ToolResult(
                        success=False,
                        error=limit_output(stderr or f"Exit code {process.returncode}"),
                        stdout=limit_output(stdout),
                        stderr=limit_output(stderr),
                        exit_code=process.returncode,
                        error_type="runtime_error",
                        retryable=True,
                    )
                    
            except subprocess.TimeoutExpired:
                # Убиваем всю группу процессов
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                
                return ToolResult(
                    success=False,
                    error=f"Таймаут >{arguments.timeout}с",
                    error_type="timeout",
                    timed_out=True,
                    retryable=True,
                )
                
        except PermissionError as e:
            return ToolResult(
                success=False,
                error=str(e),
                error_type="permission_denied",
                retryable=False,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                error_type="runtime_error",
                retryable=True,
            )

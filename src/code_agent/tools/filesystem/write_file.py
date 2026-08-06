"""
tools/filesystem/write_file.py — запись файла
"""
import shutil
import time
from pathlib import Path

from pydantic import BaseModel

from code_agent.infrastructure.atomic_write import atomic_write
from code_agent.models import RiskLevel, ToolResult
from code_agent.safety.path_guard import resolve_project_path, SafetyError
from code_agent.tools.base import Tool, ToolContext


class WriteFileArgs(BaseModel):
    path: str
    content: str


class WriteFileTool(Tool[WriteFileArgs]):
    name = "filesystem.write_file"
    description = "Создаёт или перезаписывает файл"
    args_model = WriteFileArgs
    default_risk = RiskLevel.REVIEW

    def execute(self, arguments: WriteFileArgs, context: ToolContext) -> ToolResult:
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

            # Создаем резервную копию если файл существует
            if target.exists():
                backup_dir = context.project_root / ".agent_backups"
                backup_dir.mkdir(exist_ok=True)
                backup_name = f"{target.name}.{int(time.time())}.bak"
                shutil.copy2(target, backup_dir / backup_name)
            
            atomic_write(target, arguments.content)
            
            rel_path = str(target.relative_to(project_root))
            return ToolResult(
                success=True,
                output=f"Записано {len(arguments.content)} символов в {rel_path}",
                changed_files=[rel_path],
                metadata={"path": rel_path, "size": len(arguments.content)},
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

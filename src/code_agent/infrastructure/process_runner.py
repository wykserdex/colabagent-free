"""
infrastructure/process_runner.py — запуск процессов
"""
import os
import subprocess
from dataclasses import dataclass


@dataclass
class ProcessResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


def run_process(
    command: list[str],
    cwd: str,
    timeout: int = 180,
) -> ProcessResult:
    """Запускает процесс с защитой от shell-инъекций"""
    try:
        result = subprocess.run(
            command,
            shell=False,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return ProcessResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return ProcessResult(
            success=False,
            stdout="",
            stderr=f"Таймаут >{timeout}с",
            returncode=-1,
            timed_out=True,
        )
    except Exception as e:
        return ProcessResult(
            success=False,
            stdout="",
            stderr=str(e),
            returncode=-1,
        )

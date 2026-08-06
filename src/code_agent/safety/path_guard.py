"""
safety/path_guard.py — гарантирует что любой путь, с которым работает инструмент,
физически находится внутри project_root. Проверяет и обычные '../' трюки, и симлинки.
"""
from pathlib import Path


class SafetyError(Exception):
    pass


_FORBIDDEN_NAMES = {".env", ".git"}
_FORBIDDEN_SUFFIXES = {".pem", ".key"}


def resolve_project_path(root: Path, requested: str) -> Path:
    root = root.resolve()
    target = (root / requested).resolve()

    if target != root and root not in target.parents:
        raise SafetyError(f"Путь '{requested}' выходит за пределы проекта")

    for part in target.parts:
        if part in _FORBIDDEN_NAMES:
            raise SafetyError(f"Путь '{requested}' затрагивает запрещённый файл/папку: {part}")

    if target.suffix in _FORBIDDEN_SUFFIXES:
        raise SafetyError(f"Путь '{requested}' — файл ключа/сертификата, доступ запрещён")

    return target

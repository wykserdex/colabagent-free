"""
safety/self_guard.py — не даёт агенту работать внутри собственных исходников.
"""
from pathlib import Path


class SelfGuardError(Exception):
    pass


def _agent_source_root() -> Path:
    import code_agent
    return Path(code_agent.__file__).resolve().parent.parent.parent


def ensure_not_agent_source(project_root: Path) -> None:
    project_root = project_root.resolve()
    try:
        agent_root = _agent_source_root()
    except Exception:
        return

    if project_root == agent_root or agent_root in project_root.parents:
        raise SelfGuardError(
            f"project_root ({project_root}) находится внутри исходников самого агента "
            f"({agent_root}). Это почти наверняка забытый --project — укажи явно "
            f"отдельную рабочую папку, не запускай агента над самим собой."
        )
    if project_root in agent_root.parents or project_root == agent_root.parent:
        raise SelfGuardError(
            f"project_root ({project_root}) — родительская папка для исходников агента "
            f"({agent_root}). Агент может случайно задеть собственный код при листинге/поиске."
        )

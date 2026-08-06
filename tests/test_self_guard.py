from pathlib import Path

import pytest

from code_agent.safety.self_guard import ensure_not_agent_source, SelfGuardError


def test_normal_external_project_passes(tmp_path):
    # обычная отдельная папка проекта — не должна триггерить guard
    ensure_not_agent_source(tmp_path)  # не должно кидать исключение


def test_agent_own_source_directory_blocked():
    import code_agent
    agent_source_dir = Path(code_agent.__file__).resolve().parent
    with pytest.raises(SelfGuardError):
        ensure_not_agent_source(agent_source_dir)


def test_subdirectory_of_agent_source_blocked():
    import code_agent
    agent_source_dir = Path(code_agent.__file__).resolve().parent
    subdir = agent_source_dir / "tools"  # реально существующая подпапка пакета
    with pytest.raises(SelfGuardError):
        ensure_not_agent_source(subdir)


def test_parent_of_agent_source_blocked():
    import code_agent
    agent_source_dir = Path(code_agent.__file__).resolve().parent
    with pytest.raises(SelfGuardError):
        ensure_not_agent_source(agent_source_dir.parent)

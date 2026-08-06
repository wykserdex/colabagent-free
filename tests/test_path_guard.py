import pytest
from pathlib import Path

from code_agent.safety.path_guard import resolve_project_path, SafetyError


def test_normal_path_inside_project(tmp_path):
    result = resolve_project_path(tmp_path, "src/app.py")
    assert result == (tmp_path / "src" / "app.py").resolve()


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(SafetyError):
        resolve_project_path(tmp_path, "../../etc/passwd")


def test_symlink_escape_blocked(tmp_path):
    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("secret")
    link = tmp_path / "innocent_looking_file.txt"
    link.symlink_to(outside)
    with pytest.raises(SafetyError):
        resolve_project_path(tmp_path, "innocent_looking_file.txt")


def test_env_file_forbidden(tmp_path):
    with pytest.raises(SafetyError):
        resolve_project_path(tmp_path, ".env")


def test_git_dir_forbidden(tmp_path):
    with pytest.raises(SafetyError):
        resolve_project_path(tmp_path, ".git/config")

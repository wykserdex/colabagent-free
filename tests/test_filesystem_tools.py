from pathlib import Path

from code_agent.tools.base import ToolContext
from code_agent.tools.filesystem.list_files import ListFilesTool
from code_agent.tools.filesystem.read_file import ReadFileTool
from code_agent.tools.filesystem.write_file import WriteFileTool
from code_agent.tools.code.apply_patch import ApplyPatchTool


def _ctx(tmp_path) -> ToolContext:
    return ToolContext(project_root=tmp_path, config=None, state=None)


def test_write_then_read_file(tmp_path):
    write_tool = WriteFileTool()
    ctx = _ctx(tmp_path)
    result = write_tool.execute(write_tool.parse_arguments({"path": "hello.py", "content": "print(1)\n"}), ctx)
    assert result.success
    assert result.changed_files == ["hello.py"]

    read_tool = ReadFileTool()
    result = read_tool.execute(read_tool.parse_arguments({"path": "hello.py"}), ctx)
    assert result.success
    assert "print(1)" in result.output


def test_write_file_creates_backup_on_overwrite(tmp_path):
    write_tool = WriteFileTool()
    ctx = _ctx(tmp_path)
    write_tool.execute(write_tool.parse_arguments({"path": "a.py", "content": "v1"}), ctx)
    write_tool.execute(write_tool.parse_arguments({"path": "a.py", "content": "v2"}), ctx)

    backups = list((tmp_path / ".agent_backups").glob("a.py.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text() == "v1"


def test_read_file_rejects_env(tmp_path):
    (tmp_path / ".env").write_text("SECRET=123")
    read_tool = ReadFileTool()
    ctx = _ctx(tmp_path)
    result = read_tool.execute(read_tool.parse_arguments({"path": ".env"}), ctx)
    assert not result.success


def test_list_files_ignores_venv(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("junk")

    list_tool = ListFilesTool()
    ctx = _ctx(tmp_path)
    result = list_tool.execute(list_tool.parse_arguments({"path": "."}), ctx)
    assert result.success
    assert "app.py" in result.output
    assert "junk.py" not in result.output


def test_apply_patch_requires_unique_match(tmp_path):
    ctx = _ctx(tmp_path)
    (tmp_path / "f.py").write_text("x = 1\nx = 1\n")
    patch_tool = ApplyPatchTool()
    result = patch_tool.execute(
        patch_tool.parse_arguments({"path": "f.py", "old_text": "x = 1", "new_text": "x = 2"}), ctx
    )
    assert not result.success
    assert "встречается" in result.error


def test_apply_patch_success(tmp_path):
    ctx = _ctx(tmp_path)
    (tmp_path / "f.py").write_text("def broken():\n    retun 1\n")
    patch_tool = ApplyPatchTool()
    result = patch_tool.execute(
        patch_tool.parse_arguments({"path": "f.py", "old_text": "retun 1", "new_text": "return 1"}), ctx
    )
    assert result.success
    assert (tmp_path / "f.py").read_text() == "def broken():\n    return 1\n"

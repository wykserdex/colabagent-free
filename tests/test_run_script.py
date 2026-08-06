from code_agent.tools.base import ToolContext
from code_agent.tools.code.run_script import RunScriptTool


def _ctx(tmp_path) -> ToolContext:
    return ToolContext(project_root=tmp_path, config=None, state=None)


def test_run_script_success(tmp_path):
    (tmp_path / "ok.py").write_text("print('hello')\n")
    tool = RunScriptTool()
    result = tool.execute(tool.parse_arguments({"path": "ok.py"}), _ctx(tmp_path))
    assert result.success
    assert "hello" in result.output


def test_run_script_syntax_error_caught_early(tmp_path):
    (tmp_path / "bad.py").write_text("def f(:\n    pass\n")
    tool = RunScriptTool()
    result = tool.execute(tool.parse_arguments({"path": "bad.py"}), _ctx(tmp_path))
    assert not result.success
    assert "интакс" in result.error.lower() or "syntax" in result.error.lower()


def test_run_script_missing_file(tmp_path):
    tool = RunScriptTool()
    result = tool.execute(tool.parse_arguments({"path": "nope.py"}), _ctx(tmp_path))
    assert not result.success


def test_run_script_runtime_error(tmp_path):
    (tmp_path / "crash.py").write_text("raise ValueError('boom')\n")
    tool = RunScriptTool()
    result = tool.execute(tool.parse_arguments({"path": "crash.py"}), _ctx(tmp_path))
    assert not result.success
    assert "boom" in result.error


def test_run_script_with_explicit_input_data(tmp_path):
    """Новый контракт: input_data передаётся ЯВНО, не угадывается через
    EOFError-эвристику как раньше — это чище, модель сама решает что подать на stdin."""
    (tmp_path / "interactive.py").write_text("x = input('name: ')\nprint(f'Hello, {x}')\n")
    tool = RunScriptTool()
    result = tool.execute(
        tool.parse_arguments({"path": "interactive.py", "input_data": "Kirill\n"}), _ctx(tmp_path)
    )
    assert result.success
    assert "Hello, Kirill" in result.output


def test_run_script_without_input_data_fails_on_input_call(tmp_path):
    """Без input_data скрипт с input() упадёт на EOFError — это ожидаемо честно
    репортится как ошибка, а не тихо трактуется как 'успешный смоук-тест'."""
    (tmp_path / "interactive.py").write_text("x = input('name: ')\nprint(x)\n")
    tool = RunScriptTool()
    result = tool.execute(tool.parse_arguments({"path": "interactive.py"}), _ctx(tmp_path))
    assert not result.success
    assert "EOFError" in result.error

from pathlib import Path

from pydantic import BaseModel

from code_agent.models import RiskLevel, ToolResult
from code_agent.tools.base import Tool, ToolContext
from code_agent.tools.registry import ToolRegistry
from code_agent.tools.dispatcher import ToolDispatcher


class _EchoArgs(BaseModel):
    text: str


class _EchoTool(Tool[_EchoArgs]):
    name = "test.echo"
    description = "Возвращает переданный текст как есть — для теста каркаса"
    args_model = _EchoArgs
    default_risk = RiskLevel.SAFE

    def execute(self, arguments: _EchoArgs, context: ToolContext) -> ToolResult:
        return ToolResult(success=True, output=arguments.text)


def _make_dispatcher(tmp_path) -> ToolDispatcher:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    context = ToolContext(project_root=tmp_path, config=None, state=None)
    return ToolDispatcher(registry, context)


def test_registry_prevents_duplicate_registration():
    registry = ToolRegistry()
    registry.register(_EchoTool())
    try:
        registry.register(_EchoTool())
        assert False, "должен был поднять ValueError на повторную регистрацию"
    except ValueError:
        pass


def test_registry_unknown_tool_raises():
    registry = ToolRegistry()
    try:
        registry.get("does.not.exist")
        assert False
    except KeyError:
        pass


def test_dispatcher_prepare_and_execute(tmp_path):
    dispatcher = _make_dispatcher(tmp_path)
    prepared = dispatcher.prepare("test.echo", {"text": "привет"})
    assert prepared.risk == RiskLevel.SAFE
    result = dispatcher.execute(prepared)
    assert result.success is True
    assert result.output == "привет"


def test_dispatcher_invalid_arguments_raise(tmp_path):
    dispatcher = _make_dispatcher(tmp_path)
    try:
        dispatcher.prepare("test.echo", {"wrong_field": 123})
        assert False, "должен был поднять ошибку валидации на неверные аргументы"
    except Exception:
        pass

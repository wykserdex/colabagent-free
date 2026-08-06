import json
from unittest.mock import patch, MagicMock

from code_agent.planners.colab import ColabPlanner


def _mock_response(json_body: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


def test_unwraps_fastapi_response_wrapper(tmp_path, monkeypatch):
    """Реальный баг: Colab отдаёт {"response": "<json-строка от модели>"} — двойная
    JSON-обёртка. Проверяем что распаковка работает верно."""
    monkeypatch.chdir(tmp_path)  # ColabPlanner создаёт runtime/logs относительно cwd
    inner_action = {
        "type": "tool_call", "tool": "filesystem.list_files",
        "arguments": {"path": "."}, "reason": "смотрю",
    }
    with patch("requests.post", return_value=_mock_response({"response": json.dumps(inner_action)})):
        planner = ColabPlanner(url="https://fake-colab.test", timeout=5)
        action = planner.next_action("тестовая цель", {"history_text": ""}, [])

    assert action.type == "tool_call"
    assert action.tool == "filesystem.list_files"
    assert action.arguments == {"path": "."}


def test_finish_action_through_wrapper(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inner_action = {"type": "finish", "summary": "готово"}
    with patch("requests.post", return_value=_mock_response({"response": json.dumps(inner_action)})):
        planner = ColabPlanner(url="https://fake-colab.test", timeout=5)
        action = planner.next_action("цель", {"history_text": ""}, [])

    assert action.type == "finish"
    assert action.summary == "готово"


def test_empty_inner_response_returns_message_not_crash(tmp_path, monkeypatch):
    """Ollama иногда реально возвращает пустую строку — планировщик должен
    вернуть безопасный message, а не упасть с traceback."""
    monkeypatch.chdir(tmp_path)
    with patch("requests.post", return_value=_mock_response({"response": ""})):
        planner = ColabPlanner(url="https://fake-colab.test", timeout=5)
        action = planner.next_action("цель", {"history_text": ""}, [])

    assert action.type == "message"  # безопасный фоллбэк, не исключение наружу
    assert action.message  # непустое объясняющее сообщение


def test_markdown_wrapped_inner_json_still_parses(tmp_path, monkeypatch):
    """Модель иногда оборачивает JSON в ```json ... ``` даже внутри уже
    распакованного response-поля — парсер должен это пережить."""
    monkeypatch.chdir(tmp_path)
    inner_action = {"type": "tool_call", "tool": "git.status", "arguments": {}, "reason": "проверяю"}
    wrapped = f"```json\n{json.dumps(inner_action)}\n```"
    with patch("requests.post", return_value=_mock_response({"response": wrapped})):
        planner = ColabPlanner(url="https://fake-colab.test", timeout=5)
        action = planner.next_action("цель", {"history_text": ""}, [])

    assert action.type == "tool_call"
    assert action.tool == "git.status"


def test_timeout_returns_message_not_exception(tmp_path, monkeypatch):
    """Таймаут — ожидаемая ситуация (медленная генерация), не должна ронять
    оркестратор наружу необработанным исключением."""
    monkeypatch.chdir(tmp_path)
    import requests
    with patch("requests.post", side_effect=requests.exceptions.Timeout()):
        planner = ColabPlanner(url="https://fake-colab.test", timeout=5)
        action = planner.next_action("цель", {"history_text": ""}, [])

    assert action.type == "message"
    assert "аймаут" in action.message.lower() or "имеout" in action.message.lower() or "timeout" in action.message.lower() or "секунд" in action.message.lower()


def test_constructor_respects_passed_timeout(tmp_path, monkeypatch):
    """Раньше здесь был баг: self.timeout = 1200 захардкожено, игнорируя параметр
    конструктора. Проверяем что теперь переданное значение реально используется."""
    monkeypatch.chdir(tmp_path)
    planner = ColabPlanner(url="https://fake-colab.test", timeout=42)
    assert planner.timeout == 42

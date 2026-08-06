import pytest

from code_agent.models import AgentAction


def test_message_action_valid():
    action = AgentAction(type="message", message="привет, я понял тебя")
    assert action.type == "message"
    assert action.message == "привет, я понял тебя"


def test_message_action_without_message_field_raises():
    with pytest.raises(Exception):
        AgentAction(type="message")


def test_tool_call_still_requires_tool():
    with pytest.raises(Exception):
        AgentAction(type="tool_call")


def test_finish_still_requires_summary():
    with pytest.raises(Exception):
        AgentAction(type="finish")

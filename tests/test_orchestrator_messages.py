import queue

from code_agent.models import AgentAction, RiskLevel
from code_agent.orchestrator import Orchestrator
from code_agent.planners.base import Planner
from code_agent.safety.approval import ApprovalManager
from code_agent.state import RunState
from code_agent.tools import create_tool_registry
from code_agent.tools.base import ToolContext
from code_agent.tools.dispatcher import ToolDispatcher


class _RecordingPlanner(Planner):
    """Фейковый планировщик — записывает какую историю видел на каждом вызове,
    чтобы проверить что incoming_messages реально долетают до контекста."""

    def __init__(self, actions: list[AgentAction]):
        self.actions = list(actions)
        self.seen_history_texts: list[str] = []

    def next_action(self, goal, context, tools):
        self.seen_history_texts.append(context.get("history_text", ""))
        return self.actions.pop(0)


def _setup(tmp_path):
    registry = create_tool_registry()  # реальные инструменты — совпадают с allowed_tools по фазам
    ctx = ToolContext(project_root=tmp_path, config=None, state=None)
    dispatcher = ToolDispatcher(registry, ctx)
    approval = ApprovalManager(mode="auto")
    return registry, dispatcher, approval


def test_incoming_message_appears_in_history_before_next_planner_call(tmp_path):
    """Проверяем именно инъекцию сообщения в историю — не гонимся за полным
    завершением сессии (это отдельная, более сложная логика can_finish())."""
    registry, dispatcher, approval = _setup(tmp_path)
    (tmp_path / "README.md").write_text("hello")

    class _InfinitePlanner(Planner):
        """Бесконечно повторяет безобидное чтение файла — нужно просто дожить
        до второго вызова, не завершая сессию."""
        def __init__(self):
            self.seen_history_texts: list[str] = []

        def next_action(self, goal, context, tools):
            self.seen_history_texts.append(context.get("history_text", ""))
            return AgentAction(
                type="tool_call", tool="filesystem.read_file",
                arguments={"path": "README.md"}, reason=f"читаю (попытка {len(self.seen_history_texts)})",
            )

    planner = _InfinitePlanner()
    orchestrator = Orchestrator(
        planner=planner, fallback_planner=planner, dispatcher=dispatcher,
        registry=registry, approval=approval,
        runtime_dir=str(tmp_path / "runtime"),
    )

    incoming = queue.Queue()
    incoming.put("переделай вот это пожалуйста")

    state = RunState(goal="тестовая цель", project_root=str(tmp_path), max_steps=5)
    orchestrator.run(state, incoming_messages=incoming)

    # сообщение должно было попасть в историю ДО как минимум одного из вызовов планировщика
    assert any("переделай вот это" in text for text in planner.seen_history_texts)


def test_message_action_records_and_continues(tmp_path):
    """message — просто один ход, не обрывает сессию сам по себе, цикл идёт дальше."""
    registry, dispatcher, approval = _setup(tmp_path)

    planner = _RecordingPlanner([
        AgentAction(type="message", message="понял, продолжаю", reason="просто отвечаю"),
        AgentAction(type="finish", summary="готово"),
    ])
    orchestrator = Orchestrator(
        planner=planner, fallback_planner=planner, dispatcher=dispatcher,
        registry=registry, approval=approval,
        runtime_dir=str(tmp_path / "runtime"),
    )
    state = RunState(goal="цель", project_root=str(tmp_path), max_steps=10)
    final_state = orchestrator.run(state)

    assert any(
        h["result"].get("output") == "понял, продолжаю" for h in final_state.history
    )


def test_events_emitted_for_user_message(tmp_path):
    registry, dispatcher, approval = _setup(tmp_path)
    planner = _RecordingPlanner([AgentAction(type="finish", summary="готово")])
    orchestrator = Orchestrator(
        planner=planner, fallback_planner=planner, dispatcher=dispatcher,
        registry=registry, approval=approval,
        runtime_dir=str(tmp_path / "runtime"),
    )
    incoming = queue.Queue()
    incoming.put("привет")

    events = []
    state = RunState(goal="цель", project_root=str(tmp_path), max_steps=10)
    orchestrator.run(state, on_event=events.append, incoming_messages=incoming)

    user_events = [e for e in events if e["type"] == "user_message"]
    assert len(user_events) == 1
    assert user_events[0]["text"] == "привет"


def test_review_risk_action_requires_approval(tmp_path):
    """Критично: write_file (REVIEW risk) не должен выполняться молча без
    approval — если approval отклоняет (read-only), запись не происходит."""
    from code_agent.state import Phase
    registry, dispatcher, _ = _setup(tmp_path)
    approval = ApprovalManager(mode="read-only")  # блокирует любые REVIEW-действия

    planner = _RecordingPlanner([
        AgentAction(
            type="tool_call", tool="filesystem.write_file",
            arguments={"path": "should_not_exist.py", "content": "x = 1"}, reason="тест",
        ),
        AgentAction(type="finish", summary="готово"),
    ])
    orchestrator = Orchestrator(
        planner=planner, fallback_planner=planner, dispatcher=dispatcher,
        registry=registry, approval=approval,
        runtime_dir=str(tmp_path / "runtime"),
    )
    state = RunState(goal="цель", project_root=str(tmp_path), max_steps=10)
    state.phase = Phase.IMPLEMENTATION  # write_file разрешён только в этой фазе
    orchestrator.run(state)

    assert not (tmp_path / "should_not_exist.py").exists()

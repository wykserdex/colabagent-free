"""
cli.py — точка входа для CLI.
"""
from pathlib import Path
import typer

from code_agent.config import load_settings
from code_agent.orchestrator import Orchestrator, AgentMode
from code_agent.planners.colab import ColabPlanner
from code_agent.planners.escalation import EscalationManager
from code_agent.planners.groq import GroqPlanner
from code_agent.planners.safe_planner import SafePlanner
from code_agent.safety.approval import ApprovalManager
from code_agent.safety.self_guard import ensure_not_agent_source, SelfGuardError
from code_agent.state import RunState
from code_agent.tools import create_tool_registry
from code_agent.tools.base import ToolContext
from code_agent.tools.dispatcher import ToolDispatcher

app = typer.Typer()

_MODE_MAP = {
    "ask": AgentMode.SUPERVISED,
    "auto": AgentMode.AUTONOMOUS,
    "read-only": AgentMode.REVIEW,
}

@app.command()
def run(
    goal: str = typer.Argument(..., help="Задача для агента"),
    project: str = typer.Option(..., "--project", help="Путь к рабочей папке проекта (ОБЯЗАТЕЛЬНО, не исходники агента)"),
    mode: str = typer.Option("ask", "--mode", help="ask | auto | read-only"),
):
    if mode not in _MODE_MAP:
        typer.echo(f"🛑 Неверный --mode: {mode}. Доступные: ask, auto, read-only")
        raise typer.Exit(code=1)

    settings = load_settings()
    project_root = Path(project).resolve()

    try:
        ensure_not_agent_source(project_root)
    except SelfGuardError as e:
        typer.echo(f"🛑 {e}")
        raise typer.Exit(code=1)

    project_root.mkdir(parents=True, exist_ok=True)

    registry = create_tool_registry()
    context = ToolContext(project_root=project_root, config=settings, state=None)
    dispatcher = ToolDispatcher(registry, context)
    approval = ApprovalManager(mode=mode)  # mode = "ask"/"auto"/"read-only"
    escalation = EscalationManager()

    colab_planner = SafePlanner(ColabPlanner(url=settings.colab_url, token=settings.colab_token, timeout=settings.request_timeout))
    groq_planner = SafePlanner(GroqPlanner(api_key=settings.groq_api_key, model=settings.groq_model))

    state = RunState(goal=goal, project_root=str(project_root), max_steps=settings.max_steps, runtime_dir=settings.runtime_dir)

    orchestrator = Orchestrator(
        planner=colab_planner,
        fallback_planner=groq_planner,
        dispatcher=dispatcher,
        registry=registry,
        approval=approval,
        runtime_dir=settings.runtime_dir,
        mode=_MODE_MAP[mode],
    )

    def on_event(event: dict):
        if event.get("type") == "agent_message":
            typer.echo(event.get("data", {}).get("text", ""))

    typer.echo(f"🤖 Сессия {state.session_id}, цель: {goal}")
    final_state = orchestrator.run(state, on_event=on_event)

    if final_state.status == "complete":
        typer.echo(f"\n🎉 Завершено: {final_state.summary}")
    else:
        typer.echo(f"\n⚠️ Остановлено на шаге {final_state.step}/{final_state.max_steps}, статус: {final_state.status}")

if __name__ == "__main__":
    app()

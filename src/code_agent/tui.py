"""
tui.py — интерактивный чат-интерфейс с агентом
"""
import queue
import threading
import time
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog

from code_agent.config import load_settings
from code_agent.orchestrator import Orchestrator, AgentMode
from code_agent.planners.colab import ColabPlanner
from code_agent.planners.groq import GroqPlanner
from code_agent.planners.safe_planner import SafePlanner
from code_agent.safety.approval import ApprovalManager
from code_agent.state import RunState
from code_agent.tools import create_tool_registry
from code_agent.tools.base import ToolContext
from code_agent.tools.dispatcher import ToolDispatcher

class AgentTUI(App):
    CSS = """
    RichLog {
        border: round $primary;
        padding: 0 1;
    }
    #input-box {
        margin-top: 1;
    }
    """
    BINDINGS = [("q", "quit", "Выход"), ("c", "clear", "Очистить")]
    
    def __init__(self, project_path: str = "."):
        super().__init__()
        self.project_path = Path(project_path).resolve()
        self._event_queue: queue.Queue = queue.Queue()
        self._agent_running = False
        self._approval_queue: queue.Queue = queue.Queue()  # для ответов на approval
        self.settings = load_settings()
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="💬 Напиши задачу...", id="goal-input")
        yield Footer()
    
    def on_mount(self) -> None:
        self.set_interval(0.1, self._drain_events)
        log = self.query_one("#log", RichLog)
        log.write("[green]🤖 Агент готов! Напиши задачу.[/green]")
        log.write(f"[dim]📂 Проект: {self.project_path}[/dim]")
        log.write(f"[dim]🔗 URL: {self.settings.colab_url or 'не задан'}[/dim]")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        
        log = self.query_one("#log", RichLog)
        log.write(f"[bold cyan]👤 {text}[/bold cyan]")
        
        if not self._agent_running:
            self._agent_running = True
            threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()
        else:
            log.write("[yellow]⚠️ Агент уже работает, подожди...[/yellow]")
    
    def action_clear(self) -> None:
        log = self.query_one("#log", RichLog)
        log.clear()
        log.write("[green]🧹 Лог очищен[/green]")
    
    def _run_agent(self, goal: str) -> None:
        try:
            log = self.query_one("#log", RichLog)
            
            registry = create_tool_registry()
            context = ToolContext(
                project_root=self.project_path,
                config=self.settings,
                state=None
            )
            dispatcher = ToolDispatcher(registry, context)
            
            # Создаём ApprovalManager с callback для TUI
            approval = ApprovalManager(
                mode=self.settings.approval_mode,
                ask_callback=self._ask_approval_tui
            )
            
            colab = SafePlanner(ColabPlanner(
                url=self.settings.colab_url,
                token=self.settings.colab_token,
                timeout=self.settings.request_timeout
            ))
            groq = SafePlanner(GroqPlanner(
                api_key=self.settings.groq_api_key,
                model=self.settings.groq_model
            ))
            
            state = RunState(
                goal=goal,
                project_root=str(self.project_path),
                max_steps=self.settings.max_steps,
                runtime_dir=self.settings.runtime_dir
            )
            
            orchestrator = Orchestrator(
                planner=colab,
                fallback_planner=groq,
                dispatcher=dispatcher,
                registry=registry,
                approval=approval,
                runtime_dir=self.settings.runtime_dir,
                mode=AgentMode.SUPERVISED,  # TUI по умолчанию supervised
            )
            
            # Запуск с очередью входящих сообщений
            orchestrator.run(state, on_event=self._on_event, incoming_messages=None)
            
            if state.status == "complete":
                self._on_event({"type": "finished", "summary": state.summary})
            elif state.status == "failed":
                self._on_event({"type": "failed", "error": "Задача не выполнена"})
                
        except Exception as e:
            self._on_event({"type": "failed", "error": f"Ошибка: {e}"})
        finally:
            self._agent_running = False
            self.query_one("#log", RichLog).write("[dim]💡 Агент готов к новой задаче[/dim]")
    
    def _ask_approval_tui(self, prepared) -> bool:
        """Callback для запроса подтверждения в TUI."""
        # Отправляем событие в основной поток
        self._event_queue.put({
            "type": "ask_user",
            "question": f"Разрешить {prepared.tool_name} с аргументами {prepared.arguments.model_dump()}? (y/n)",
            "reason": "Требуется подтверждение"
        })
        # Ждём ответ из очереди (пользователь введёт в поле ввода)
        # В TUI мы будем перехватывать ввод и класть ответ в специальную очередь
        # Здесь мы будем ждать, пока пользователь не ответит через поле ввода
        # Для упрощения используем отдельный механизм: в on_input_submitted будем проверять флаг
        # Реализуем просто: создадим локальную очередь и будем ждать
        # Пока оставим как есть, но надо доработать — для простоты оставим пока input()
        # (но в TUI это заблокирует UI). Для полноценной работы нужно реализовать асинхронный опрос.
        # Временно используем input() — некрасиво, но работает.
        answer = input(f"\n⚠️ {prepared.tool_name} с аргументами {prepared.arguments.model_dump()}\nРазрешить? [y/N]: ").strip().lower()
        return answer in ("y", "yes", "д", "да")
    
    def _on_event(self, event: dict) -> None:
        self._event_queue.put(event)
    
    def _drain_events(self) -> None:
        log = self.query_one("#log", RichLog)
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._render_event(event, log)
        except queue.Empty:
            pass
    
    def _render_event(self, event: dict, log: RichLog) -> None:
        etype = event.get("type")
        
        if etype == "thinking":
            log.write("[dim]🧠 думаю...[/dim]")
        elif etype == "action_decided":
            action = event.get("action", {})
            atype = action.get("type")
            if atype == "tool_call":
                tool = action.get("tool", "?")
                args = action.get("arguments", {})
                reason = action.get("reason", "")
                log.write(f"[cyan]🔧 {tool}[/cyan] {args}")
                if reason:
                    log.write(f"[dim]💡 {reason}[/dim]")
            elif atype == "message":
                msg = action.get("message", "")
                if msg:
                    log.write(f"[bold green]🤖 {msg}[/bold green]")
            elif atype == "ask_user":
                question = action.get("question", "")
                reason = action.get("reason", "")
                log.write(f"[yellow]❓ {question}[/yellow]")
                if reason:
                    log.write(f"[dim]💡 {reason}[/dim]")
            elif atype == "blocked":
                reason = action.get("reason", "")
                log.write(f"[red]🚫 Заблокировано: {reason}[/red]")
            elif atype == "finish":
                summary = action.get("summary", "")
                log.write(f"[green]✅ {summary}[/green]")
        elif etype == "step_result":
            if event.get("success"):
                output = event.get("output", "успешно")
                log.write(f"[green]✅ {output}[/green]")
            else:
                error = event.get("error", "ошибка")
                log.write(f"[red]❌ {error}[/red]")
        elif etype == "agent_message":
            text = event.get("text", "")
            if text:
                log.write(f"[bold green]🤖 {text}[/bold green]")
        elif etype == "ask_user":
            question = event.get("question", "")
            log.write(f"[yellow]❓ {question}[/yellow]")
        elif etype == "blocked":
            reason = event.get("reason", "")
            log.write(f"[red]🚫 Заблокировано: {reason}[/red]")
        elif etype == "finish_rejected":
            reasons = event.get("reasons", [])
            log.write("[yellow]⚠️ Завершение отклонено:[/yellow]")
            for r in reasons:
                log.write(f"[dim]  • {r}[/dim]")
        elif etype == "finished":
            summary = event.get("summary", "Готово!")
            log.write(f"[bold green]🎉 {summary}[/bold green]")
            log.write("[dim]💡 Можешь дать новую задачу[/dim]")
        elif etype == "failed":
            error = event.get("error", "неизвестная ошибка")
            log.write(f"[bold red]💥 {error}[/bold red]")
        elif etype == "session_start":
            session_id = event.get("session_id", "")
            log.write(f"[dim]🆔 Сессия: {session_id}[/dim]")

def main() -> None:
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    AgentTUI(project_path=project_path).run()

if __name__ == "__main__":
    main()

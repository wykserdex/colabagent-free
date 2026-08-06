import time
import logging
from typing import Callable, Optional, List, Dict, Any
from enum import Enum

from code_agent.models import AgentAction
from code_agent.planners.base import Planner
from code_agent.policy.policy_engine import PolicyEngine, ActionStatus
from code_agent.prompts import format_history
from code_agent.state import RunState, Phase
from code_agent.tools.dispatcher import ToolDispatcher
from code_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)
EventCallback = Callable[[dict], None]

class AgentMode(str, Enum):
    AUTONOMOUS = "autonomous"
    SUPERVISED = "supervised"
    REVIEW = "review"

class Orchestrator:
    def __init__(
        self,
        planner: Planner,
        fallback_planner: Optional[Planner] = None,
        dispatcher: Optional[ToolDispatcher] = None,
        registry: Optional[ToolRegistry] = None,
        runtime_dir: str = "runtime",
        approval=None,
        mode: AgentMode = AgentMode.SUPERVISED,
    ):
        self.planner = planner
        self.fallback_planner = fallback_planner
        self.dispatcher = dispatcher
        self.registry = registry
        self.runtime_dir = runtime_dir
        self.approval = approval
        self.mode = mode
        # PolicyEngine раньше существовал отдельно (policy/policy_engine.py) и
        # никогда не вызывался — весь gating шёл только через tool.get_risk().
        # AgentMode ("autonomous"/"supervised"/"review") специально совпадает
        # по значениям с режимами PolicyEngine, так что маппинг тривиальный.
        self.policy_engine = PolicyEngine(mode=self.mode.value)
    
    def run(self, state: RunState, on_event: Optional[EventCallback] = None, incoming_messages=None) -> RunState:
        def emit(event: dict) -> None:
            if on_event:
                on_event(event)
        
        emit({"type": "session_start", "session_id": state.session_id})
        
        while state.step < state.max_steps and state.status == "running":
            # Обработка входящих сообщений от пользователя (для TUI)
            if incoming_messages is not None:
                import queue as _queue
                while True:
                    try:
                        user_text = incoming_messages.get_nowait()
                    except _queue.Empty:
                        break
                    state.history.append({
                        "timestamp": time.time(), "source": "user",
                        "action": {"type": "user_message", "text": user_text},
                        "result": {"success": True, "output": user_text},
                    })
                    emit({"type": "user_message", "text": user_text})

            # Проверяем завершение
            can_finish, reasons = state.can_finish()
            if can_finish:
                state.status = "complete"
                emit({"type": "finished", "summary": state.summary or "Готово"})
                break
            
            # 1. Очевидные шаги
            deterministic = self._deterministic_action(state)
            if deterministic:
                emit({"type": "thinking", "step": state.step, "deterministic": True})
                self._execute_action(state, deterministic, emit)
                state.step += 1
                state.save(self.runtime_dir)
                continue
            
            # 2. Проверяем циклы
            loop = state.detect_loop()
            if loop:
                emit({"type": "failed", "error": loop})
                state.status = "failed"
                break
            
            # 3. Формируем контекст
            context = self._build_context(state)
            
            # 4. Получаем динамический список инструментов
            allowed_tools = self._get_allowed_tools(state)
            tools_schema = self._get_tools_schemas(allowed_tools)
            
            emit({"type": "thinking", "step": state.step, "allowed_tools": allowed_tools})
            
            # 5. Получаем действие
            action = self._get_action_with_repair(state, context, tools_schema)
            
            if not action:
                emit({"type": "failed", "error": "Не удалось получить действие"})
                break
            
            # 6. Проверяем что инструмент в списке разрешенных
            if action.type == "tool_call" and action.tool not in allowed_tools:
                emit({"type": "blocked", "reason": f"Инструмент {action.tool} недоступен на этой фазе"})
                state.add_feedback(f"Инструмент {action.tool} недоступен. Доступны: {allowed_tools}")
                state.step += 1
                continue
            
            # 7. Проверяем избыточность
            redundant, reason = state.is_redundant(
                action.tool or action.type,
                action.arguments or {}
            )
            if redundant:
                state.add_feedback(reason)
                emit({"type": "step_result", "success": False, "error": reason})
                state.step += 1
                continue
            
            # 8. Выполняем
            self._execute_action(state, action, emit)
            state.step += 1
            state.save(self.runtime_dir)
        
        if state.status == "running":
            emit({"type": "step_limit_reached", "step": state.step})
            state.status = "failed"
        
        return state
    
    def _get_allowed_tools(self, state: RunState) -> List[str]:
        always = ["filesystem.list_files", "filesystem.read_file", "search.search_text"]
        phase = state.phase.value if isinstance(state.phase, Phase) else state.phase
        
        if phase == "discovery":
            return always
        if phase == "implementation":
            return always + ["filesystem.write_file", "code.apply_patch", "code.run_script"]
        if phase == "verification":
            return always + ["tests.run", "code.run_script"]
        if phase == "review":
            return ["filesystem.read_file", "git.status", "git.diff", "tests.run"]
        if phase == "completion":
            return ["git.status", "git.diff"]
        
        return ["filesystem.list_files", "filesystem.read_file", "filesystem.write_file",
                "code.run_script", "code.apply_patch", "tests.run", "git.status", "git.diff"]
    
    def _get_tools_schemas(self, allowed_tools: List[str]) -> List[dict]:
        if not self.registry:
            return []
        all_schemas = self.registry.schemas()
        allowed_names = set(allowed_tools)
        return [s for s in all_schemas if s.get("name") in allowed_names]
    
    def _build_context(self, state: RunState) -> dict:
        history_text = format_history(state.history, window=8)
        
        # Автоопределение фазы
        phase = state.phase.value if isinstance(state.phase, Phase) else "discovery"
        if state.step < 2 and not state.changed_files:
            phase = "discovery"
        elif state.changed_files and not state.tests_run:
            phase = "implementation"
        elif state.tests_run and not state.tests_passed:
            phase = "verification"
        elif state.tests_run and state.tests_passed and not state.diff_reviewed:
            phase = "review"
        elif state.can_finish()[0]:
            phase = "completion"
        
        # Обновляем фазу в состоянии
        try:
            state.phase = Phase(phase)
        except ValueError:
            state.phase = Phase.DISCOVERY
        
        return {
            "history_text": history_text,
            "phase": phase,
            "phase_hint": self._get_phase_hint(phase, state),
            "step": state.step,
            "max_steps": state.max_steps,
            "changed_files": list(state.changed_files),
            "tests_run": state.tests_run,
            "tests_passed": state.tests_passed,
            "feedback": state.feedback[-3:],
            "can_finish": state.can_finish()[0],
            "finish_reasons": state.can_finish()[1],
            "artifacts": {
                path: {"hash": a.content_hash[:8], "preview": a.content_preview[:100]}
                for path, a in list(state.artifacts.items())[-5:]
            },
        }
    
    def _get_phase_hint(self, phase: str, state: RunState) -> str:
        hints = {
            "discovery": "Изучи структуру проекта: посмотри файлы и папки.",
            "implementation": "Внеси одно точечное изменение.",
            "verification": f"Исправь ошибку: {state.unresolved_errors[-1] if state.unresolved_errors else 'проверь тесты'}",
            "review": "Проверь изменения через git.diff.",
            "completion": "Все критерии выполнены. Можно завершать.",
        }
        return hints.get(phase, "Выбери следующее действие.")
    
    def _deterministic_action(self, state: RunState) -> Optional[AgentAction]:
        if state.step == 0:
            return AgentAction(
                type="tool_call",
                tool="filesystem.list_files",
                arguments={"path": ".", "max_depth": 3},
                reason="Первичное изучение структуры проекта"
            )
        if state.changed_files and not state.tests_run:
            return AgentAction(
                type="tool_call",
                tool="tests.run",
                arguments={"targets": ["tests/"], "extra_args": ["-q"]},
                reason="Проверка внесённых изменений"
            )
        if state.tests_run and state.tests_passed and not state.diff_reviewed:
            return AgentAction(
                type="tool_call",
                tool="git.diff",
                arguments={"stat_only": False},
                reason="Проверка итоговых изменений"
            )
        return None
    
    def _get_action_with_repair(self, state: RunState, context: dict, tools_schema: list) -> Optional[AgentAction]:
        try:
            action = self.planner.next_action(state.goal, context, tools_schema)
            if action and action.type:
                return action
        except Exception as e:
            logger.warning(f"Основной planner ошибка: {e}")
        
        if self.fallback_planner:
            try:
                logger.info("🔄 Fallback на Groq...")
                action = self.fallback_planner.next_action(state.goal, context, tools_schema)
                if action and action.type:
                    return action
            except Exception as e:
                logger.warning(f"Fallback ошибка: {e}")
        
        return None
    
    def _execute_action(self, state: RunState, action: AgentAction, emit: EventCallback) -> None:
        emit({"type": "action_decided", "action": action.model_dump()})
        
        if action.type == "message":
            msg = action.message or "Агент не дал ответа"
            state.history.append({
                "timestamp": time.time(),
                "source": "agent",
                "action": action.model_dump(),
                "result": {"success": True, "output": msg},
            })
            emit({"type": "agent_message", "text": msg})
            return
        
        if action.type == "finish":
            can_finish, reasons = state.can_finish()
            if can_finish:
                state.status = "complete"
                state.summary = action.summary or "Готово"
                emit({"type": "finished", "summary": state.summary})
            else:
                state.add_feedback(f"Завершение отклонено: {', '.join(reasons)}")
                emit({"type": "finish_rejected", "reasons": reasons})
            return
        
        if action.type == "ask_user":
            state.pending_approval = True
            emit({"type": "ask_user", "question": action.question, "reason": action.reason})
            return
        
        if action.type == "blocked":
            state.blocked = True
            state.blocked_reason = action.reason
            state.status = "blocked"
            emit({"type": "blocked", "reason": action.reason})
            return
        
        if action.type == "tool_call" and self.dispatcher:
            try:
                prepared = self.dispatcher.prepare(action.tool, action.arguments)
            except Exception as e:
                state.add_feedback(f"Ошибка подготовки: {e}")
                emit({"type": "step_result", "success": False, "error": str(e)})
                return

            from code_agent.models import RiskLevel

            # Два независимых слоя: tool-level risk (SAFE/REVIEW/FORBIDDEN,
            # захардкожен в каждом Tool.default_risk) и PolicyEngine
            # (запрещённые пути, точная карта tool -> action_key, режимы).
            # Берём более строгий результат из двух.
            policy_decision = self.policy_engine.check_action(action.tool, action.arguments or {})

            is_forbidden = prepared.risk == RiskLevel.FORBIDDEN or policy_decision.status == ActionStatus.DENY
            if is_forbidden:
                reason = (
                    policy_decision.reason
                    if policy_decision.status == ActionStatus.DENY
                    else "запрещено safety-политикой"
                )
                state.add_feedback(f"Действие {action.tool} запрещено: {reason}")
                emit({"type": "step_result", "success": False, "error": "forbidden", "reason": reason})
                return

            needs_approval = prepared.risk == RiskLevel.REVIEW or policy_decision.status == ActionStatus.REQUEST_APPROVAL
            if needs_approval:
                if self.approval is None:
                    state.add_feedback(f"{action.tool} требует подтверждения, но approval не настроен")
                    emit({"type": "step_result", "success": False, "error": "approval_not_configured"})
                    return
                try:
                    self.approval.require(prepared)
                except Exception as e:
                    state.add_feedback(f"Пользователь отклонил: {e}")
                    emit({"type": "step_result", "success": False, "error": str(e)})
                    return

            try:
                result = self.dispatcher.execute(prepared)
                state.record_action(action.model_dump(), result.model_dump())
                if result.success:
                    emit({"type": "step_result", "success": True, "output": result.output})
                    # Если это запись файла, добавляем артефакт
                    if action.tool == "filesystem.write_file":
                        path = action.arguments.get("path", "")
                        content = action.arguments.get("content", "")
                        if path:
                            state.add_artifact(path, content)
                            state.changed_files.add(path)
                else:
                    error_sig = state.error_signature(result.model_dump())
                    state.error_attempts[error_sig] = state.error_attempts.get(error_sig, 0) + 1
                    state.add_feedback(f"Ошибка: {result.error}")
                    emit({"type": "step_result", "success": False, "error": result.error})
            except Exception as e:
                state.add_feedback(f"Ошибка выполнения: {e}")
                emit({"type": "step_result", "success": False, "error": str(e)})

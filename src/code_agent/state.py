from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Set, Optional, Tuple
from pathlib import Path
import json
import time
import hashlib

from code_agent.safety.redactor import redact

class Phase(str, Enum):
    DISCOVERY = "discovery"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"
    REVIEW = "review"
    COMPLETION = "completion"

LOOP_REPEAT_THRESHOLD = 3

@dataclass
class Artifact:
    """Информация о созданном/изменённом артефакте."""
    content_hash: str
    content_preview: str

@dataclass
class RunState:
    goal: str = ""
    project_root: str = "."
    step: int = 0
    max_steps: int = 999
    status: str = "running"
    phase: Phase = Phase.DISCOVERY
    summary: str = ""
    history: List[Dict] = field(default_factory=list)
    artifacts: Dict[str, Artifact] = field(default_factory=dict)  # теперь с типом Artifact
    changed_files: Set[str] = field(default_factory=set)
    unresolved_errors: List[str] = field(default_factory=list)
    tests_run: bool = False
    tests_passed: bool = False
    diff_reviewed: bool = False
    feedback: List[str] = field(default_factory=list)
    pending_approval: bool = False
    blocked: bool = False
    blocked_reason: str = ""
    error_attempts: Dict[str, int] = field(default_factory=dict)
    session_id: str = ""
    runtime_dir: str = "runtime"
    
    def __post_init__(self):
        if not self.session_id:
            self.session_id = f"session_{int(time.time())}"
    
    def check_limits(self) -> Tuple[bool, List[str]]:
        blockers = []
        if self.step >= self.max_steps:
            blockers.append(f"Достигнут лимит шагов ({self.step}/{self.max_steps})")
        loop_sig = self.detect_loop()
        if loop_sig:
            blockers.append(f"Обнаружено зацикливание: {loop_sig}")
        return (len(blockers) == 0), blockers
    
    def detect_loop(self) -> Optional[str]:
        tool_calls = [
            h for h in self.history
            if h.get("action", {}).get("type") == "tool_call"
        ]
        if len(tool_calls) < LOOP_REPEAT_THRESHOLD:
            return None

        last_n = tool_calls[-LOOP_REPEAT_THRESHOLD:]
        signatures = {self._call_signature(h["action"]) for h in last_n}
        if len(signatures) == 1:
            return signatures.pop()
        return None

    @staticmethod
    def _call_signature(action: dict) -> str:
        tool = action.get("tool", "")
        args = action.get("args") or action.get("arguments") or {}
        try:
            args_repr = json.dumps(args, sort_keys=True, ensure_ascii=False)
        except TypeError:
            args_repr = str(args)
        return f"{tool}:{args_repr}"
    
    def error_signature(self, result: dict) -> str:
        error = result.get("error") or result.get("error_type") or ""
        return hashlib.sha256(str(error).encode()).hexdigest()[:12]
    
    def record_action(self, action: dict, result: dict):
        self.history.append({
            "timestamp": time.time(),
            "action": redact(action),
            "result": redact(result),
        })
        if action.get("type") == "tool_call":
            self.step += 1
    
    def add_feedback(self, message: str):
        self.feedback.append(message)
    
    def is_redundant(self, tool: str, args: dict) -> Tuple[bool, str]:
        signature = self._call_signature({"tool": tool, "arguments": args})
        for entry in self.history:
            action = entry.get("action", {})
            result = entry.get("result", {})
            if action.get("type") != "tool_call":
                continue
            if self._call_signature(action) == signature and result.get("success"):
                return True, f"{tool} с такими же аргументами уже успешно выполнялся"
        return False, ""
    
    def save(self, runtime_dir: str = None):
        target_dir = Path(runtime_dir or self.runtime_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        session_hash = hashlib.sha256(self.session_id.encode()).hexdigest()[:8]
        target_file = target_dir / f"state_{session_hash}.json"

        payload = asdict(self)
        payload["phase"] = self.phase.value if isinstance(self.phase, Phase) else self.phase
        payload["changed_files"] = list(self.changed_files)
        # Преобразуем artifacts в словарь для сериализации
        payload["artifacts"] = {k: {"content_hash": v.content_hash, "content_preview": v.content_preview} for k, v in self.artifacts.items()}

        tmp_file = target_file.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
        tmp_file.replace(target_file)

    # ----- НОВЫЕ МЕТОДЫ -----
    def can_finish(self) -> Tuple[bool, List[str]]:
        """Проверяет, достигнута ли цель."""
        reasons = []
        if self.tests_run and self.tests_passed and self.diff_reviewed:
            return True, []
        if not self.tests_run:
            reasons.append("Тесты не запущены")
        elif not self.tests_passed:
            reasons.append("Тесты не пройдены")
        if not self.diff_reviewed:
            reasons.append("Изменения не проверены (git.diff)")
        return False, reasons

    def repeated_actions(self) -> int:
        """Максимальное количество повторений одного и того же действия подряд."""
        tool_calls = [
            h for h in self.history
            if h.get("action", {}).get("type") == "tool_call"
        ]
        if len(tool_calls) < 2:
            return 0
        max_repeat = 1
        cur_repeat = 1
        prev_sig = self._call_signature(tool_calls[0].get("action", {}))
        for entry in tool_calls[1:]:
            sig = self._call_signature(entry.get("action", {}))
            if sig == prev_sig:
                cur_repeat += 1
                max_repeat = max(max_repeat, cur_repeat)
            else:
                cur_repeat = 1
            prev_sig = sig
        return max_repeat

    def repeated_errors(self) -> int:
        """Максимальное количество повторений одной и той же ошибки подряд."""
        errors = [
            h for h in self.history
            if h.get("result", {}).get("success") is False
        ]
        if len(errors) < 2:
            return 0
        max_repeat = 1
        cur_repeat = 1
        prev_sig = self.error_signature(errors[0].get("result", {}))
        for entry in errors[1:]:
            sig = self.error_signature(entry.get("result", {}))
            if sig == prev_sig:
                cur_repeat += 1
                max_repeat = max(max_repeat, cur_repeat)
            else:
                cur_repeat = 1
            prev_sig = sig
        return max_repeat

    def steps_without_progress(self) -> int:
        """Количество шагов без изменения файлов или прогресса."""
        # Если нет изменений и тесты не запускались, считаем застой
        if len(self.changed_files) == 0 and not self.tests_run:
            # Проверяем, были ли вообще попытки что-то сделать
            tool_calls = [h for h in self.history if h.get("action", {}).get("type") == "tool_call"]
            if len(tool_calls) > 3:
                return self.step - len(self.changed_files)  # упрощённо
        return 0

    def add_artifact(self, path: str, content: str):
        """Добавляет артефакт с хешем и превью."""
        h = hashlib.sha256(content.encode()).hexdigest()[:8]
        preview = content[:200] + "..." if len(content) > 200 else content
        self.artifacts[path] = Artifact(content_hash=h, content_preview=preview)

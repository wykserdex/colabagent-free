"""
memory/decision_logger.py — логирование решений агента
Сохраняет принятые решения для предотвращения повторения одних и тех же действий
"""
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from code_agent.safety.redactor import redact


class Decision(BaseModel):
    """Модель принятого решения"""
    decision: str
    reason: str
    file: Optional[str] = None
    tool: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    context: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return self.model_dump()


class DecisionLogger:
    """Логгер решений агента"""
    
    def __init__(self, runtime_dir: str = "runtime"):
        self.runtime_dir = Path(runtime_dir)
        self.decisions_file = self.runtime_dir / "decisions.json"
        self.decisions: List[Decision] = []
        self._load_decisions()
    
    def _load_decisions(self):
        """Загружает решения из файла"""
        if self.decisions_file.exists():
            try:
                with open(self.decisions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.decisions = [Decision(**d) for d in data]
            except (json.JSONDecodeError, Exception):
                self.decisions = []
    
    def _save_decisions(self):
        """Сохраняет решения в файл"""
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with open(self.decisions_file, 'w', encoding='utf-8') as f:
            json.dump([d.to_dict() for d in self.decisions], f, indent=2, ensure_ascii=False)
    
    def log_decision(self, decision: str, reason: str, file: str = None, 
                     tool: str = None, context: dict = None):
        """
        Логирует принятое решение
        
        Args:
            decision: Текст решения
            reason: Причина принятия решения
            file: Связанный файл (если есть)
            tool: Использованный инструмент (если есть)
            context: Дополнительный контекст
        """
        dec = Decision(
            decision=decision,
            reason=reason,
            file=file,
            tool=tool,
            context=redact(context or {})
        )
        self.decisions.append(dec)
        self._save_decisions()
    
    def find_similar_decisions(self, query: str, threshold: float = 0.7) -> List[Decision]:
        """
        Ищет похожие решения
        
        Args:
            query: Текст запроса для поиска
            threshold: Порог схожести (0-1)
        
        Returns:
            Список похожих решений
        """
        # Простой поиск по подстроке (можно улучшить с embeddings)
        query_lower = query.lower()
        results = []
        
        for dec in self.decisions:
            if (query_lower in dec.decision.lower() or 
                query_lower in dec.reason.lower()):
                results.append(dec)
        
        return results
    
    def has_similar_decision(self, query: str, threshold: float = 0.7) -> bool:
        """Проверяет, есть ли уже похожее решение"""
        return len(self.find_similar_decisions(query, threshold)) > 0
    
    def get_recent_decisions(self, limit: int = 10) -> List[Decision]:
        """Получает последние N решений"""
        return self.decisions[-limit:]
    
    def clear(self):
        """Очищает все решения"""
        self.decisions = []
        self._save_decisions()

"""
infrastructure/history_summary.py — создание summary из истории
"""
import json
from typing import List, Dict, Any


def summarize_history(history: List[Dict], max_entries: int = 8) -> str:
    """
    Создает краткое резюме из истории для передачи в промпт
    """
    if len(history) <= max_entries:
        # Если история маленькая — возвращаем как есть
        lines = []
        for entry in history[-max_entries:]:
            source = entry.get("source", "system")
            action = entry.get("action", {})
            result = entry.get("result", {})
            
            if source == "user":
                lines.append(f"[user] {action.get('text', '')}")
            elif source == "agent":
                if result.get("success"):
                    lines.append(f"[agent] ✅ {result.get('output', 'ok')[:200]}")
                else:
                    lines.append(f"[agent] ❌ {result.get('error', 'error')[:200]}")
            elif source == "system":
                lines.append(f"[system] {result.get('output', '')[:200]}")
        return "\n".join(lines)
    
    # Если история большая — делаем summary
    lines = []
    
    # Последние 5 действий в деталях
    lines.append("### Последние действия:")
    for entry in history[-5:]:
        source = entry.get("source", "system")
        action = entry.get("action", {})
        result = entry.get("result", {})
        
        if source == "user":
            lines.append(f"[user] {action.get('text', '')}")
        elif source == "agent":
            if result.get("success"):
                lines.append(f"[agent] ✅ {result.get('output', 'ok')[:200]}")
            else:
                lines.append(f"[agent] ❌ {result.get('error', 'error')[:200]}")
        elif source == "system":
            lines.append(f"[system] {result.get('output', '')[:200]}")
    
    # Собираем статистику
    total_actions = len([e for e in history if e.get("source") == "agent"])
    successful = len([e for e in history if e.get("source") == "agent" and e.get("result", {}).get("success")])
    failed = total_actions - successful
    
    lines.append(f"\n### Статистика:")
    lines.append(f"- Всего действий: {total_actions}")
    lines.append(f"- Успешно: {successful}")
    lines.append(f"- Ошибок: {failed}")
    
    return "\n".join(lines)

def format_history(history: list, window: int = 8) -> str:
    if not history:
        return "(пока ничего не делалось)"
    
    lines = []
    for h in history[-window:]:
        source = h.get("source", "")
        action = h["action"]
        result = h["result"]
        
        if source == "user":
            lines.append(f"👤 {action.get('text', '')}")
            continue
        
        if action.get("type") == "message":
            lines.append(f"🤖 {result.get('output', '')}")
            continue
        
        status = "✅" if result.get("success") else "❌"
        tool = action.get("tool") or action.get("type")
        args = action.get("arguments", {})
        lines.append(f"{status} {tool} {args}")
        
        output = result.get("output") or result.get("error") or ""
        if output:
            lines.append(f"   → {output[:200]}")
    
    return "\n".join(lines)

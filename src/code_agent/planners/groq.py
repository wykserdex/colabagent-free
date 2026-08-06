import json
import re
import httpx
from code_agent.models import AgentAction
from code_agent.planners.base import Planner


class GroqPlanner(Planner):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b", timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
    
    def next_action(self, goal: str, context: dict, tools: list[dict]) -> AgentAction:
        try:
            prompt = self._build_prompt(goal, context, tools)
            
            response = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            raw = response.json()["choices"][0]["message"]["content"]
            raw = re.sub(r"```json\s*|```\s*", "", raw).strip()
            
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            
            data = json.loads(raw)
            return AgentAction.model_validate(data)
            
        except Exception as e:
            return AgentAction(
                type="message",
                message=f"⚠️ Groq fallback ошибка: {str(e)[:200]}"
            )
    
    def _build_prompt(self, goal: str, context: dict, tools: list[dict]) -> str:
        tools_desc = "\n".join(f"- {t['name']}: {t['description']}" for t in tools[:10])
        history = context.get("history_text", "")
        
        return f"""Ты — coding-агент (Groq fallback).

ЦЕЛЬ: {goal}

ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
{tools_desc}

ИСТОРИЯ:
{history}

Верни ОДИН JSON с действием.
Только JSON, без пояснений."""

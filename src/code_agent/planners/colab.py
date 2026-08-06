import json
import re
import requests
from code_agent.models import AgentAction
from code_agent.planners.base import Planner
from code_agent.config import load_settings


def _strip_markdown_fence(text: str) -> str:
    """Модель иногда оборачивает JSON в ```json ... ``` даже там где просили
    только чистый JSON — снимаем обёртку перед парсингом."""
    return re.sub(r"```json\s*|```\s*", "", text).strip()


class ColabPlanner(Planner):
    def __init__(self, url: str = None, token: str = "", timeout: int = 120):
        if not url:
            raise ValueError(
                "ColabPlanner: url не передан. Проверь AGENT_COLAB_URL в .env — "
                "и помни что Cloudflare-туннель МЕНЯЕТСЯ при каждом перезапуске "
                "Colab-ячейки, обновляй .env после каждого рестарта."
            )
        self.url = url.rstrip("/") + "/generate" if not url.rstrip("/").endswith("/generate") else url
        self.token = token
        self.timeout = timeout or load_settings().request_timeout

    def next_action(self, goal: str, context: dict, tools: list[dict]) -> AgentAction:
        prompt = self._build_prompt(goal, context, tools)
        
        try:
            response = requests.post(
                self.url,
                json={"text": prompt, "token": self.token},
                timeout=self.timeout
            )
            
            print(f"📥 Статус: {response.status_code}")
            
            if response.status_code != 200:
                return AgentAction(
                    type="message",
                    message=f"⚠️ Ошибка HTTP {response.status_code}"
                )
            
            # 🔥 ПАРСИМ JSON
            try:
                data = response.json()
                print(f"📥 Получено: {data}")
                
                # Проверяем что пришло
                if "type" in data:
                    # Это готовый AgentAction
                    return AgentAction.model_validate(data)
                
                if "response" in data:
                    # Это ответ с полем response
                    raw = _strip_markdown_fence(data["response"].strip())
                    if raw:
                        try:
                            action_data = json.loads(raw)
                            return AgentAction.model_validate(action_data)
                        except:
                            return AgentAction(
                                type="message",
                                message=raw[:500]
                            )
                
                # Если ничего не подошло
                return AgentAction(
                    type="message",
                    message=f"⚠️ Неизвестный формат: {data}"
                )
                
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                return AgentAction(
                    type="message",
                    message=f"⚠️ Ошибка парсинга: {response.text[:200]}"
                )
            
        except requests.exceptions.Timeout:
            print(f"❌ Таймаут после {self.timeout}с")
            return AgentAction(
                type="message",
                message=f"⚠️ Таймаут: модель не ответила за {self.timeout} секунд"
            )
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return AgentAction(
                type="message",
                message=f"⚠️ Ошибка: {str(e)[:200]}"
            )

    def _build_prompt(self, goal: str, context: dict, tools: list[dict]) -> str:
        # 🔥 МИНИМАЛЬНЫЙ ПРОМПТ
        tools_desc = "\n".join(f"- {t['name']}" for t in tools[:5])
        history = context.get("history_text", "")[-500:]  # Обрезаем историю
        
        return f"""Ты - агент. Делай ОДНО действие.

ЦЕЛЬ: {goal}

ИНСТРУМЕНТЫ:
{tools_desc}

ИСТОРИЯ:
{history}

Верни ТОЛЬКО JSON:
{{"type":"tool_call","tool":"имя","arguments":{{}},"reason":"зачем"}}
{{"type":"message","message":"текст"}}
{{"type":"finish","summary":"готово"}}

ДЕЙСТВУЙ!"""

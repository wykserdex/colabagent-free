"""
config.py — вся конфигурация читается из окружения/.env через pydantic-settings.
Никаких URL/токенов, зашитых прямо в код — Cloudflare-туннель МЕНЯЕТСЯ при каждом
перезапуске Colab-ячейки, хардкодить его бессмысленно и опасно (будет молча
использоваться мёртвый адрес, что и стало причиной 'пустых ответов').

Использование: обнови .env после каждого рестарта Colab-ячейки —
AGENT_COLAB_URL=https://новый-адрес.trycloudflare.com
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    colab_url: str = ""
    colab_token: str = ""

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    max_steps: int = 30
    request_timeout: int = 120
    process_timeout: int = 180
    max_output_chars: int = 30_000

    planner_temperature: float = 0.3
    repair_temperature: float = 0.0

    use_bwrap: bool = True
    allow_network: bool = False
    approval_mode: str = "ask"  # ask | auto | read-only

    runtime_dir: str = "runtime"


def load_settings() -> Settings:
    settings = Settings()
    if not settings.colab_url:
        print(
            "⚠️  AGENT_COLAB_URL не задан в .env! Без него агент не сможет "
            "связаться с Colab. Создай .env в корне проекта с содержимым:\n"
            "AGENT_COLAB_URL=https://твой-текущий-туннель.trycloudflare.com"
        )
    return settings

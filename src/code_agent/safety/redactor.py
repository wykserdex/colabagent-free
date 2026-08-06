"""
safety/redactor.py — вычищает секреты перед тем, как что-либо попадёт в
decisions.json, runtime/state_*.json или события, летящие в UI/логи.

decision_logger.py пишет context (в т.ч. сырые arguments тула) на диск как
есть. Если модель когда-нибудь передаст токен/ключ аргументом в shell.run
или write_file (например, при отладке .env), он осядет в runtime/ в
открытом виде — а runtime/ уже сейчас лежит в репозитории (.agent_backups
туда же). Redactor вызывается один раз, прямо перед записью/эмитом,
а не полагается на то, что каждый вызывающий код не забудет про секреты.
"""
import re
from typing import Any

# Имена ключей, значения которых считаем секретами целиком, независимо от содержимого
_SECRET_KEY_PATTERN = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|auth|session|credential|private[_-]?key)",
    re.IGNORECASE,
)

# Паттерны значений, похожих на секреты, даже если ключ не подсказал
_SECRET_VALUE_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),               # Google API key
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                   # OpenAI/Groq-style key
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),                  # Groq key
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),                  # GitHub PAT
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),          # Slack token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),    # PEM private key
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]

_REDACTED = "***REDACTED***"


def _redact_value(value: str) -> str:
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            return _REDACTED
    return value


def redact(obj: Any) -> Any:
    """Рекурсивно проходит dict/list/str и заменяет секреты на ***REDACTED***.
    Не мутирует исходный объект."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if isinstance(key, str) and _SECRET_KEY_PATTERN.search(key):
                result[key] = _REDACTED if value else value
            else:
                result[key] = redact(value)
        return result
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact(item) for item in obj)
    if isinstance(obj, str):
        return _redact_value(obj)
    return obj

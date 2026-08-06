"""
infrastructure/logging.py — настройка логирования
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = None, debug: bool = False) -> None:
    """Настраивает логирование"""
    
    # Создаем папку для логов
    if log_dir is None:
        log_dir = Path.home() / ".local/share/code-agent/logs"
    else:
        log_dir = Path(log_dir)
    
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "code-agent.log"
    
    # Корневой логгер
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Очищаем старые хендлеры
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # Консольный хендлер
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    console.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    root.addHandler(console)
    
    # Файловый хендлер с ротацией
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s "
            "%(name)s %(filename)s:%(lineno)d "
            "%(message)s"
        )
    )
    root.addHandler(file_handler)
    
    # Отключаем лишние логи от библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("textual").setLevel(logging.WARNING)
    
    # Логируем запуск
    root.info(f"📝 Логирование настроено: {log_file}")
    root.info(f"🐍 Python {sys.version}")

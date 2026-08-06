# ============================================================
# Docker-песочница для агента — изолирует всё что агент делает
# (pip install, запуск скриптов, файловые операции) от хост-системы.
# Единственное что видно снаружи — папка /workspace через volume mount.
# ============================================================
FROM python:3.11-slim

# --------- системные зависимости для запускаемого агентом кода ---------
# git — нужен для git.status/git.diff инструментов
# ripgrep — для search.search_text (без него фоллбэк на медленный python-поиск)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ripgrep \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --------- ставим сам агент как пакет (не просто копируем файлы) ---------
# pip install . использует pyproject.toml — это даёт entry point code-agent-tui,
# а не просто голые .py файлы без метаданных пакета
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir . 2>&1 | tail -30

# --------- непривилегированный пользователь ---------
# Даже внутри контейнера не работаем от root без необходимости — если
# что-то вырвется за пределы /workspace внутри самого контейнера (баг
# path_guard, например), root внутри контейнера всё ещё может натворить
# больше чем обычный пользователь
RUN useradd --create-home --shell /bin/bash agent
USER agent
WORKDIR /workspace

# --------- НИКАКИХ секретов/URL захардкоженных в образ ---------
# AGENT_COLAB_URL меняется при каждом рестарте Colab-ячейки — если зашить
# его в образ, придётся пересобирать образ на каждый рестарт. Передавай
# через --env-file .env или -e при docker run (см. docker-compose.yml)

ENTRYPOINT ["python", "-m", "code_agent.tui"]
CMD ["/workspace"]

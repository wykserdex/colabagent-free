#!/bin/bash

# ============================================
# Code Agent Runner — запускает агента в Docker
# ============================================

set -euo pipefail

# Цвета для красоты
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Code Agent Docker Runner${NC}"
echo "========================================"

# Корень репозитория вычисляется от расположения скрипта — раньше здесь был
# зашит абсолютный путь с чужой машины (/home/kali/Desktop/...), из-за чего
# скрипт падал у всех остальных на первой же строке.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_ROOT"

# Проверяем, собран ли образ
if ! docker image inspect code-agent:latest &>/dev/null; then
    echo -e "${YELLOW}📦 Образ не найден, собираю...${NC}"
    docker build -t code-agent .
    echo -e "${GREEN}✅ Образ собран!${NC}"
fi

# Проверяем аргументы
if [ $# -lt 1 ]; then
    echo -e "${YELLOW}⚠️  Не указана папка проекта${NC}"
    echo -e "Использование: ./run_agent.sh <путь_к_папке>"
    echo -e "Пример: ./run_agent.sh ~/projects/my_game"
    exit 1
fi

PROJECT_PATH="$1"
shift
mkdir -p "$PROJECT_PATH"
PROJECT_PATH=$(realpath "$PROJECT_PATH")

# Подхватываем .env из корня репозитория, если он есть, — иначе агент уедет
# в контейнер без URL туннеля и молча получит пустые ответы.
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
fi

: "${AGENT_COLAB_URL:=}"
: "${AGENT_COLAB_TOKEN:=}"
: "${AGENT_GROQ_API_KEY:=}"

if [ -z "$AGENT_COLAB_URL" ]; then
    echo -e "${RED}❌ AGENT_COLAB_URL не задан${NC}"
    echo -e "Запусти серверную ячейку (colab/server_cell.txt) и впиши в .env:"
    echo -e "  AGENT_COLAB_URL=https://<туннель>.trycloudflare.com"
    echo -e "  AGENT_COLAB_TOKEN=<токен из вывода ячейки>"
    echo -e "Напоминание: адрес меняется при каждом перезапуске Colab-ячейки."
    exit 1
fi

if [ -z "$AGENT_COLAB_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  AGENT_COLAB_TOKEN пуст — сервер ответит 401, если ячейка требует токен${NC}"
fi

echo -e "${BLUE}📂 Проект: ${PROJECT_PATH}${NC}"
echo -e "${BLUE}🔗 URL: ${AGENT_COLAB_URL}${NC}"
echo -e "${GREEN}🚀 Запускаю агента...${NC}"
echo "========================================"

# Запускаем контейнер. Токены пробрасываются из окружения, а не затираются
# пустыми строками, как было раньше.
docker run -it \
    --rm \
    --name code-agent \
    -v "$PROJECT_PATH:/workspace" \
    -e AGENT_COLAB_URL="$AGENT_COLAB_URL" \
    -e AGENT_COLAB_TOKEN="$AGENT_COLAB_TOKEN" \
    -e AGENT_GROQ_API_KEY="$AGENT_GROQ_API_KEY" \
    code-agent "$@"

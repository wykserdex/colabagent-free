#!/bin/bash

# ============================================
# Code Agent Runner — запускает агента в Docker
# ============================================

set -e

# Цвета для красоты
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Code Agent Docker Runner${NC}"
echo "========================================"

# Путь к проекту
AGENT_PATH="/home/kali/Desktop/code_agent (3)"
cd "$AGENT_PATH"

# Проверяем, собран ли образ
if ! docker image inspect code-agent:latest &>/dev/null; then
    echo -e "${YELLOW}📦 Образ не найден, собираю...${NC}"
    docker build -t code-agent .
    echo -e "${GREEN}✅ Образ собран!${NC}"
fi

# Проверяем аргументы
if [ -z "$1" ]; then
    echo -e "${YELLOW}⚠️  Не указана папка проекта${NC}"
    echo -e "Использование: ./run_agent.sh <путь_к_папке>"
    echo -e "Пример: ./run_agent.sh ~/projects/my_game"
    exit 1
fi

PROJECT_PATH="$1"
PROJECT_PATH=$(realpath "$PROJECT_PATH")

# Создаем папку если её нет
mkdir -p "$PROJECT_PATH"

# Проверяем URL
if [ -z "$AGENT_COLAB_URL" ]; then
    echo -e "${YELLOW}⚠️  AGENT_COLAB_URL не задан, использую дефолтный...${NC}"
    AGENT_COLAB_URL=""
fi

echo -e "${BLUE}📂 Проект: ${PROJECT_PATH}${NC}"
echo -e "${BLUE}🔗 URL: ${AGENT_COLAB_URL}${NC}"
echo -e "${GREEN}🚀 Запускаю агента...${NC}"
echo "========================================"

# Запускаем контейнер
docker run -it \
    --rm \
    --name code-agent \
    -v "$PROJECT_PATH:/workspace" \
    -e AGENT_COLAB_URL="$AGENT_COLAB_URL" \
    -e AGENT_COLAB_TOKEN="" \
    -e AGENT_GROQ_API_KEY="" \
    code-agent

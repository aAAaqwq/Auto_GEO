#!/bin/bash
# AutoGeo 更新脚本
# 拉取最新镜像并重新部署（零停机）

set -e

COMPOSE_FILE="${COMPOSE_FILE:-./docker-compose.prod.yml}"

# 颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}开始更新 AutoGeo...${NC}"

# 拉取最新镜像
echo "拉取最新镜像..."
docker-compose -f "$COMPOSE_FILE" pull backend

# 重新创建容器（零停机）
echo "重新部署服务..."
docker-compose -f "$COMPOSE_FILE" up -d --no-deps backend

# 等待健康检查
echo "等待服务就绪..."
sleep 5

for i in {1..12}; do
    if curl -sf http://localhost/api/health &>/dev/null; then
        echo -e "${GREEN}更新成功！${NC}"
        docker-compose -f "$COMPOSE_FILE" ps backend
        exit 0
    fi
    echo -n "."
    sleep 5
done

echo -e "${YELLOW}警告: 健康检查超时，请手动检查服务状态${NC}"
docker-compose -f "$COMPOSE_FILE" logs backend --tail 50

#!/bin/bash
# n8n 一键部署脚本 - 简化版

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 n8n 一键部署脚本${NC}"
echo "===================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

cd "$(dirname "$0")"

# 如果没有 .env 文件，自动创建
if [[ ! -f ".env" ]]; then
    echo -e "${YELLOW}⚠️  .env 文件不存在，创建默认配置...${NC}"

    # 获取服务器IP
    SERVER_IP=$(curl -s ip.sb 2>/dev/null || echo "localhost")

    # 生成随机密码
    DB_PASS=$(openssl rand -base64 20 2>/dev/null | tr -d "=" | cut -c1-20)
    REDIS_PASS=$(openssl rand -base64 20 2>/dev/null | tr -d "=" | cut -c1-20)
    N8N_PASS=$(openssl rand -base64 20 2>/dev/null | tr -d "=" | cut -c1-16)

    cat > ".env" << EOF
# n8n 配置 - 自动生成于 $(date)
# 请修改以下配置

# 你的服务器IP或域名（重要：用于webhook回调）
N8N_HOST=${SERVER_IP}
WEBHOOK_URL=http://${SERVER_IP}:5678

# 登录账号密码
N8N_USER=admin
N8N_PASSWORD=${N8N_PASS}

# 数据库密码（自动生成）
POSTGRES_PASSWORD=${DB_PASS}
REDIS_PASSWORD=${REDIS_PASS}
EOF

    echo -e "${GREEN}✅ 已创建 .env 文件${NC}"
    echo -e "${YELLOW}⚠️  请编辑 .env 文件修改配置（特别是 N8N_HOST），然后重新运行脚本${NC}"
    echo "   命令: nano .env"
    echo ""
    echo "当前生成的密码："
    echo "  n8n 登录密码: ${N8N_PASS}"
    exit 0
fi

# 加载配置
source ".env"

# 检查必要配置
if [[ -z "$N8N_HOST" || "$N8N_HOST" == "your-domain-or-ip" ]]; then
    echo -e "${RED}❌ 请编辑 .env 文件，设置 N8N_HOST 为你的服务器IP或域名${NC}"
    exit 1
fi

# 创建备份目录
mkdir -p backup

# 启动服务
echo -e "${GREEN}🐳 启动服务...${NC}"
docker-compose up -d

# 等待启动
echo -n "⏳ 等待服务就绪"
for i in {1..30}; do
    if curl -sf http://localhost:5678/healthz &>/dev/null || curl -sf http://localhost:5678/ &>/dev/null; then
        echo ""
        echo -e "${GREEN}✅ n8n 启动成功！${NC}"
        echo ""
        echo "===================="
        echo "📱 访问地址: http://${N8N_HOST}:5678"
        echo "👤 用户名: ${N8N_USER:-admin}"
        echo "🔑 密码: ${N8N_PASSWORD:-见 .env 文件}"
        echo "===================="
        echo ""
        echo "常用命令:"
        echo "  查看日志: docker-compose logs -f"
        echo "  停止服务: docker-compose down"
        echo "  重启服务: docker-compose restart"
        echo "  备份数据: docker-compose exec postgres pg_dump -U n8n n8n > backup/n8n_$(date +%Y%m%d).sql"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo -e "${RED}❌ 启动超时，查看日志:${NC}"
docker-compose logs --tail=30
echo ""
echo "如果一直失败，请检查:"
echo "  1. 端口 5678 是否被占用"
echo "  2. Docker 是否正常运行"
echo "  3. 配置文件是否正确"
exit 1

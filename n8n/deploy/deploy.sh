#!/bin/bash
# n8n 独立部署脚本
# 用法: ./deploy.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查环境
check_environment() {
    log_info "检查环境..."
    if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
        log_error "请先安装 Docker 和 Docker Compose"
        exit 1
    fi
    log_success "环境检查通过"
}

# 检查配置
check_config() {
    if [[ ! -f ".env" ]]; then
        log_error "配置文件不存在，请复制 .env.example 为 .env 并修改"
        exit 1
    fi
    log_success "配置检查通过"
}

# 生成密码（如果没有）
generate_passwords() {
    if ! grep -q "POSTGRES_PASSWORD=" .env || grep -q "POSTGRES_PASSWORD=your-postgres-password" .env; then
        log_info "生成 PostgreSQL 密码..."
        POSTGRES_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASS/" .env
        log_success "PostgreSQL 密码已生成"
    fi

    if ! grep -q "REDIS_PASSWORD=" .env || grep -q "REDIS_PASSWORD=your-redis-password" .env; then
        log_info "生成 Redis 密码..."
        REDIS_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        sed -i "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASS/" .env
        log_success "Redis 密码已生成"
    fi
}

# 启动服务
start_services() {
    log_info "启动 n8n 服务..."

    # 创建备份目录
    mkdir -p backup

    # 启动依赖服务
    docker-compose up -d postgres redis

    # 等待数据库就绪
    log_info "等待 PostgreSQL 就绪..."
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U n8n &>/dev/null; then
            log_success "PostgreSQL 已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done

    # 启动n8n
    docker-compose up -d n8n nginx

    log_success "n8n 服务已启动"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    for i in {1..20}; do
        if curl -sf http://localhost/health &>/dev/null; then
            log_success "健康检查通过"
            return 0
        fi
        echo -n "."
        sleep 3
    done

    log_error "健康检查失败"
    docker-compose logs n8n --tail 50
    return 1
}

# 显示信息
show_info() {
    echo ""
    echo "========================================"
    echo "  n8n 部署完成"
    echo "========================================"
    echo ""
    echo "管理界面: http://$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')"
    echo "Webhook地址: http://$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')/webhook/"
    echo ""
    echo "默认账号: admin"
    echo "默认密码: 见 .env 文件 N8N_PASSWORD"
    echo ""
    echo "容器状态:"
    docker-compose ps
    echo ""
    echo "常用命令:"
    echo "  查看日志: docker-compose logs -f n8n"
    echo "  停止服务: docker-compose down"
    echo "  备份数据: ./backup.sh"
    echo "========================================"
}

# 主函数
main() {
    echo "========================================"
    echo "  n8n 独立部署脚本"
    echo "========================================"
    echo ""

    check_environment
    check_config
    generate_passwords
    start_services
    health_check
    show_info
}

trap 'log_error "部署被中断"; exit 1' INT TERM

main "$@"

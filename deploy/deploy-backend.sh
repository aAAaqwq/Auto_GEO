#!/bin/bash
# AutoGeo 后端一键部署脚本
# 适用: 阿里云ECS Ubuntu/CentOS
# 用法: ./deploy-backend.sh [环境变量文件路径]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$SCRIPT_DIR/.env.backend}"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.backend.yml"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 未安装，请先安装"
        exit 1
    fi
}

check_environment() {
    log_info "检查环境..."
    check_command docker
    check_command docker-compose
    if ! docker info &> /dev/null; then
        log_error "Docker 未运行"
        exit 1
    fi
    log_success "环境检查通过"
}

check_config() {
    log_info "检查配置文件..."
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "环境变量文件不存在: $ENV_FILE"
        log_info "请复制 .env.backend.example 为 .env.backend 并修改配置"
        exit 1
    fi
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Docker Compose 文件不存在: $COMPOSE_FILE"
        exit 1
    fi
    source "$ENV_FILE"
    local required_vars=("DB_PASSWORD" "AUTO_GEO_ENCRYPTION_KEY" "N8N_WEBHOOK_URL" "DEEPSEEK_API_KEY")
    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "缺少必要的环境变量:"
        for var in "${missing_vars[@]}"; do echo "  - $var"; done
        exit 1
    fi
    log_success "配置检查通过"
}

prepare_directories() {
    log_info "准备数据目录..."
    mkdir -p "$SCRIPT_DIR/backups"
    mkdir -p "$SCRIPT_DIR/nginx/ssl"
    log_success "目录准备完成"
}

pull_images() {
    log_info "拉取镜像..."
    # 优先使用密码文件登录
    if [[ -n "$ALIYUN_ACR_PASSWORD_FILE" && -f "$ALIYUN_ACR_PASSWORD_FILE" ]]; then
        log_info "登录阿里云ACR..."
        docker login crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com \
            --username "${ALIYUN_ACR_USERNAME}" --password-file "$ALIYUN_ACR_PASSWORD_FILE" 2>/dev/null || log_warn "ACR登录失败"
    fi
    docker-compose -f "$COMPOSE_FILE" pull backend || log_warn "拉取镜像失败，使用本地镜像"
}

start_services() {
    log_info "启动服务..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres
    log_info "等待 PostgreSQL 就绪..."
    for i in {1..30}; do
        if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U autogeo &> /dev/null; then
            log_success "PostgreSQL 已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done
    docker-compose -f "$COMPOSE_FILE" up -d
    log_success "所有服务已启动"
}

run_migrations() {
    log_info "执行数据库迁移..."
    sleep 5
    docker-compose -f "$COMPOSE_FILE" exec -T backend alembic upgrade head || log_warn "迁移执行失败"
}

health_check() {
    log_info "健康检查..."
    local max_retries=10
    for i in $(seq 1 $max_retries); do
        if curl -sf http://localhost/api/health &> /dev/null; then
            log_success "API 健康检查通过"
            return 0
        fi
        echo -n "."
        sleep 3
    done
    log_error "健康检查失败"
    return 1
}

show_info() {
    local server_ip=$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')
    log_success "后端部署完成！"
    echo ""
    echo "========================================"
    echo "  AutoGeo 后端部署信息"
    echo "========================================"
    echo "API 地址:     http://${server_ip}/api"
    echo "健康检查:     http://${server_ip}/api/health"
    echo "API文档:      http://${server_ip}/docs"
    echo "========================================"
}

main() {
    echo "========================================"
    echo "  AutoGeo 后端部署脚本"
    echo "========================================"
    echo ""
    check_environment
    check_config
    prepare_directories
    pull_images
    start_services
    run_migrations
    health_check
    show_info
}

trap 'log_error "部署被中断"; exit 1' INT TERM
main "$@"

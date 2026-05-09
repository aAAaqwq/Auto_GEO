#!/bin/bash
# n8n 一键部署脚本
# 用法: ./deploy-n8n.sh [环境变量文件路径]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$SCRIPT_DIR/.env.n8n}"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.n8n.yml"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_environment() {
    log_info "检查环境..."
    if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
        log_error "Docker 或 docker-compose 未安装"
        exit 1
    fi
    log_success "环境检查通过"
}

check_config() {
    log_info "检查配置..."
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "环境变量文件不存在: $ENV_FILE"
        exit 1
    fi
    source "$ENV_FILE"
    local required_vars=("N8N_HOST" "N8N_PASSWORD" "POSTGRES_PASSWORD" "REDIS_PASSWORD")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            log_error "缺少必要的环境变量: $var"
            exit 1
        fi
    done
    log_success "配置检查通过"
}

deploy() {
    log_info "部署 n8n..."
    cd "$SCRIPT_DIR"
    docker-compose -f "$COMPOSE_FILE" up -d
    log_info "等待服务启动..."
    sleep 15
    log_success "n8n 部署完成"
}

show_info() {
    source "$ENV_FILE"
    log_success "部署信息："
    echo "访问地址: http://${N8N_HOST}:5678"
    echo "用户名: ${N8N_USER:-admin}"
    echo "初始密码: ${N8N_PASSWORD}"
}

main() {
    echo "========================================"
    echo "  n8n 部署脚本"
    echo "========================================"
    echo ""
    check_environment
    check_config
    deploy
    show_info
}

trap 'log_error "部署被中断"; exit 1' INT TERM
main "$@"

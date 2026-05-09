#!/bin/bash
# AutoGeo 后端一键部署脚本
# 适用: 阿里云ECS Ubuntu/CentOS
# 用法: ./deploy.sh [环境变量文件路径]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${1:-$PROJECT_DIR/.env}"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"

# 打印带颜色的信息
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 未安装，请先安装"
        exit 1
    fi
}

# 检查环境
check_environment() {
    log_info "检查环境..."

    check_command docker
    check_command docker-compose

    # 检查Docker是否运行
    if ! docker info &> /dev/null; then
        log_error "Docker 未运行，请启动 Docker 服务"
        exit 1
    fi

    log_success "环境检查通过"
}

# 检查配置文件
check_config() {
    log_info "检查配置文件..."

    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "环境变量文件不存在: $ENV_FILE"
        log_info "请复制 .env.example 为 .env 并修改配置"
        exit 1
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Docker Compose 文件不存在: $COMPOSE_FILE"
        exit 1
    fi

    # 检查必要的环境变量
    source "$ENV_FILE"

    local required_vars=("DB_PASSWORD" "AUTO_GEO_ENCRYPTION_KEY" "DEEPSEEK_API_KEY")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "缺少必要的环境变量:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi

    log_success "配置检查通过"
}

# 创建必要的目录
prepare_directories() {
    log_info "准备数据目录..."

    mkdir -p "$PROJECT_DIR/backups"
    mkdir -p "$PROJECT_DIR/nginx/ssl"

    log_success "目录准备完成"
}

# 拉取最新镜像
pull_images() {
    log_info "拉取最新镜像..."

    cd "$PROJECT_DIR"

    # 登录阿里云ACR（如果配置了密码文件）
    if [[ -n "$ALIYUN_ACR_PASSWORD_FILE" && -f "$ALIYUN_ACR_PASSWORD_FILE" ]]; then
        log_info "登录阿里云ACR..."
        docker login crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com \
            --username "${ALIYUN_ACR_USERNAME:-$ALIYUN_ACR_REGISTRY_USERNAME}" \
            --password-file "$ALIYUN_ACR_PASSWORD_FILE" 2>/dev/null || log_warn "ACR登录失败，尝试拉取公开镜像"
    elif [[ -n "$ALIYUN_ACR_USERNAME" && -n "$ALIYUN_ACR_PASSWORD" ]]; then
        log_warn "检测到环境变量密码，建议使用密码文件更安全"
        log_info "登录阿里云ACR..."
        printf '%s' "$ALIYUN_ACR_PASSWORD" | docker login crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com \
            -u "$ALIYUN_ACR_USERNAME" --password-stdin 2>/dev/null || log_warn "ACR登录失败，尝试拉取公开镜像"
    fi

    docker-compose -f "$COMPOSE_FILE" pull backend || {
        log_warn "拉取最新镜像失败，将使用本地镜像"
    }

    log_success "镜像拉取完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."

    cd "$PROJECT_DIR"

    # 先启动PostgreSQL
    log_info "启动 PostgreSQL..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres

    # 等待PostgreSQL就绪
    log_info "等待 PostgreSQL 就绪..."
    for i in {1..30}; do
        if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U autogeo &> /dev/null; then
            log_success "PostgreSQL 已就绪"
            break
        fi
        echo -n "."
        sleep 2
    done

    # 启动其他服务
    log_info "启动其他服务..."
    docker-compose -f "$COMPOSE_FILE" up -d

    log_success "所有服务已启动"
}

# 执行数据库迁移
run_migrations() {
    log_info "执行数据库迁移..."

    cd "$PROJECT_DIR"

    # 等待后端服务就绪
    sleep 5

    # 执行迁移
    docker-compose -f "$COMPOSE_FILE" exec -T backend alembic upgrade head || {
        log_warn "数据库迁移执行失败，可能需要手动处理"
        return 1
    }

    log_success "数据库迁移完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    cd "$PROJECT_DIR"

    # 检查容器状态
    local services=("postgres" "backend" "nginx")
    for service in "${services[@]}"; do
        local status
        status=$(docker-compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null)
        if [[ -z "$status" ]]; then
            log_error "服务 $service 未运行"
            return 1
        fi
    done

    # 检查API健康端点
    local max_retries=10
    local retry_count=0

    while [[ $retry_count -lt $max_retries ]]; do
        if curl -sf http://localhost/api/health &> /dev/null; then
            log_success "API 健康检查通过"
            return 0
        fi
        retry_count=$((retry_count + 1))
        echo -n "."
        sleep 3
    done

    log_error "API 健康检查失败"
    return 1
}

# 显示部署信息
show_deployment_info() {
    log_success "部署完成！"
    echo ""
    echo "========================================"
    echo "  AutoGeo 后端部署信息"
    echo "========================================"
    echo ""
    echo "API 地址:     http://$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')/api"
    echo "健康检查:     http://$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')/api/health"
    echo "API文档:      http://$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')/docs"
    echo ""
    echo "容器状态:"
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    echo "常用命令:"
    echo "  查看日志:   docker-compose -f docker-compose.prod.yml logs -f"
    echo "  停止服务:   docker-compose -f docker-compose.prod.yml down"
    echo "  重启服务:   docker-compose -f docker-compose.prod.yml restart"
    echo "  数据库备份: ./scripts/backup.sh"
    echo "========================================"
}

# 清理旧镜像
cleanup() {
    log_info "清理旧镜像..."
    docker image prune -f &> /dev/null || true
}

# 主函数
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
    cleanup
    show_deployment_info
}

# 处理中断信号
trap 'log_error "部署被中断"; exit 1' INT TERM

# 执行主函数
main "$@"

#!/bin/bash
# AutoGeo 后端部署脚本（共享 n8n 数据库版本）
# 版本: 3.3.0

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

COMPOSE_FILE="docker-compose.backend.yml"
HEALTH_CHECK_RETRIES=30

# 使用说明
show_help() {
    cat << EOF
AutoGeo 后端部署脚本（共享 n8n 数据库）

用法: $0 [选项]

选项:
    -h, --help          显示帮助
    -i, --image         指定后端镜像
    --rollback IMAGE    回滚到指定镜像

前提条件:
    1. n8n 必须已部署并运行（提供 PostgreSQL 和 Redis）
    2. n8n_postgres 容器必须在 n8n_network 网络中

环境变量:
    BACKEND_IMAGE       后端镜像地址
    N8N_DB_PASSWORD     n8n PostgreSQL 密码（如果在 .env.backend 中）
EOF
}

# 解析参数
ROLLBACK_IMAGE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help) show_help; exit 0 ;;
        -i|--image) export BACKEND_IMAGE="$2"; shift 2 ;;
        --rollback) ROLLBACK_IMAGE="$2"; shift 2 ;;
        *) log_error "未知选项: $1"; exit 1 ;;
    esac
done

cd "$(dirname "$0")"

# 检查 n8n 是否运行
check_n8n() {
    log_step "1/6: 检查 n8n 服务..."

    if ! docker ps | grep -q "n8n_postgres"; then
        log_error "n8n PostgreSQL 未运行！"
        echo ""
        echo "请先部署 n8n:"
        echo "  cd ../n8n/deploy"
        echo "  ./deploy.sh"
        exit 1
    fi

    if ! docker network ls | grep -q "n8n_network"; then
        log_error "n8n 网络不存在！"
        exit 1
    fi

    log_info "✅ n8n 服务已就绪"
}

# 初始化数据库
init_database() {
    log_step "2/6: 初始化数据库..."

    # 检查 autogeo 数据库是否存在，不存在则创建
    if ! docker exec n8n_postgres psql -U n8n -lqt | cut -d \| -f 1 | grep -qw autogeo; then
        log_info "创建 autogeo 数据库..."
        docker exec n8n_postgres psql -U n8n -c "CREATE DATABASE autogeo;" || {
            log_warn "数据库创建失败（可能已存在或权限不足）"
        }
    else
        log_info "autogeo 数据库已存在"
    fi
}

# 备份当前状态
backup_current() {
    log_step "3/6: 备份当前状态..."

    CURRENT_IMAGE=$(docker-compose -f "$COMPOSE_FILE" ps -q backend 2>/dev/null | xargs docker inspect --format='{{.Config.Image}}' 2>/dev/null || echo "")

    if [[ -n "$CURRENT_IMAGE" ]]; then
        echo "$CURRENT_IMAGE" > .last_deployed_image
        log_info "当前镜像: $CURRENT_IMAGE"
    fi
}

# 登录镜像仓库
login_registry() {
    log_step "4/6: 登录镜像仓库..."

    export BACKEND_IMAGE="${BACKEND_IMAGE:-crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com/opencaio/auto_geo_backend:latest}"

    if [[ -n "${ALIYUN_ACR_USERNAME:-}" && -n "${ALIYUN_ACR_PASSWORD:-}" ]]; then
        echo "$ALIYUN_ACR_PASSWORD" | docker login crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com \
            -u "$ALIYUN_ACR_USERNAME" --password-stdin 2>/dev/null || log_warn "登录失败，使用本地镜像"
    fi

    docker-compose -f "$COMPOSE_FILE" pull backend 2>/dev/null || log_warn "拉取镜像失败，使用本地镜像"
}

# 清理旧容器
cleanup_old() {
    log_info "清理旧容器..."
    docker-compose -f "$COMPOSE_FILE" stop backend 2>/dev/null || true
    docker-compose -f "$COMPOSE_FILE" rm -f backend 2>/dev/null || true
}

# 部署
deploy() {
    log_step "5/6: 启动后端服务..."

    cleanup_old
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps backend

    # 重载 nginx
    if docker-compose -f "$COMPOSE_FILE" ps nginx 2>/dev/null | grep -q "Up"; then
        docker-compose -f "$COMPOSE_FILE" exec -T nginx nginx -s reload 2>/dev/null || true
    fi
}

# 健康检查
health_check() {
    log_step "6/6: 健康检查..."

    for i in $(seq 1 $HEALTH_CHECK_RETRIES); do
        if curl -sf http://localhost:8001/api/health >/dev/null 2>&1; then
            log_info "✅ 健康检查通过"
            return 0
        fi
        echo -n "."
        sleep 2
    done

    echo ""
    log_error "❌ 健康检查失败"
    docker-compose -f "$COMPOSE_FILE" logs --tail=30 backend
    return 1
}

# 回滚
rollback() {
    local target="${1:-$(cat .last_deployed_image 2>/dev/null || echo "")}"
    if [[ -z "$target" ]]; then
        log_error "无回滚目标"
        exit 1
    fi

    log_warn "🔄 回滚到: $target"
    export BACKEND_IMAGE="$target"
    cleanup_old
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps backend
    sleep 5
    health_check && log_info "✅ 回滚成功"
}

# 显示状态
show_status() {
    echo ""
    echo "========================================"
    docker-compose -f "$COMPOSE_FILE" ps
    echo "========================================"
    echo ""
    echo "📱 访问地址:"
    echo "   API: http://$(curl -s ip.sb 2>/dev/null || echo 'localhost')/api"
    echo "   文档: http://$(curl -s ip.sb 2>/dev/null || echo 'localhost')/docs"
}

# 主流程
main() {
    log_info "🚀 AutoGeo 后端部署脚本 v3.3.0（共享 n8n 数据库）"
    echo "========================================"

    # 回滚模式
    if [[ -n "$ROLLBACK_IMAGE" ]]; then
        rollback "$ROLLBACK_IMAGE"
        show_status
        exit 0
    fi

    # 标准部署
    check_n8n
    init_database
    backup_current
    login_registry
    deploy

    if health_check; then
        log_info "✅ 部署成功！"
        show_status
    else
        log_error "❌ 部署失败，尝试回滚..."
        rollback ""
    fi
}

main

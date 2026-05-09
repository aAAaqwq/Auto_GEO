#!/bin/bash
# RAGFlow 一键部署脚本
# 适用: 阿里云ECS Ubuntu/CentOS
# 注意: RAGFlow需要至少8GB内存，建议单独服务器部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$SCRIPT_DIR/.env.ragflow}"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.ragflow.yml"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查系统资源
check_resources() {
    log_info "检查系统资源..."

    # 检查内存
    local total_mem=$(free -m | awk '/^Mem:/{print $2}')
    if [[ $total_mem -lt 8192 ]]; then
        log_warn "内存不足8GB (当前: ${total_mem}MB)，RAGFlow可能运行缓慢"
        log_warn "建议: 使用8GB+内存的服务器部署RAGFlow"
        read -p "是否继续部署? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_success "内存检查通过: ${total_mem}MB"
    fi

    # 检查磁盘空间
    local available_disk=$(df -m . | tail -1 | awk '{print $4}')
    if [[ $available_disk -lt 20480 ]]; then
        log_warn "磁盘空间不足20GB (可用: ${available_disk}MB)"
        log_warn "RAGFlow需要存储大量向量数据，建议预留50GB+空间"
    else
        log_success "磁盘空间检查通过: ${available_disk}MB可用"
    fi
}

# 检查环境
check_environment() {
    log_info "检查环境..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        log_info "安装Docker: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose 未安装"
        log_info "安装: sudo pip3 install docker-compose"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker 未运行"
        exit 1
    fi

    log_success "环境检查通过"
}

# 检查配置
check_config() {
    log_info "检查配置文件..."

    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "环境变量文件不存在: $ENV_FILE"
        log_info "请复制 .env.ragflow.example 为 .env.ragflow 并修改配置"
        exit 1
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Docker Compose 文件不存在: $COMPOSE_FILE"
        exit 1
    fi

    source "$ENV_FILE"

    local required_vars=("MYSQL_PASSWORD" "REDIS_PASSWORD" "MINIO_PASSWORD")
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

# 启动服务
start_services() {
    log_info "启动 RAGFlow 服务..."

    cd "$SCRIPT_DIR"

    # 先启动依赖服务
    log_info "启动 MySQL..."
    docker-compose -f "$COMPOSE_FILE" up -d mysql

    log_info "等待 MySQL 就绪..."
    sleep 30

    log_info "启动 Redis..."
    docker-compose -f "$COMPOSE_FILE" up -d redis

    log_info "启动 MinIO..."
    docker-compose -f "$COMPOSE_FILE" up -d minio

    log_info "启动 Elasticsearch..."
    docker-compose -f "$COMPOSE_FILE" up -d es01

    log_info "等待 Elasticsearch 就绪（约60秒）..."
    sleep 60

    log_info "启动 RAGFlow 主服务..."
    docker-compose -f "$COMPOSE_FILE" up -d ragflow

    log_success "所有服务已启动"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    local max_retries=20
    local retry_count=0

    while [[ $retry_count -lt $max_retries ]]; do
        if curl -sf http://localhost:9380/api/health &> /dev/null; then
            log_success "RAGFlow 健康检查通过"
            return 0
        fi
        retry_count=$((retry_count + 1))
        echo -n "."
        sleep 5
    done

    log_error "RAGFlow 健康检查失败"
    log_info "查看日志: docker-compose -f $COMPOSE_FILE logs -f ragflow"
    return 1
}

# 显示部署信息
show_info() {
    local server_ip=$(curl -s ip.sb 2>/dev/null || echo 'your-server-ip')

    log_success "RAGFlow 部署完成！"
    echo ""
    echo "========================================"
    echo "  RAGFlow 部署信息"
    echo "========================================"
    echo ""
    echo "访问地址:"
    echo "  - RAGFlow界面: http://${server_ip}:9380"
    echo "  - MinIO控制台: http://${server_ip}:9001"
    echo ""
    echo "API信息:"
    echo "  - API地址: http://${server_ip}:9380/api"
    echo "  - 获取API Key: 登录后右上角头像 → API → RAGFlow API"
    echo ""
    echo "首次使用:"
    echo "  1. 访问 http://${server_ip}:9380"
    echo "  2. 注册管理员账号"
    echo "  3. 创建知识库"
    echo "  4. 获取API Key配置到AutoGeo"
    echo ""
    echo "常用命令:"
    echo "  查看日志: docker-compose -f docker-compose.ragflow.yml logs -f"
    echo "  停止服务: docker-compose -f docker-compose.ragflow.yml down"
    echo "  重启服务: docker-compose -f docker-compose.ragflow.yml restart ragflow"
    echo "========================================"
}

# 主函数
main() {
    echo "========================================"
    echo "  RAGFlow 部署脚本"
    echo "  注意: 需要至少8GB内存"
    echo "========================================"
    echo ""

    check_resources
    check_environment
    check_config
    start_services
    health_check
    show_info
}

# 处理中断
trap 'log_error "部署被中断"; exit 1' INT TERM

main "$@"

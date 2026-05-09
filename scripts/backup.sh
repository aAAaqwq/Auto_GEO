#!/bin/bash
# AutoGeo 数据库备份脚本
# 自动备份PostgreSQL数据库并压缩存储

set -e

# 配置
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/autogeo_$DATE.sql"
COMPOSE_FILE="${COMPOSE_FILE:-./docker-compose.prod.yml}"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 创建备份目录
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}开始备份数据库...${NC}"

# 执行备份
docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump \
    -U autogeo \
    -d autogeo \
    --clean \
    --if-exists \
    --verbose > "$BACKUP_FILE"

# 压缩备份
echo "压缩备份文件..."
gzip "$BACKUP_FILE"

# 清理旧备份
echo "清理 $KEEP_DAYS 天前的备份..."
find "$BACKUP_DIR" -name "autogeo_*.sql.gz" -mtime +$KEEP_DAYS -delete 2>/dev/null || true

# 显示结果
echo -e "${GREEN}备份完成: ${BACKUP_FILE}.gz${NC}"
echo "备份文件大小: $(du -h "${BACKUP_FILE}.gz" | cut -f1)"
ls -lh "$BACKUP_DIR"/autogeo_*.sql.gz 2>/dev/null | tail -5

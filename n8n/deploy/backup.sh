#!/bin/bash
# n8n 数据备份脚本

set -e

BACKUP_DIR="${BACKUP_DIR:-./backup}"
KEEP_DAYS="${KEEP_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "开始备份 n8n 数据..."

# 备份 PostgreSQL
echo "备份 PostgreSQL..."
docker-compose exec -T postgres pg_dump -U n8n n8n > "$BACKUP_DIR/n8n_postgres_$DATE.sql"
gzip "$BACKUP_DIR/n8n_postgres_$DATE.sql"

# 备份 n8n 配置文件
echo "备份 n8n 配置..."
docker-compose exec -T n8n tar czf - /home/node/.n8n > "$BACKUP_DIR/n8n_config_$DATE.tar.gz"

# 清理旧备份
echo "清理旧备份..."
find "$BACKUP_DIR" -name "n8n_postgres_*.sql.gz" -mtime +$KEEP_DAYS -delete
find "$BACKUP_DIR" -name "n8n_config_*.tar.gz" -mtime +$KEEP_DAYS -delete

echo "备份完成:"
ls -lh "$BACKUP_DIR"/*$DATE*

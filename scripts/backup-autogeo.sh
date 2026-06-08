#!/bin/bash
# ============================================
# AutoGeo 数据备份脚本
# 创建时间: 2026-02-26
# ============================================

set -e

# 配置
BACKUP_ROOT="/autogeo-backup"          # 备份根目录
DATA_DIR="$HOME/autogeo"               # 数据目录
CONTAINER_NAME="autogeo-backend"       # 容器名称
TIMESTAMP=$(date +%Y%m%d_%H%M%S)       # 时间戳
RETENTION_DAYS=7                       # 保留天数

# 创建备份目录
mkdir -p "$BACKUP_ROOT/daily"
mkdir -p "$BACKUP_ROOT/weekly"

echo "🚀 开始备份 AutoGeo 数据..."
echo "时间: $(date)"
echo "================================"

# ============================================
# 第一步: 备份数据库（最重要！）
# ============================================
echo ""
echo "📦 第一步: 备份 SQLite 数据库..."

if [ -f "$DATA_DIR/database/auto_geo_v3.db" ]; then
    # 直接复制（简单快速）
    cp "$DATA_DIR/database/auto_geo_v3.db" "$BACKUP_ROOT/daily/auto_geo_v3_$TIMESTAMP.db"
    echo "✅ 数据库备份完成: auto_geo_v3_$TIMESTAMP.db"
else
    echo "⚠️  数据库文件不存在，跳过"
fi

# ============================================
# 第二步: 备份 Cookies（重要！包含登录状态）
# ============================================
echo ""
echo "🍪 第二步: 备份 Cookies..."

if [ -d "$DATA_DIR/cookies" ]; then
    tar -czf "$BACKUP_ROOT/daily/cookies_$TIMESTAMP.tar.gz" -C "$DATA_DIR" cookies/
    echo "✅ Cookies 备份完成"
else
    echo "⚠️  Cookies 目录不存在，跳过"
fi

# ============================================
# 第三步: 备份其他数据（可选）
# ============================================
echo ""
echo "📁 第三步: 备份其他数据..."

# 备份整个数据目录（排除日志，日志太大）
tar -czf "$BACKUP_ROOT/daily/data_$TIMESTAMP.tar.gz" \
    --exclude='logs' \
    -C "$DATA_DIR" .

echo "✅ 数据备份完成"

# ============================================
# 第四步: 清理旧备份
# ============================================
echo ""
echo "🗑️  第四步: 清理 $RETENTION_DAYS 天前的旧备份..."

find "$BACKUP_ROOT/daily" -name "*.db" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_ROOT/daily" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "✅ 旧备份已清理"

# ============================================
# 第五步: 备份摘要
# ============================================
echo ""
echo "================================"
echo "📊 备份摘要:"
echo "  - 备份目录: $BACKUP_ROOT"
echo "  - 时间戳: $TIMESTAMP"
echo "  - 保留天数: $RETENTION_DAYS"

# 显示备份文件大小
echo ""
echo "📋 当前备份文件:"
ls -lh "$BACKUP_ROOT/daily/" | tail -5

echo ""
echo "✅ 备份完成！"

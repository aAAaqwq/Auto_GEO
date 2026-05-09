#!/bin/bash
# ============================================
# AutoGeo 数据恢复脚本
# 创建时间: 2026-02-26
# ============================================

set -e

# 配置
BACKUP_ROOT="/autogeo-backup"          # 备份根目录
DATA_DIR="$HOME/autogeo"               # 数据目录
CONTAINER_NAME="autogeo-backend"       # 容器名称

# 检查参数
if [ -z "$1" ]; then
    echo "❌ 错误: 请指定备份文件或日期"
    echo ""
    echo "用法:"
    echo "  $0 <backup_file>         # 恢复指定的备份文件"
    echo "  $0 <date>                # 恢复指定日期的备份 (格式: YYYYMMDD)"
    echo ""
    echo "示例:"
    echo "  $0 auto_geo_v3_20260226_030000.db"
    echo "  $0 20260226"
    echo ""
    echo "📋 可用的备份:"
    ls -lh "$BACKUP_ROOT/daily/" | grep -E "\.db|\.tar\.gz" | tail -10
    exit 1
fi

RESTORE_TARGET="$1"

echo "🔄 开始恢复 AutoGeo 数据..."
echo "时间: $(date)"
echo "================================"

# ============================================
# 第一步: 停止容器（避免数据冲突）
# ============================================
echo ""
echo "⏹️  第一步: 停止容器..."

if docker ps | grep -q $CONTAINER_NAME; then
    docker stop $CONTAINER_NAME
    echo "✅ 容器已停止"
else
    echo "ℹ️  容器未运行，跳过"
fi

# ============================================
# 第二步: 备份当前数据（安全起见）
# ============================================
echo ""
echo "📦 第二步: 备份当前数据（恢复前）..."

CURRENT_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_ROOT/before-restore"

if [ -f "$DATA_DIR/database/auto_geo_v3.db" ]; then
    cp "$DATA_DIR/database/auto_geo_v3.db" "$BACKUP_ROOT/before-restore/auto_geo_v3_before_restore_$CURRENT_TIMESTAMP.db"
    echo "✅ 当前数据库已备份"
fi

# ============================================
# 第三步: 恢复数据
# ============================================
echo ""
echo "📥 第三步: 恢复数据..."

# 判断是日期还是完整文件名
if [[ "$RESTORE_TARGET" =~ ^[0-9]{8}$ ]]; then
    # 是日期，查找该日期的备份
    echo "查找日期 $RESTORE_TARGET 的备份..."
    BACKUP_FILE=$(ls "$BACKUP_ROOT/daily/" | grep "$RESTORE_TARGET" | grep "\.db$" | head -1)

    if [ -z "$BACKUP_FILE" ]; then
        echo "❌ 错误: 找不到日期 $RESTORE_TARGET 的备份"
        exit 1
    fi

    RESTORE_PATH="$BACKUP_ROOT/daily/$BACKUP_FILE"
else
    # 是完整文件名
    RESTORE_PATH="$BACKUP_ROOT/daily/$RESTORE_TARGET"

    if [ ! -f "$RESTORE_PATH" ]; then
        echo "❌ 错误: 文件不存在: $RESTORE_PATH"
        exit 1
    fi
fi

echo "恢复文件: $RESTORE_PATH"

# 根据文件类型恢复
if [[ "$RESTORE_PATH" == *.db ]]; then
    # 恢复数据库
    mkdir -p "$DATA_DIR/database"
    cp "$RESTORE_PATH" "$DATA_DIR/database/auto_geo_v3.db"
    echo "✅ 数据库恢复完成"

elif [[ "$RESTORE_PATH" == *.tar.gz ]]; then
    # 恢复压缩包
    tar -xzf "$RESTORE_PATH" -C "$DATA_DIR"
    echo "✅ 数据恢复完成"
fi

# ============================================
# 第四步: 启动容器
# ============================================
echo ""
echo "▶️  第四步: 启动容器..."

docker start $CONTAINER_NAME 2>/dev/null || {
    echo "容器已删除，需要手动启动..."
    echo "启动命令:"
    echo "docker run -d --name $CONTAINER_NAME --restart unless-stopped -p 8001:8001 ..."
}

echo "✅ 容器已启动"

# ============================================
# 第五步: 验证恢复
# ============================================
echo ""
echo "🔍 第五步: 验证恢复..."

sleep 5
if curl -f http://localhost:8001/api/health > /dev/null 2>&1; then
    echo "✅ 服务正常"
else
    echo "⚠️  服务可能未正常启动，请检查日志:"
    echo "docker logs $CONTAINER_NAME --tail 50"
fi

echo ""
echo "================================"
echo "✅ 恢复完成！"
echo "恢复前备份: $BACKUP_ROOT/before-restore/"

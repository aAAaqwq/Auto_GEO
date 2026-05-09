# AutoGeo 线上部署指南 (PostgreSQL版)

> 本文档描述如何将AutoGeo后端数据库从SQLite改造为PostgreSQL，并部署到生产环境。

## 1. 架构变化

### 改造前（SQLite）
```
┌──────────────┐
│   FastAPI    │
│   Backend    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   SQLite     │  (本地文件，单实例)
└──────────────┘
```

### 改造后（PostgreSQL）
```
┌─────────────────────────────────────────┐
│              Docker Network              │
│  ┌──────────────┐    ┌──────────────┐  │
│  │   FastAPI    │◄──►│  PostgreSQL  │  │
│  │   Backend    │    │    15+       │  │
│  └──────────────┘    └──────────────┘  │
│        ▲                    ▲          │
│        │                    │          │
│   Volume挂载           Volume持久化     │
└─────────────────────────────────────────┘
```

## 2. 快速开始

### 2.1 准备工作

```bash
# 1. 确保已安装 Docker 和 Docker Compose
docker --version
docker-compose --version

# 2. 克隆项目
git clone <repository-url>
cd Auto_GEO

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置强密码
```

### 2.2 配置环境变量

编辑 `.env` 文件：

```bash
# 加密密钥（必须修改）
AUTO_GEO_ENCRYPTION_KEY=your-32-char-secure-key-here

# PostgreSQL配置（必须修改）
DB_PASSWORD=your-secure-password-here

# DeepSeek API（必须配置）
DEEPSEEK_API_KEY=your-deepseek-api-key

# RAGFlow配置（可选）
RAGFLOW_API_KEY=your-ragflow-api-key
```

### 2.3 启动服务

```bash
# 1. 启动所有服务（后台运行）
docker-compose up -d

# 2. 查看服务状态
docker-compose ps

# 3. 查看日志
docker-compose logs -f backend
docker-compose logs -f postgres
```

### 2.4 初始化数据库

```bash
# 1. 等待PostgreSQL启动完成（约10秒）
sleep 10

# 2. 执行数据库迁移
docker-compose exec backend alembic upgrade head

# 3. 验证数据库状态
docker-compose exec postgres psql -U autogeo -d autogeo -c "\dt"
```

## 3. 详细配置

### 3.1 PostgreSQL配置

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `DB_USER` | autogeo | 数据库用户名 |
| `DB_PASSWORD` | changeme | **必须修改** |
| `DB_NAME` | autogeo | 数据库名 |
| `DB_PORT` | 5432 | 对外暴露端口 |
| `DB_POOL_SIZE` | 10 | 连接池大小 |
| `DB_MAX_OVERFLOW` | 20 | 最大溢出连接 |

### 3.2 连接池优化

根据并发量调整：

```bash
# 低并发（<50并发）
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# 中等并发（50-200）
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# 高并发（>200）
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

### 3.3 使用外部PostgreSQL

如果使用云数据库（如AWS RDS、阿里云RDS）：

```bash
# 1. 修改 .env，配置完整URL
DATABASE_URL=postgresql://user:password@your-rds-endpoint:5432/autogeo

# 2. 注释掉 docker-compose.yml 中的 postgres 服务

# 3. 重启服务
docker-compose up -d
```

## 4. 数据迁移（从SQLite）

### 4.1 导出SQLite数据

```bash
# 1. 进入backend目录
cd backend

# 2. 安装pgloader（数据迁移工具）
# macOS
brew install pgloader

# Ubuntu/Debian
apt-get install pgloader

# 3. 执行迁移
pgloader sqlite:///database/auto_geo_v3.db postgresql://autogeo:password@localhost/autogeo
```

### 4.2 使用Python脚本迁移

```bash
# 1. 安装依赖
pip install sqlalchemy psycopg2-binary pandas

# 2. 运行迁移脚本
python scripts/migrate_sqlite_to_pg.py \
  --sqlite-url sqlite:///backend/database/auto_geo_v3.db \
  --pg-url postgresql://autogeo:password@localhost:5432/autogeo
```

### 4.3 验证迁移结果

```bash
# 连接PostgreSQL检查数据
docker-compose exec postgres psql -U autogeo -d autogeo

# 查看表数量
SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';

# 查看记录数
SELECT 'accounts' as table_name, COUNT(*) as count FROM accounts
UNION ALL
SELECT 'geo_articles', COUNT(*) FROM geo_articles
UNION ALL
SELECT 'publish_records', COUNT(*) FROM publish_records;
```

## 5. 备份与恢复

### 5.1 自动备份脚本

```bash
#!/bin/bash
# backup.sh - 每天凌晨3点执行

BACKUP_DIR="/backups/autogeo"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/autogeo_$DATE.sql"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行备份
docker-compose exec -T postgres pg_dump -U autogeo autogeo > $BACKUP_FILE

# 压缩备份
gzip $BACKUP_FILE

# 保留最近30天备份
find $BACKUP_DIR -name "autogeo_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

添加到crontab：
```bash
# 编辑crontab
crontab -e

# 添加定时任务（每天凌晨3点）
0 3 * * * /path/to/backup.sh >> /var/log/autogeo_backup.log 2>&1
```

### 5.2 手动备份

```bash
# 备份
docker-compose exec postgres pg_dump -U autogeo autogeo > backup_$(date +%Y%m%d).sql

# 恢复
docker-compose exec -T postgres psql -U autogeo -d autogeo < backup_20240101.sql
```

## 6. 监控与运维

### 6.1 查看数据库状态

```bash
# 连接数查询
docker-compose exec postgres psql -U autogeo -c "SELECT count(*) FROM pg_stat_activity;"

# 慢查询
docker-compose exec postgres psql -U autogeo -c "SELECT query, query_start FROM pg_stat_activity WHERE state = 'active';"

# 数据库大小
docker-compose exec postgres psql -U autogeo -c "SELECT pg_size_pretty(pg_database_size('autogeo'));"
```

### 6.2 日志查看

```bash
# 实时查看PostgreSQL日志
docker-compose logs -f postgres

# 查看最近的错误
docker-compose logs postgres | grep ERROR
```

### 6.3 性能优化

```sql
-- 添加常用查询索引
CREATE INDEX CONCURRENTLY idx_geo_articles_status ON geo_articles(publish_status);
CREATE INDEX CONCURRENTLY idx_accounts_last_auth ON accounts(last_auth_time);

-- 分析表统计信息
ANALYZE geo_articles;
ANALYZE accounts;
```

## 7. 故障排除

### 7.1 常见问题

#### Q: PostgreSQL启动失败
```bash
# 检查日志
docker-compose logs postgres

# 检查端口占用
lsof -i :5432

# 清理数据卷（谨慎操作！）
docker-compose down -v
docker-compose up -d postgres
```

#### Q: 数据库连接失败
```bash
# 检查网络
docker-compose exec backend ping postgres

# 检查配置
docker-compose exec backend env | grep DATABASE

# 重置连接池
docker-compose restart backend
```

#### Q: 迁移失败
```bash
# 查看迁移历史
docker-compose exec backend alembic history

# 回滚到上一个版本
docker-compose exec backend alembic downgrade -1

# 重新执行
docker-compose exec backend alembic upgrade head
```

### 7.2 紧急回滚到SQLite

如果PostgreSQL版本出现问题，可以快速回滚：

```bash
# 1. 修改 .env
DATABASE_URL=sqlite:///./data/auto_geo.db

# 2. 停止服务
docker-compose down

# 3. 使用旧配置启动
docker-compose -f docker-compose.sqlite.yml up -d
```

## 8. 安全建议

1. **修改默认密码**: 生产环境务必修改所有默认密码
2. **限制网络访问**: 不将PostgreSQL端口暴露到公网
3. **定期备份**: 配置自动备份策略
4. **更新系统**: 定期更新Docker镜像和系统补丁
5. **使用HTTPS**: 配置Nginx SSL证书

## 9. 参考文档

- [PostgreSQL官方文档](https://www.postgresql.org/docs/15/index.html)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [Alembic迁移工具](https://alembic.sqlalchemy.org/)

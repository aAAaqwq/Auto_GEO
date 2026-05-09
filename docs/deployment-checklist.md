# AutoGeo 线上部署检查清单

> ⚠️ **重要提示**：代码改造完成 ≠ 立即可用，还需完成以下部署步骤

---

## 第一阶段：服务器准备 ✅

### 1.1 服务器环境

| 检查项 | 要求 | 命令 |
|--------|------|------|
| 操作系统 | Linux (Ubuntu 20.04+/CentOS 7+) | `cat /etc/os-release` |
| CPU | 2核+ | `nproc` |
| 内存 | 4GB+ (推荐8GB) | `free -h` |
| 磁盘 | 20GB+ SSD | `df -h` |
| 网络 | 公网IP，开放端口 | `curl ip.sb` |

### 1.2 安装Docker

```bash
# 检查Docker是否安装
docker --version  # 需要 20.10+
docker-compose --version  # 需要 1.29+ 或 docker compose

# 如未安装，参考官方文档：https://docs.docker.com/engine/install/
```

**状态**: ⬜ 待完成

---

## 第二阶段：代码部署 ⬜

### 2.1 克隆代码

```bash
# 在服务器上执行
git clone <your-repository-url>
cd Auto_GEO
```

**状态**: ⬜ 待完成

### 2.2 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，必须修改以下配置：
# 1. AUTO_GEO_ENCRYPTION_KEY - 加密密钥（32字符）
# 2. DB_PASSWORD - 数据库密码（强密码）
# 3. DEEPSEEK_API_KEY - DeepSeek API密钥
# 4. RAGFLOW_API_KEY - RAGFlow API密钥

# 生成加密密钥示例
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**状态**: ⬜ 待完成

### 2.3 启动基础服务

```bash
# 仅启动PostgreSQL（先不启动backend）
docker-compose up -d postgres

# 等待PostgreSQL启动完成（约10秒）
sleep 10

# 检查PostgreSQL状态
docker-compose ps postgres
```

**状态**: ⬜ 待完成

---

## 第三阶段：数据库初始化 ⬜

### 3.1 执行数据库迁移

```bash
# 执行迁移脚本，创建所有表
docker-compose run --rm backend alembic upgrade head

# 或如果backend已在运行
docker-compose exec backend alembic upgrade head
```

**预期输出**:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, initial migration
✅ 初始表结构创建完成
```

### 3.2 验证数据库表

```bash
# 检查表是否创建成功
docker-compose exec postgres psql -U autogeo -d autogeo -c "\dt"

# 预期输出：显示所有表名
# accounts, clients, projects, keywords, geo_articles, publish_records, ...
```

**状态**: ⬜ 待完成

---

## 第四阶段：启动服务 ⬜

### 4.1 启动所有服务

```bash
# 启动全部服务
docker-compose up -d

# 检查状态
docker-compose ps

# 预期：所有服务状态为 "Up" 或 "healthy"
# - auto_geo_postgres    Up
# - auto_geo_backend     Up (healthy)
# - auto_geo_n8n         Up
# - auto_geo_nginx       Up
```

### 4.2 健康检查

```bash
# 后端API健康检查
curl http://localhost:8001/health

# 预期输出：
# {"status":"ok","database":"connected"}
```

**状态**: ⬜ 待完成

---

## 第五阶段：功能测试 ⬜

### 5.1 API基础测试

```bash
# 测试API是否可访问
curl http://localhost:8001/api/health

# 测试账号API
curl http://localhost:8001/api/accounts

# 预期：返回JSON数据或空数组
```

### 5.2 数据库连接测试

```bash
# 进入backend容器
docker-compose exec backend python3 -c "
from backend.database import get_db
from backend.database.models import Account

db = next(get_db())
count = db.query(Account).count()
print(f'数据库连接正常，账号数: {count}')
"
```

### 5.3 关键功能验证

| 功能 | 测试方法 | 预期结果 |
|------|---------|---------|
| 账号管理 | POST /api/accounts | 创建成功 |
| 项目管理 | GET /api/projects | 返回列表 |
| 文章生成 | POST /api/geo/generate | 队列任务创建 |
| 发布测试 | POST /api/publish | 发布任务创建 |

**状态**: ⬜ 待完成

---

## 第六阶段：安全配置 ⬜

### 6.1 防火墙配置

```bash
# 开放必要端口
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8001/tcp  # 后端API（如需直接访问）

# 不开放以下端口：
# - 5432 (PostgreSQL，仅限内网)
# - 5678 (n8n，如需公网访问则开放)
```

### 6.2 SSL证书（生产必需）

```bash
# 使用Let's Encrypt申请免费证书
certbot --nginx -d your-domain.com

# 或配置nginx使用现有证书
```

**状态**: ⬜ 待完成

---

## 第七阶段：监控配置 ⬜

### 7.1 日志监控

```bash
# 实时查看日志
docker-compose logs -f backend
docker-compose logs -f postgres

# 日志轮转已在docker-compose中配置
# 位置：/var/log/docker/
```

### 7.2 数据库监控

```bash
# 查看连接数
docker-compose exec postgres psql -U autogeo -c "SELECT count(*) FROM pg_stat_activity;"

# 查看数据库大小
docker-compose exec postgres psql -U autogeo -c "SELECT pg_size_pretty(pg_database_size('autogeo'));"
```

### 7.3 告警配置（可选）

```bash
# 设置Prometheus + Grafana监控
# 或配置云监控告警
```

**状态**: ⬜ 待完成

---

## 第八阶段：备份配置 ⬜

### 8.1 自动备份脚本

```bash
# 创建备份脚本
mkdir -p /opt/backups/autogeo
cat > /opt/backups/autogeo/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/autogeo"
DATE=$(date +%Y%m%d_%H%M%S)

cd /path/to/Auto_GEO
docker-compose exec -T postgres pg_dump -U autogeo autogeo > $BACKUP_DIR/autogeo_$DATE.sql
gzip $BACKUP_DIR/autogeo_$DATE.sql
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/backups/autogeo/backup.sh

# 添加到定时任务（每天凌晨3点）
echo "0 3 * * * /opt/backups/autogeo/backup.sh >> /var/log/autogeo_backup.log 2>&1" | sudo crontab -
```

**状态**: ⬜ 待完成

---

## 常见问题排查

### Q1: PostgreSQL启动失败

```bash
# 检查日志
docker-compose logs postgres

# 常见原因：
# 1. 端口冲突：5432被占用
# 2. 权限问题：数据卷权限不足
# 3. 内存不足
```

### Q2: 数据库迁移失败

```bash
# 检查PostgreSQL是否就绪
docker-compose exec postgres pg_isready -U autogeo

# 查看迁移历史
docker-compose exec backend alembic history

# 手动执行SQL检查
docker-compose exec postgres psql -U autogeo -d autogeo -c "SELECT * FROM alembic_version;"
```

### Q3: Backend连接数据库失败

```bash
# 检查环境变量
docker-compose exec backend env | grep DATABASE

# 检查网络连接
docker-compose exec backend ping postgres

# 重启服务
docker-compose restart backend
```

### Q4: 前端无法访问API

```bash
# 检查CORS配置
# 修改 .env 中的 CORS_ORIGINS，添加前端域名

# 检查Nginx配置
docker-compose logs nginx
```

---

## 完成确认清单

| 阶段 | 状态 | 负责人 | 时间 |
|------|------|--------|------|
| 服务器准备 | ⬜ | | |
| 代码部署 | ⬜ | | |
| 数据库初始化 | ⬜ | | |
| 服务启动 | ⬜ | | |
| 功能测试 | ⬜ | | |
| 安全配置 | ⬜ | | |
| 监控配置 | ⬜ | | |
| 备份配置 | ⬜ | | |

---

## 部署后验证命令

```bash
# 一键验证所有服务状态
echo "=== AutoGeo 部署验证 ==="
echo ""
echo "1. 容器状态:"
docker-compose ps

echo ""
echo "2. 数据库连接:"
docker-compose exec postgres pg_isready -U autogeo

echo ""
echo "3. API健康检查:"
curl -s http://localhost:8001/health | python3 -m json.tool

echo ""
echo "4. 数据库表数量:"
docker-compose exec postgres psql -U autogeo -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"

echo ""
echo "=== 验证完成 ==="
```

---

## 预估时间

| 阶段 | 预估时间 | 实际时间 |
|------|---------|---------|
| 服务器准备 | 30分钟 | |
| 代码部署 | 15分钟 | |
| 数据库初始化 | 10分钟 | |
| 服务启动 | 10分钟 | |
| 功能测试 | 30分钟 | |
| 安全配置 | 20分钟 | |
| 监控配置 | 20分钟 | |
| **总计** | **~2.5小时** | |

> 注：以上为首次部署时间，后续更新仅需5-10分钟

# n8n 独立部署方案

## 架构特点

- **独立部署**: n8n 与 AutoGeo 后端分离，各自独立升级维护
- **PostgreSQL**: 生产级数据持久化（非SQLite）
- **Redis队列**: 支持高并发执行
- **可扩展**: 支持水平扩展（高可用模式）
- **IP+端口访问**: 无需域名和SSL，直接通过IP访问

## 部署步骤

### 1. 快速部署

```bash
cd n8n/deploy

# 复制环境变量模板
cp .env.example .env

# 编辑配置（修改your-server-ip为你的服务器IP）
vim .env

# 一键部署
./deploy.sh
```

部署完成后访问：
- 管理界面: `http://your-server-ip:5678`
- Webhook地址: `http://your-server-ip:5678/webhook/`

### 2. 启用高可用模式

```bash
# 修改 .env
EXECUTIONS_MODE=queue

# 启动主服务+worker节点
docker-compose --profile ha up -d

# 会自动启动:
# - n8n (主服务，端口5678)
# - n8n_webhook (webhook专用，端口5679)
# - n8n_worker (执行worker，无端口暴露)

# 访问方式:
# - 管理界面: http://your-server-ip:5678
# - Webhook: http://your-server-ip:5678/webhook/ 或 http://your-server-ip:5679/webhook/
```

### 3. 配置AutoGeo连接

在 AutoGeo 后端 `.env` 文件中：

```bash
# 配置独立n8n地址
N8N_WEBHOOK_URL=http://your-n8n-server-ip:5678/webhook
```

## 目录结构

```
n8n/deploy/
├── docker-compose.yml    # 主编排文件
├── .env.example          # 环境变量模板
├── deploy.sh             # 一键部署脚本
├── backup.sh             # 数据备份脚本
└── README.md             # 本文件
```

## 高可用模式

### 架构图（IP+端口方式）

```
                    ┌─────────────────┐
                    │   服务器IP      │
                    │  端口5678/5679  │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼─────┐    ┌──────▼─────┐    ┌───────▼────┐
    │   n8n     │    │ n8n_webhook│    │ n8n_worker │
    │  :5678    │    │  :5679     │    │ (无端口)   │
    └─────┬─────┘    └────────────┘    └────────────┘
          │
    ┌─────▼─────┐    ┌────────────┐
    │ PostgreSQL│    │   Redis    │
    │  (数据)   │    │  (队列)    │
    └───────────┘    └────────────┘
```

### 启用HA模式

```bash
# 修改 .env
EXECUTIONS_MODE=queue

# 启动所有服务
docker-compose --profile ha up -d

# 此时有多个入口：
# - http://ip:5678 - 主服务（管理界面+webhook）
# - http://ip:5679 - webhook专用节点
```

## 备份与恢复

### 自动备份

```bash
# 手动备份
./backup.sh

# 定时备份（每天凌晨3点）
echo "0 3 * * * cd /path/to/n8n/deploy && ./backup.sh" | crontab -
```

### 恢复数据

```bash
# 停止服务
docker-compose down

# 恢复PostgreSQL
gunzip < backup/n8n_postgres_xxxx.sql.gz | docker-compose exec -T postgres psql -U n8n

# 恢复配置
docker-compose run --rm n8n tar xzf /backup/n8n_config_xxxx.tar.gz -C /

# 重启服务
docker-compose up -d
```

## 故障排查

```bash
# 查看日志
docker-compose logs -f n8n

# 检查服务状态
docker-compose ps

# 检查端口监听
netstat -tlnp | grep 5678

# 测试webhook（在服务器上）
curl http://localhost:5678/webhook/keyword-distill \
  -H "Content-Type: application/json" \
  -d '{"core_kw": "测试", "target_info": "测试"}'

# 检查队列状态
docker-compose exec redis redis-cli -a your-password LLEN n8nQueue:jobs:waiting

# 重启服务
docker-compose restart n8n

# 查看执行历史
docker-compose exec postgres psql -U n8n -c "SELECT * FROM execution_entity ORDER BY started_at DESC LIMIT 10;"
```

## 性能调优

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| N8N_CONCURRENCY | 10 | 并发执行数 |
| EXECUTIONS_DATA_MAX_AGE | 168 | 执行数据保留小时 |
| worker --concurrency | 5 | Worker并发数 |

## 防火墙配置

如果使用阿里云ECS，需要开放安全组端口：

```bash
# 开放n8n端口（建议在阿里云控制台配置）
# 入方向规则：
# - 端口5678，允许你的IP访问（管理界面）
# - 端口5679（HA模式下webhook专用，可选）
```

## 与云端n8n对比

| 特性 | 独立部署 | 云端n8n |
|------|---------|---------|
| 数据控制 | 完全自主 | 托管 |
| 成本 | 服务器费用 | 订阅费用 |
| 定制化 | 完全定制 | 受限 |
| 维护 | 自主维护 | 免维护 |
| 网络延迟 | 内网低延迟 | 公网延迟 |
| 扩展性 | 无限 | 受限 |

**建议**: 生产环境使用独立部署，开发测试可用云端。

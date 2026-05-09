# RAGFlow 独立部署指南

## 部署前须知

RAGFlow是一个资源密集型的AI知识库系统，**建议单独服务器部署**。

### 资源需求

| 配置项 | 最低要求 | 建议配置 |
|--------|----------|----------|
| 内存 | 8GB | 16GB+ |
| CPU | 4核 | 8核+ |
| 磁盘 | 50GB SSD | 100GB+ SSD |
| 网络 | 内网互通 | 固定公网IP |

### 架构说明

```
┌─────────────────────────────────────────────┐
│               RAGFlow 服务器                │
│                                             │
│  ┌─────────────┐    ┌─────────────────────┐ │
│  │  RAGFlow    │    │  Elasticsearch      │ │
│  │  :9380      │────│  :9200 (向量检索)   │ │
│  └──────┬──────┘    └─────────────────────┘ │
│         │                                   │
│  ┌──────┴───────────────────────────────┐  │
│  │      依赖服务                        │  │
│  │  - MySQL 8.0 (元数据)                │  │
│  │  - Redis 7 (缓存/队列)               │  │
│  │  - MinIO (文档存储)                  │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────┐
│           AutoGeo 后端服务器                │
│                                             │
│  通过 API Key 调用 RAGFlow                  │
│  配置: RAGFLOW_API_KEY + RAGFLOW_BASE_URL   │
└─────────────────────────────────────────────┘
```

## 快速部署

### 1. 准备服务器

创建一台独立的阿里云ECS（建议8GB+内存）：
```bash
# 系统要求: Ubuntu 22.04 / CentOS 8
# 开放安全组端口: 9380
```

### 2. 一键部署

```bash
# 进入部署目录
cd Auto_GEO/deploy

# 复制环境变量模板
cp .env.ragflow.example .env.ragflow

# 编辑配置文件
vim .env.ragflow
```

配置内容示例：
```bash
MYSQL_PASSWORD=your-secure-mysql-password
REDIS_PASSWORD=your-secure-redis-password
MINIO_PASSWORD=your-secure-minio-password
```

### 3. 执行部署

```bash
./ragflow-deploy.sh
```

部署过程约需5-10分钟（首次启动ES和MySQL较慢）。

## 配置 AutoGeo 连接

### 1. 获取 RAGFlow API Key

1. 访问 `http://ragflow-server-ip:9380`
2. 注册/登录管理员账号
3. 右上角头像 → **API** → **RAGFlow API**
4. 复制 API Key

### 2. 创建知识库

1. 点击 **知识库** → **创建知识库**
2. 配置嵌入模型：选择适合的模型（如bge-large-zh-v1.5）
3. 上传文档并解析
4. 记录 **知识库ID**（从URL中获取）

### 3. 配置 AutoGeo

在 AutoGeo 后端 `.env` 文件中：

```bash
# RAGFlow 配置
RAGFLOW_API_KEY=your-ragflow-api-key
RAGFLOW_BASE_URL=http://ragflow-server-ip:9380
```

测试连接：
```bash
cd backend/integrations/ragflow
python check_status.py
```

## 服务管理

| 操作 | 命令 |
|------|------|
| 查看日志 | `docker-compose -f docker-compose.ragflow.yml logs -f` |
| 停止服务 | `docker-compose -f docker-compose.ragflow.yml down` |
| 重启服务 | `docker-compose -f docker-compose.ragflow.yml restart ragflow` |
| 查看状态 | `docker-compose -f docker-compose.ragflow.yml ps` |

## 故障排查

### 1. 服务启动失败

```bash
# 检查日志
docker-compose -f docker-compose.ragflow.yml logs ragflow

# 常见原因：ES启动超时，增加等待时间后重试
docker-compose -f docker-compose.ragflow.yml restart ragflow
```

### 2. 连接超时

检查防火墙/安全组：
- 确保端口 9380 已开放
- 确保 AutoGeo 服务器能访问 RAGFlow 服务器IP

### 3. 内存不足

```bash
# 检查内存使用
free -h

# 如内存不足，增加swap或升级服务器
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 4. 数据备份

```bash
# 备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose -f docker-compose.ragflow.yml exec -T mysql mysqldump -u root -p${MYSQL_PASSWORD} ragflow > ragflow_backup_${DATE}.sql
```

## 升级

```bash
cd Auto_GEO/deploy

# 拉取最新镜像
docker-compose -f docker-compose.ragflow.yml pull

# 重启服务
docker-compose -f docker-compose.ragflow.yml down
docker-compose -f docker-compose.ragflow.yml up -d

# 检查状态
docker-compose -f docker-compose.ragflow.yml ps
```

## 相关信息

| 项目 | 地址/说明 |
|------|-----------|
| RAGFlow 官方文档 | https://ragflow.io/docs |
| RAGFlow GitHub | https://github.com/infiniflow/ragflow |
| RAGFlow 镜像 | registry.cn-hangzhou.aliyuncs.com/ragflow/ragflow:latest |
| API 文档 | http://your-ip:9380/api/docs |

---

**注意**: RAGFlow 首次启动较慢（需要初始化ES索引），请耐心等待。

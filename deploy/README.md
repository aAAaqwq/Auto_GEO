# AutoGeo 生产环境部署指南

## 架构概览

AutoGeo 采用 **3+1 独立部署架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                      部署架构图                              │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   后端服务    │   n8n服务    │  RAGFlow服务 │   前端应用      │
│  (必需)       │   (必需)     │   (可选)     │   (桌面应用)    │
├──────────────┼──────────────┼──────────────┼────────────────┤
│  PostgreSQL  │  PostgreSQL  │   MySQL      │   Electron     │
│  Backend     │  Redis       │   Redis      │   Vue3         │
│  Nginx       │  n8n Engine  │   MinIO      │                │
│              │              │   ES         │                │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

## 服务器规划

| 服务 | 建议配置 | 端口 | 说明 |
|------|----------|------|------|
| 后端 | 2核4GB | 80 | 可与n8n同机部署 |
| n8n | 2核4GB | 5678 | 可与后端同机部署 |
| RAGFlow | 4核8GB+ | 9380 | **建议独立服务器** |

## 快速部署

### 1. 克隆项目

```bash
git clone https://github.com/Architecture-Matrix/Auto_GEO.git
cd Auto_GEO/deploy
```

### 2. 部署后端服务

```bash
# 复制环境变量模板
cp .env.backend.example .env.backend
vim .env.backend  # 修改配置

# 执行部署
./deploy-backend.sh
```

### 3. 部署 n8n（建议单独服务器）

```bash
# 在n8n服务器上
cp .env.n8n.example .env.n8n
vim .env.n8n  # 修改配置

./deploy-n8n.sh
```

### 4. 部署 RAGFlow（可选，需8GB+内存）

详见 [RAGFLOW-DEPLOY.md](./RAGFLOW-DEPLOY.md)

```bash
cp .env.ragflow.example .env.ragflow
vim .env.ragflow

./ragflow-deploy.sh
```

## 配置说明

### 后端 .env.backend 关键配置

```bash
# 数据库密码
DB_PASSWORD=your-secure-password

# 加密密钥（生成: python -c "import secrets; print(secrets.token_urlsafe(32))"）
AUTO_GEO_ENCRYPTION_KEY=xxx

# n8n地址（部署后填写）
N8N_WEBHOOK_URL=http://n8n-server-ip:5678/webhook

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx

# RAGFlow地址（可选）
RAGFLOW_BASE_URL=http://ragflow-server-ip:9380
```

### n8n .env.n8n 关键配置

```bash
# n8n服务器IP
N8N_HOST=your-server-ip
N8N_PASSWORD=admin-password

# 数据库和Redis密码
POSTGRES_PASSWORD=xxx
REDIS_PASSWORD=xxx
```

## 目录结构

```
deploy/
├── docker-compose.backend.yml    # 后端编排
├── docker-compose.n8n.yml        # n8n编排
├── docker-compose.ragflow.yml    # RAGFlow编排
├── deploy-backend.sh             # 后端部署脚本
├── deploy-n8n.sh                 # n8n部署脚本
├── ragflow-deploy.sh             # RAGFlow部署脚本
├── .env.backend.example          # 后端环境变量模板
├── .env.n8n.example              # n8n环境变量模板
├── .env.ragflow.example          # RAGFlow环境变量模板
├── RAGFLOW-DEPLOY.md             # RAGFlow详细文档
└── README.md                     # 本文档
```

## 常用命令

| 操作 | 后端 | n8n |
|------|------|-----|
| 查看日志 | `docker-compose -f docker-compose.backend.yml logs -f` | `docker-compose -f docker-compose.n8n.yml logs -f` |
| 停止服务 | `docker-compose -f docker-compose.backend.yml down` | `docker-compose -f docker-compose.n8n.yml down` |
| 重启 | `docker-compose -f docker-compose.backend.yml restart` | `docker-compose -f docker-compose.n8n.yml restart` |

## 前端使用

前端为 **Electron 桌面应用**，无需服务器部署：

```bash
cd frontend
npm install
npm run dev  # 开发模式
npm run build  # 打包
```

用户安装打包后的应用即可使用。

## 故障排查

### 端口冲突

```bash
# 检查端口占用
netstat -tlnp | grep 80
netstat -tlnp | grep 5678
```

### 登录阿里云ACR失败

使用密码文件方式更安全：
```bash
echo 'your-password' > /etc/autogeo/acr-pass
chmod 600 /etc/autogeo/acr-pass
# 在.env中设置 ALIYUN_ACR_PASSWORD_FILE=/etc/autogeo/acr-pass
```

### 数据库迁移失败

```bash
docker-compose -f docker-compose.backend.yml exec backend alembic upgrade head
```

## 镜像说明

所有镜像均使用**阿里云镜像站**：
- `registry.cn-hangzhou.aliyuncs.com/acs-sample/postgres:15-alpine`
- `registry.cn-hangzhou.aliyuncs.com/acs-sample/redis:7-alpine`
- `registry.cn-hangzhou.aliyuncs.com/acs-sample/nginx:alpine`
- `registry.cn-hangzhou.aliyuncs.com/acs-sample/n8n:latest`

后端镜像：
- `crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com/opencaio/auto_geo_backend:latest`

---

部署完成后，访问 `http://backend-server-ip/docs` 查看 API 文档。

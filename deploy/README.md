# AutoGeo 部署指南

## 新架构概览（简化版）

```
┌─────────────────────────────────────────────────────────┐
│                    新部署架构（4容器）                    │
├─────────────────┬─────────────────┬─────────────────────┤
│   n8n 服务      │   后端服务      │     前端（桌面）     │
│   (3容器)       │   (1容器)       │                     │
├─────────────────┼─────────────────┼─────────────────────┤
│  PostgreSQL ←───┼─── backend      │    Electron + Vue3  │
│  Redis      ←───┼─── (API:8001)   │                     │
│  n8n            │                 │                     │
└─────────────────┴─────────────────┴─────────────────────┘
         │                              ▲
         └───── 服务器 Nginx:80 ─────────┘
```

### 核心变更
- **后端不再自带数据库**，复用 n8n 的 PostgreSQL
- **后端不再带 Nginx**，使用服务器 Nginx 做反向代理
- **总容器数从 7 → 4**，节省资源

---

## 快速开始

### 第一步：部署 n8n（必需）

```bash
cd n8n/deploy
./deploy.sh
```

访问：`http://your-server-ip:5678`

---

### 第二步：配置服务器 Nginx

后端只提供 API 服务（8001 端口），需要在服务器 Nginx 添加反向代理：

```nginx
# /etc/nginx/conf.d/autogeo.conf
server {
    listen 80;
    server_name your-domain-or-ip;

    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /docs {
        proxy_pass http://localhost:8001/docs;
    }
}
```

然后重载 Nginx：
```bash
sudo nginx -s reload
```

---

### 第三步：部署后端

```bash
cd deploy

# 1. 配置环境变量
cp .env.backend.example .env.backend
nano .env.backend
```

**关键配置（只改4项）：**

```bash
# n8n数据库密码（与 n8n/.env 中的一致）
N8N_DB_PASSWORD=xxx

# 加密密钥（生成: openssl rand -base64 32）
AUTO_GEO_ENCRYPTION_KEY=xxx

# n8n地址和API Key
N8N_WEBHOOK_URL=http://ip:5678/webhook
N8N_API_KEY=xxx

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx
```

```bash
# 2. 执行部署
./deploy.sh
```

访问：`http://your-server-ip/api`

---

## 文件结构

```
deploy/
├── docker-compose.backend.yml    # 后端编排（1服务：backend）
├── deploy.sh                     # 一键部署脚本
├── .env.backend.example          # 环境变量模板
└── README.md                     # 本文档

n8n/deploy/
├── docker-compose.yml            # n8n编排（3服务：postgres+redis+n8n）
├── deploy.sh                     # 一键部署脚本
└── .env                          # 自动生成
```

---

## 常用命令

| 操作 | 命令 |
|------|------|
| 后端日志 | `cd deploy && docker-compose logs -f` |
| n8n日志 | `cd n8n/deploy && docker-compose logs -f` |
| 停止后端 | `cd deploy && docker-compose down` |
| 停止n8n | `cd n8n/deploy && docker-compose down` |

---

## 注意事项

1. **必须先部署 n8n**，后端依赖 n8n 的数据库
2. **需要配置服务器 Nginx** 反向代理到后端 8001 端口
3. 后端会自动在 n8n_postgres 中创建 `autogeo` 数据库
4. 确保防火墙开放 5678（n8n）和 80（http）端口

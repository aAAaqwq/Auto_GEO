# AutoGeo 部署指南（宝塔面板版）

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
         └───── 宝塔 Nginx:80 ──────────┘
```

### 核心变更
- **后端不再自带数据库**，复用 n8n 的 PostgreSQL
- **后端不再带 Nginx**，使用宝塔 Nginx 做反向代理
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

### 第二步：配置宝塔 Nginx

后端只提供 API 服务（8001 端口），需要在宝塔添加反向代理：

**方法1：直接创建配置文件**

创建文件：`/www/server/panel/vhost/nginx/autogeo.conf`

```nginx
server {
    listen 80;
    server_name your-domain-or-ip;

    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /docs {
        proxy_pass http://localhost:8001/docs;
    }

    # WebSocket 支持（如果需要）
    location /ws {
        proxy_pass http://localhost:8001/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**方法2：使用宝塔面板可视化配置**

1. 登录宝塔面板
2. 网站 → 添加站点（或使用已有站点）
3. 配置文件 → 添加上面的 location 配置

**重载 Nginx：**
```bash
/www/server/nginx/sbin/nginx -s reload
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

## 宝塔环境路径速查

| 项目 | 路径 |
|------|------|
| Nginx 配置目录 | `/www/server/panel/vhost/nginx/` |
| Nginx 主程序 | `/www/server/nginx/sbin/nginx` |
| Nginx 重载命令 | `/www/server/nginx/sbin/nginx -s reload` |
| 网站目录 | `/www/wwwroot/` |

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
| 重载Nginx | `/www/server/nginx/sbin/nginx -s reload` |

---

## 注意事项

1. **必须先部署 n8n**，后端依赖 n8n 的数据库
2. **需要配置宝塔 Nginx** 反向代理到后端 8001 端口
3. 后端会自动在 n8n_postgres 中创建 `autogeo` 数据库
4. 确保防火墙开放 5678（n8n）和 80（http）端口

---

## 故障排查

### 后端无法连接数据库
```bash
# 检查 n8n_postgres 是否运行
docker ps | grep n8n_postgres

# 检查密码是否正确
docker exec n8n_postgres psql -U n8n -c "\l"
```

### Nginx 配置测试
```bash
/www/server/nginx/sbin/nginx -t
```

### 查看 Nginx 错误日志
```bash
tail -f /www/server/nginx/logs/error.log
```

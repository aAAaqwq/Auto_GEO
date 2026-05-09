# AutoGeo AI搜索引擎优化自动化平台

> 智能GEO/SEO内容优化平台，支持40+平台自动发布、AI搜索引擎收录检测、GEO文章生成

[![Startup Validation](https://github.com/Architecture-Matrix/Auto_GEO/actions/workflows/startup-validation.yml/badge.svg)](https://github.com/Architecture-Matrix/Auto_GEO/actions/workflows/startup-validation.yml)
[![Backend CI](https://github.com/Architecture-Matrix/Auto_GEO/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/Architecture-Matrix/Auto_GEO/actions/workflows/backend-ci.yml)
[![Backend Deploy](https://github.com/Architecture-Matrix/Auto_GEO/actions/workflows/backend-deploy.yml/badge.svg)](https://github.com/Architecture-Matrix/Auto_GEO/actions/workflows/backend-deploy.yml)

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户层 (客户端)                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Electron + Vue3 桌面应用                                 │   │
│  │  - 本地安装，无需服务器部署                                 │   │
│  │  - 直接调用后端API                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼ HTTP API
┌─────────────────────────────────────────────────────────────────┐
│                        服务层 (服务端)                            │
│  ┌──────────────┬──────────────┬─────────────────────────────┐  │
│  │   后端服务    │   n8n服务    │        RAGFlow服务          │  │
│  │  (必需)      │   (必需)     │         (可选)              │  │
│  ├──────────────┼──────────────┼─────────────────────────────┤  │
│  │ PostgreSQL   │ PostgreSQL   │ MySQL 8.0                   │  │
│  │ FastAPI      │ Redis        │ Redis                       │  │
│  │ Nginx        │ n8n Engine   │ MinIO (文档存储)            │  │
│  │ Playwright   │              │ Elasticsearch (向量检索)    │  │
│  └──────────────┴──────────────┴─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AI能力层                                  │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  DeepSeek API    │  │   RAGFlow API    │                    │
│  │  - 文章生成      │  │   - 知识检索     │                    │
│  │  - 关键词蒸馏    │  │   - 文档问答     │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术选型 | 部署方式 |
|------|---------|----------|
| 客户端 | Electron + Vue3 + TypeScript + Vite | 用户本地安装 |
| 后端 | FastAPI + PostgreSQL + Playwright + Alembic | Docker Compose |
| AI中台 | n8n 工作流引擎 + DeepSeek API | Docker Compose |
| 知识库 | RAGFlow (MySQL + Redis + ES + MinIO) | Docker Compose |

## 快速开始

### 方式一：生产部署（推荐）

完整部署文档：[deploy/README.md](./deploy/README.md)

```bash
# 1. 克隆项目
git clone https://github.com/Architecture-Matrix/Auto_GEO.git
cd Auto_GEO

# 2. 部署后端服务
cd deploy
cp .env.backend.example .env.backend
# 编辑 .env.backend 填入配置
./deploy-backend.sh

# 3. 部署 n8n（建议单独服务器）
cp .env.n8n.example .env.n8n
# 编辑 .env.n8n 填入配置
./deploy-n8n.sh

# 4. 部署 RAGFlow（可选，需8GB+内存）
# 详见 deploy/RAGFLOW-DEPLOY.md
cp .env.ragflow.example .env.ragflow
./ragflow-deploy.sh

# 5. 构建前端（供用户下载安装）
cd ../frontend
npm install
npm run build
```

### 方式二：开发环境

```bash
# 后端（终端1）
cd backend
pip install -r requirements.txt
playwright install chromium
python main.py

# 前端（终端2）
cd frontend
npm install
npm run dev
```

## 服务器规划

| 服务 | 建议配置 | 端口 | 说明 |
|------|----------|------|------|
| 后端 | 2核4GB | 80 | 可与n8n同机 |
| n8n | 2核4GB | 5678 | 可与后端同机 |
| RAGFlow | 4核8GB+ | 9380 | **建议独立服务器** |

## 功能特性

- **多平台发布**：知乎、百家号、搜狐、头条号等40+平台自动发布
- **收录检测**：豆包、千问、DeepSeek等AI搜索引擎收录检测
- **GEO文章生成**：基于关键词自动生成SEO优化文章
- **知识库管理**：RAGFlow知识库接入，支持文档问答
- **定时任务**：自动检测、失败重试、预警通知
- **数据报表**：收录趋势、平台分布、关键词排名分析

## 项目结构

```
Auto_GEO/
├── backend/              # FastAPI 后端
│   ├── api/              # API路由
│   ├── database/         # 数据库模型和迁移 (Alembic)
│   ├── services/         # 业务服务
│   ├── migrations/       # 数据库迁移脚本
│   └── main.py           # 入口文件
├── frontend/             # Electron + Vue3 前端
│   ├── electron/         # Electron主进程
│   ├── src/              # Vue源码
│   └── package.json
├── n8n/workflows/        # n8n工作流JSON文件
├── deploy/               # ⭐ 生产部署配置（部署入口）
│   ├── docker-compose.backend.yml
│   ├── docker-compose.n8n.yml
│   ├── docker-compose.ragflow.yml
│   ├── deploy-backend.sh
│   ├── deploy-n8n.sh
│   ├── ragflow-deploy.sh
│   ├── .env.backend.example
│   ├── .env.n8n.example
│   ├── .env.ragflow.example
│   ├── README.md         # 部署总览
│   └── RAGFLOW-DEPLOY.md # RAGFlow详细文档
└── docs/                 # 项目文档
    ├── architecture/     # 架构设计
    └── api.md           # API文档
```

## 部署架构

### 后端部署

```yaml
# deploy/docker-compose.backend.yml
services:
  postgres:
    image: registry.cn-hangzhou.aliyuncs.com/acs-sample/postgres:15-alpine
    # 资源限制: 2CPU / 1GB内存

  backend:
    image: crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com/opencaio/auto_geo_backend:latest
    # 资源限制: 2CPU / 2GB内存
    environment:
      - DATABASE_URL=postgresql://...
      - N8N_WEBHOOK_URL=http://n8n-server:5678/webhook
      - DEEPSEEK_API_KEY=...

  nginx:
    image: registry.cn-hangzhou.aliyuncs.com/acs-sample/nginx:alpine
    ports:
      - "80:80"
```

### n8n部署

```yaml
# deploy/docker-compose.n8n.yml
services:
  postgres:    # n8n元数据存储
  redis:       # 执行队列和缓存
  n8n:         # 工作流引擎
    ports:
      - "5678:5678"
```

### RAGFlow部署

RAGFlow资源需求较高，建议独立服务器部署。详见 [deploy/RAGFLOW-DEPLOY.md](./deploy/RAGFLOW-DEPLOY.md)

## CI/CD 自动化

| 工作流 | 触发条件 | 说明 |
|-------|---------|------|
| **Startup Validation** | Push/PR | 验证项目结构和部署配置 |
| **Backend CI** | Push/PR | Ruff检查、MyPy类型检查、单元测试、安全扫描 |
| **Backend Deploy** | Push to main | 构建镜像并部署到生产服务器 |

## 镜像说明

所有生产镜像均使用**阿里云镜像站**，国内服务器拉取更快：

| 镜像 | 地址 |
|------|------|
| PostgreSQL | `registry.cn-hangzhou.aliyuncs.com/acs-sample/postgres:15-alpine` |
| Redis | `registry.cn-hangzhou.aliyuncs.com/acs-sample/redis:7-alpine` |
| Nginx | `registry.cn-hangzhou.aliyuncs.com/acs-sample/nginx:alpine` |
| n8n | `registry.cn-hangzhou.aliyuncs.com/acs-sample/n8n:latest` |
| 后端 | `crpi-lwz264sedmauvivo.cn-guangzhou.personal.cr.aliyuncs.com/opencaio/auto_geo_backend:latest` |

## 文档

| 文档 | 说明 |
|------|------|
| [deploy/README.md](./deploy/README.md) | 生产环境部署指南 |
| [deploy/RAGFLOW-DEPLOY.md](./deploy/RAGFLOW-DEPLOY.md) | RAGFlow独立部署文档 |
| [backend/migrations/README.md](./backend/migrations/README.md) | 数据库迁移指南 |
| [docs/architecture/](./docs/architecture/) | 架构设计文档 |
| [docs/api.md](./docs/api.md) | API接口文档 |

## 更新日志

### v3.1.0 (2026-05-08) - 生产环境重构

**部署架构升级**：
- 统一使用 `deploy/` 目录作为部署入口
- 后端 + n8n + RAGFlow 三服务独立部署
- 全部使用阿里云镜像站，国内部署更快
- 新增资源限制配置（CPU/内存）
- 前端改为纯桌面应用，无需服务器部署

**数据库升级**：
- SQLite → PostgreSQL
- 新增 Alembic 数据库迁移
- 支持用户级数据隔离

### v3.0.0 (2026-02-24) - CI/CD自动化

- Startup Validation工作流
- Electron自动修复
- 完整API文档

## 许可证

MIT License

---

**维护者**: 架构矩阵团队  
**版本**: v3.1.0 (生产环境重构版)  
**更新日期**: 2026-05-08

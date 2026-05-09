# Auto_GEO 技术架构梳理与上线服务器评估

> 日期: 2026-05-01
> 版本: v1.0
> 维护者: CRO

---

## 一、当前技术栈总览

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| **后端** | Python 3.12 + FastAPI + SQLAlchemy | ~27K行代码, 17个API模块 |
| **数据库** | SQLite (当前) → PostgreSQL (建议) | 784行models, 含账号/发布/知识库/客户管理等 |
| **前端** | Vue 3 + Element Plus + Vite + Electron | 桌面客户端 + Web端 |
| **浏览器自动化** | Playwright (Chromium) | **最大资源消耗点**, 支持并发3个发布任务 |
| **工作流引擎** | n8n | 3个AI工作流 (文章生成/关键词蒸馏等) |
| **知识库** | RAGFlow (外部) | 向量检索 + 文章去重, 当前指向 `ragflow.xinzhixietong.com` |
| **AI服务** | DeepSeek + 豆包 + 通义千问 | 文章生成/重写/GEO优化 |
| **反向代理** | Nginx | SSL + 负载均衡 |
| **容器化** | Docker Compose | 多服务编排 |
| **定时任务** | APScheduler | 收录检测/文章采集等 |

### 支持平台 (30+)

知乎、百家号、搜狐号、头条号、百度文库、企鹅号、微信公众号、网易号、字节号、小红书、B站专栏、36氪、虎嗅、人人都是产品经理、抖音、快手、视频号、搜狐视频、新浪微博、好看视频、西瓜视频、简书号、爱奇艺、大鱼号、AcFun、腾讯视频、一点号、皮皮虾、美拍、豆瓣、快传号、大风号、雪球号、易车号、车家号、多多视频、腾讯微视、芒果TV、喜马拉雅、美团、支付宝、抖音企业号、自定义

---

## 二、服务依赖关系图

```
用户(Electron/浏览器)
    ↓
  Nginx (:80/:443)
    ├── /api/* → FastAPI Backend (:8001)
    │               ├── SQLite/PostgreSQL (数据存储)
    │               ├── Playwright (浏览器自动化) ← 重IO
    │               ├── n8n (:5678) → AI工作流
    │               ├── RAGFlow → 知识库/向量检索 ← 重内存
    │               └── DeepSeek/豆包/千问 API → AI生成
    └── / → 前端静态文件
```

---

## 三、各服务资源消耗分析

| 服务 | CPU | 内存 | 磁盘IO | 网络 | 说明 |
|------|-----|------|--------|------|------|
| **FastAPI后端** | 中 | 1-2GB | 低 | 中 | API处理 + 调度 |
| **Playwright** | **高** | **1-3GB/实例** | 中 | 中 | **核心瓶颈**: 每个Chromium实例约1GB, 并发3=3GB |
| **n8n** | 低-中 | 512MB-1GB | 低 | 中 | 工作流执行, 轻量 |
| **RAGFlow** | **高** | **8-16GB** | **高** | 低 | 向量检索 + Embedding计算, 最吃资源 |
| **PostgreSQL** | 中 | 1-2GB | 中 | 低 | 替代SQLite后 |
| **Nginx** | 极低 | <128MB | 极低 | 高 | 纯代理 |
| **前端静态** | 无 | 无 | 低 | 中 | CDN可卸载 |

---

## 四、推荐部署方案

### 方案A: 单服务器部署 (适合初期/MVP)

**适用场景**: 用户<50, 并发发布<5

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| **CPU** | 8核 | Playwright + RAGFlow 并行需要 |
| **内存** | 32GB | RAGFlow 8GB + Playwright 6GB + 系统/其他 6GB + 缓冲 |
| **系统盘** | 100GB SSD | OS + Docker + 日志 |
| **数据盘** | 200GB SSD | 数据库 + 知识库 + 上传文件 |
| **带宽** | 10Mbps+ | 发布文章上传图片 |

**预估月费**: 阿里云/腾讯云约 **800-1500元/月**

> **注意**: RAGFlow 自部署是这个方案需要 32GB 的主要原因。如果继续使用外部 RAGFlow 实例, 16GB 即可。

---

### 方案B: 分开部署 (推荐, 适合生产环境)

**强烈建议拆分为2-3台服务器:**

#### 服务器1: 应用服务器 (Backend + n8n + Nginx)

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| CPU | 4-8核 | Playwright并发是主要消耗 |
| 内存 | 16GB | Playwright 3并发=3GB + 后端2GB + n8n 1GB |
| 磁盘 | 100GB SSD | 日志 + Docker镜像 |
| 带宽 | 5-10Mbps | API + 文件上传 |

**预估月费**: 约 **400-600元/月**

#### 服务器2: RAGFlow 知识库专用 (最重)

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| CPU | 8核+ | Embedding计算 + 向量检索 |
| 内存 | **16-32GB** | Elasticsearch/Infinity + 模型推理 |
| 磁盘 | 200GB SSD | 向量索引 + 原始文档 |
| GPU | 可选 (推理加速) | 有GPU可降到8核+16GB |

**预估月费**: 约 **600-1200元/月** (无GPU)

> **替代方案**: 继续使用外部 RAGFlow 实例 (`ragflow.xinzhixietong.com`), 省掉这台服务器的费用。但数据安全和延迟需要评估。

#### 服务器3: 数据库服务器 (后期扩展)

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| CPU | 4核 | PostgreSQL 足够 |
| 内存 | 8GB | 缓存热点数据 |
| 磁盘 | 200GB SSD | 数据库 + 备份 |
| 特性 | 主从复制 | 读写分离 |

**预估月费**: 约 **300-500元/月**

> 初期可与应用服务器共用, 后期用户增长后再拆分。

---

## 五、数据库扩展性路线

**当前问题**: 使用 SQLite, 不支持并发写入, 无法水平扩展。

### 迁移路径

```
SQLite (当前) → PostgreSQL (推荐, 单机) → PostgreSQL 主从 (中期) → PostgreSQL + 读写分离 (长期)
```

### 具体改动点

1. `backend/config.py` — 已预留 `DATABASE_URL` 切换逻辑
2. `backend/requirements.txt` — 需添加 `psycopg2-binary` 或 `asyncpg`
3. SQLAlchemy ORM 层无需修改, 仅换连接字符串
4. `docker-compose.yml` — 添加 PostgreSQL 服务
5. 数据迁移脚本 — SQLite → PostgreSQL 数据导出导入

### PostgreSQL docker-compose 示例

```yaml
  postgres:
    image: postgres:16-alpine
    container_name: auto_geo_postgres
    environment:
      POSTGRES_DB: auto_geo
      POSTGRES_USER: autogeo
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - auto_geo_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autogeo"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    name: auto_geo_postgres_data
```

---

## 六、架构改进建议

### 1. 必须改 (上线前)

- [ ] **SQLite → PostgreSQL**: 生产环境绝不能用SQLite, 并发发布会锁库
- [ ] **Playwright 资源隔离**: 限制并发数 (当前 `MAX_CONCURRENT_PUBLISH=3`, 合理)
- [ ] **加密密钥管理**: `backend/config.py:67-71` 的默认密钥必须移除, 强制从环境变量读取
- [ ] **CORS 硬编码清理**: `backend/config.py:56-57` 硬编码了内网IP `8.138.59.152`, 上线前清理

### 2. 建议改 (上线后1-2月)

- [ ] **前端部署CDN**: 静态文件走CDN, 减轻服务器带宽压力
- [ ] **Redis缓存**: 会话管理 + 热点数据缓存 (当前无缓存层)
- [ ] **日志收集**: ELK 或 Loki, 当前仅文件日志
- [ ] **健康监控**: Prometheus + Grafana

### 3. 长期优化

- [ ] **Playwright Worker 池**: 类似浏览器农场架构, 独立服务
- [ ] **消息队列**: RabbitMQ/Redis Stream 替代当前的直接API调用模式
- [ ] **对象存储**: OSS/S3 替代本地上传文件存储

---

## 七、费用总估算

| 方案 | 月费用 | 适用场景 |
|------|--------|---------|
| **单服务器 (继续用外部RAGFlow)** | 400-800元 | 初期验证, <20用户 |
| **单服务器 (自建RAGFlow)** | 1000-1500元 | 初期, 需要完整控制 |
| **双服务器 (应用+RAGFlow分离)** | 1000-1800元 | **推荐**, 生产环境 |
| **三服务器 (完全分离)** | 1300-2300元 | 规模化, >100用户 |

---

## 八、推荐上线方案总结

### 短期 (1-3月)

**双服务器部署**:
- 应用服务器 (16GB) + RAGFlow专用 (16-32GB)
- 数据库先用 Docker 内 PostgreSQL 与应用同机

### 数据库

上线前**必须迁移到PostgreSQL**, 这是不可绕过的。

### RAGFlow

如果外部实例 (`ragflow.xinzhixietong.com`) 可靠且数据安全可接受, 可以继续用外部实例省一台服务器。

### n8n

与 Backend 同机部署即可, 资源消耗很小。

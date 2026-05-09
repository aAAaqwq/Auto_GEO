# AutoGeo 数据库改造计划

> 将SQLite改造为PostgreSQL，支持线上生产环境部署

## 1. 现状分析

### 1.1 当前架构

| 组件 | 当前配置 | 说明 |
|------|---------|------|
| 数据库 | SQLite 3 | 文件型数据库，单机使用 |
| ORM | SQLAlchemy 2.0 | 已支持，无需更换 |
| 连接池 | 内置 | SQLite不支持真正的连接池 |
| 迁移工具 | 无 | 依赖 `Base.metadata.create_all()` |

### 1.2 存在问题

1. **并发性能差**: SQLite的WAL模式虽然能改善，但高并发下仍会出现`database is locked`
2. **无法水平扩展**: 文件型数据库无法支持多实例部署
3. **数据完整性**: 缺乏完善的备份、恢复机制
4. **运维困难**: 无法使用标准数据库监控工具
5. **线上风险**: SQLite不适合生产环境高负载场景

### 1.3 模型分析

现有模型共 **15个表**：
- 账号管理: `accounts`
- 发布系统: `publish_records`, `auto_publish_tasks`, `auto_publish_records`
- GEO系统: `projects`, `keywords`, `question_variants`, `index_check_records`, `geo_articles`
- 知识库: `knowledge_categories`, `knowledge_items`
- 客户管理: `clients`
- 用户系统: `users`
- 参考文章: `reference_articles`
- 定时任务: `scheduled_tasks`
- 站点构建: `site_projects`

## 2. 改造目标

### 2.1 目标架构

```
┌─────────────────────────────────────────────────────────────┐
│                         应用层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ FastAPI  │  │ Temporal │  │  n8n     │  │ Worker   │    │
│  │ 主服务   │  │ Workflow │  │ Webhook  │  │ 任务队列  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
├───────┼─────────────┼─────────────┼─────────────┼──────────┤
│       │             │             │             │           │
│       └─────────────┴──────┬──────┴─────────────┘           │
│                            │                                 │
│                    ┌────────▼────────┐                       │
│                    │   SQLAlchemy    │                       │
│                    │   ORM Layer     │                       │
│                    └────────┬────────┘                       │
│                             │                                 │
│                    ┌────────▼────────┐                       │
│                    │  SQLAlchemy     │                       │
│                    │  Connection Pool│                       │
│                    │  (Pool Size: 20)│                       │
│                    └────────┬────────┘                       │
├─────────────────────────────┼────────────────────────────────┤
│                             │                                 │
│                    ┌────────▼────────┐                       │
│                    │   PostgreSQL    │                       │
│                    │    主数据库      │                       │
│                    │  (Docker/云托管) │                       │
│                    └────────┬────────┘                       │
│                             │                                 │
│                    ┌────────▼────────┐                       │
│                    │  Volume持久化   │                       │
│                    │  /var/lib/pgsql │                       │
│                    └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 选型理由

| 组件 | 选择 | 理由 |
|------|------|------|
| 数据库 | PostgreSQL 15+ | 功能丰富、稳定性高、开源免费 |
| 连接池 | SQLAlchemy内置 | 无需额外依赖 |
| 迁移工具 | Alembic | SQLAlchemy官方工具，无缝集成 |
| 部署 | Docker Compose | 与现有架构一致 |

## 3. 改造范围

### 3.1 需要修改的文件

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `backend/config.py` | 修改 | 添加PostgreSQL配置 |
| `backend/database/__init__.py` | 修改 | 支持多数据库类型 |
| `backend/database/models.py` | 修改 | 适配PostgreSQL类型 |
| `backend/requirements.txt` | 修改 | 添加psycopg2-binary、alembic |
| `docker-compose.yml` | 修改 | 添加PostgreSQL服务 |
| `backend/migrations/` | 新增 | Alembic迁移脚本 |
| `.env.example` | 修改 | 添加数据库配置模板 |

### 3.2 不修改的范围

- API接口层 (`backend/api/*.py`)
- 业务逻辑层 (`backend/services/*.py`)
- 前端代码

## 4. 分阶段实施计划

### Phase 1: 基础设施准备 (1天)

- [ ] 更新 `requirements.txt`，添加依赖
- [ ] 修改 `config.py`，实现数据库URL动态配置
- [ ] 创建 `database/core.py`，抽象数据库连接层
- [ ] 测试本地SQLite模式是否正常工作

### Phase 2: 模型层改造 (1天)

- [ ] 分析现有模型，识别需要调整的类型
- [ ] 修改 `models.py`，适配PostgreSQL
- [ ] 添加索引优化
- [ ] 运行单元测试验证

### Phase 3: 迁移工具集成 (1天)

- [ ] 初始化Alembic项目结构
- [ ] 创建初始迁移脚本
- [ ] 编写迁移回滚脚本
- [ ] 测试迁移流程

### Phase 4: Docker配置更新 (0.5天)

- [ ] 修改 `docker-compose.yml`
- [ ] 配置PostgreSQL数据卷
- [ ] 配置环境变量模板
- [ ] 添加健康检查

### Phase 5: 测试与验证 (1天)

- [ ] 编写数据库兼容性测试
- [ ] 测试数据迁移流程
- [ ] 性能基准测试
- [ ] 编写回滚方案

### Phase 6: 文档更新 (0.5天)

- [ ] 更新部署文档
- [ ] 编写数据库运维手册
- [ ] 更新环境变量说明

**总工期：约5天**

## 5. 关键技术点

### 5.1 数据库URL格式

```python
# SQLite (开发/测试)
DATABASE_URL=sqlite:///./auto_geo.db

# PostgreSQL (生产)
DATABASE_URL=postgresql://user:password@localhost:5432/auto_geo

# PostgreSQL with connection pool (高并发)
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/auto_geo?pool_size=20&max_overflow=0
```

### 5.2 类型映射

| SQLite类型 | PostgreSQL类型 | SQLAlchemy类型 | 说明 |
|-----------|---------------|----------------|------|
| INTEGER | INTEGER | Integer | 无需修改 |
| TEXT | TEXT | Text | 无需修改 |
| VARCHAR | VARCHAR | String | 无需修改 |
| BOOLEAN | BOOLEAN | Boolean | 无需修改 |
| DATETIME | TIMESTAMP | DateTime | 需添加timezone支持 |
| JSON | JSONB | JSON | PostgreSQL建议用JSONB |
| BLOB | BYTEA | LargeBinary | 如需二进制存储 |

### 5.3 索引优化策略

```python
# 当前已有索引
- accounts.platform
- accounts.status
- publish_records.article_id
- publish_records.account_id
- keywords.project_id
- geo_articles.keyword_id
- geo_articles.project_id

# 建议新增索引（PostgreSQL性能优化）
- accounts.last_auth_time (用于清理过期账号)
- publish_records.publish_status (查询待发布任务)
- geo_articles.publish_status (查询待发布文章)
- geo_articles.created_at (按时间排序)
- reference_articles.platform (按平台查询)
- auto_publish_tasks.status (查询待执行任务)
```

### 5.4 连接池配置

```python
# PostgreSQL连接池配置
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # 常驻连接数
    max_overflow=20,        # 最大超额连接
    pool_timeout=30,        # 获取连接超时
    pool_recycle=3600,      # 连接回收时间
    pool_pre_ping=True,     # 连接健康检查
)
```

## 6. 数据迁移方案

### 6.1 新部署场景

无需迁移，直接初始化：
```bash
# 1. 启动PostgreSQL容器
docker-compose up -d postgres

# 2. 运行迁移脚本
cd backend && alembic upgrade head

# 3. 初始化基础数据
python scripts/init_base_data.py
```

### 6.2 现有数据迁移

从SQLite迁移到PostgreSQL：
```bash
# 1. 导出SQLite数据
sqlite3 auto_geo_v3.db .dump > backup.sql

# 2. 转换SQL语法（使用工具）
pgloader sqlite:///auto_geo_v3.db postgresql://user:pass@localhost/auto_geo

# 或手动导入（简单表结构）
python scripts/migrate_sqlite_to_pg.py
```

## 7. 回滚方案

### 7.1 数据库回滚

```bash
# 1. 回滚到上一个版本
alembic downgrade -1

# 2. 回滚到指定版本
alembic downgrade <revision_id>

# 3. 回滚所有迁移
alembic downgrade base
```

### 7.2 应用回滚

如果改造出现问题，快速回退到SQLite版本：
```bash
# 1. 修改环境变量
DATABASE_URL=sqlite:///./auto_geo_v3.db

# 2. 重启应用
docker-compose restart backend
```

## 8. 风险评估

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| 数据类型不兼容 | 中 | 高 | 充分的单元测试 |
| 迁移脚本错误 | 低 | 高 | 先在测试环境验证 |
| 性能下降 | 低 | 中 | 连接池优化、索引优化 |
| 连接泄漏 | 低 | 高 | 连接池配置、监控告警 |
| Docker配置错误 | 中 | 中 | 逐步验证每个服务 |

## 9. 成功指标

- [ ] 所有现有API正常工作
- [ ] 单元测试100%通过
- [ ] 并发100请求无错误
- [ ] 数据库连接无泄漏
- [ ] 迁移流程可重复执行
- [ ] 回滚方案验证通过

---

## 附录A: 环境变量对照表

| 变量名 | SQLite配置 | PostgreSQL配置 | 说明 |
|-------|-----------|---------------|------|
| DATABASE_URL | `sqlite:///./db.sqlite3` | `postgresql://user:pass@host:5432/db` | 数据库连接URL |
| DB_POOL_SIZE | N/A | 10 | 连接池大小 |
| DB_MAX_OVERFLOW | N/A | 20 | 最大溢出连接 |
| DB_POOL_RECYCLE | N/A | 3600 | 连接回收时间(秒) |

## 附录B: 常用命令

```bash
# 初始化Alembic
cd backend && alembic init migrations

# 创建迁移脚本
alembic revision --autogenerate -m "initial migration"

# 执行迁移
alembic upgrade head

# 查看历史
alembic history

# 回滚
alembic downgrade -1

# 生成SQL（不执行）
alembic upgrade head --sql
```

# 数据库迁移说明

## 迁移文件列表

| 版本 | 文件 | 说明 |
|------|------|------|
| 0001 | 0001_initial.py | 初始表结构创建 |
| 0002 | 0002_add_user_isolation.py | 添加用户级数据隔离 |

## 执行迁移

```bash
# 开发环境
cd backend
alembic upgrade head

# Docker环境
docker-compose exec backend alembic upgrade head
```

## 回滚迁移

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到初始状态
alembic downgrade base
```

## 创建新迁移

```bash
# 修改models.py后
alembic revision --autogenerate -m "migration_name"
```

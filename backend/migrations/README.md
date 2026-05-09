# AutoGeo 数据库迁移工具

## 常用命令

### 1. 创建迁移脚本
```bash
cd backend

# 自动生成迁移脚本（检测模型变化）
alembic revision --autogenerate -m "description"

# 手动创建空迁移脚本
alembic revision -m "description"
```

### 2. 执行迁移
```bash
# 升级到最新版本
alembic upgrade head

# 升级到指定版本
alembic upgrade <revision_id>

# 升级2个版本
alembic upgrade +2

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

### 3. 回滚迁移
```bash
# 回滚1个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision_id>

# 回滚所有迁移
alembic downgrade base
```

### 4. 其他命令
```bash
# 显示SQL语句（不执行）
alembic upgrade head --sql

# 查看当前配置
alembic show <revision_id>
```

## 在Docker中执行迁移

```bash
# 进入容器执行
docker-compose exec backend alembic upgrade head

# 或者运行一次性容器
docker-compose run --rm backend alembic upgrade head
```

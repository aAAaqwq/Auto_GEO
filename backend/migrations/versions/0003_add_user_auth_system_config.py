"""
用户认证和系统配置迁移
- 扩展User表：添加role、is_active、last_login等字段
- 创建SystemConfig表：系统配置管理

Revision ID: 0003_add_user_auth_system_config
Revises: 0002_add_user_isolation
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '0003_add_user_auth_system_config'
down_revision = '0002_add_user_isolation'
branch_labels = None
depends_on = None


def upgrade():
    """添加用户认证字段和系统配置表"""

    # 检测是否为PostgreSQL
    dialect = op.get_context().dialect.name
    is_postgres = dialect == 'postgresql'

    # ==================== 扩展 User 表 ====================

    # 添加 role 字段
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=False, server_default='user'))
    op.create_index('ix_users_role', 'users', ['role'])

    # 添加 is_active 字段
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))
    op.create_index('ix_users_is_active', 'users', ['is_active'])

    # 添加 last_login 字段
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    op.create_index('ix_users_last_login', 'users', ['last_login'])

    # 添加 login_count 字段
    op.add_column('users', sa.Column('login_count', sa.Integer(), nullable=False, server_default='0'))

    # 添加安全相关字段
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))

    # 扩展 password_hash 字段长度（支持bcrypt）
    # 注意：SQLite不支持直接修改列，需要重建表
    if is_postgres:
        op.alter_column('users', 'password_hash',
                        existing_type=sa.String(length=200),
                        type_=sa.String(length=255),
                        nullable=False,
                        postgresql_using="COALESCE(password_hash, '')")
    else:
        # SQLite：先添加允许NULL的字段，然后通过数据迁移处理
        # 这里使用批量操作模式
        with op.batch_alter_table('users') as batch_op:
            batch_op.alter_column('password_hash',
                                  existing_type=sa.String(length=200),
                                  type_=sa.String(length=255),
                                  nullable=True)

    # 为 username 和 email 添加索引（如果尚未存在）
    # 注意：它们是unique的，通常已有索引，但显式确保
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ==================== 创建 SystemConfig 表 ====================

    op.create_table(
        'system_configs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('config_key', sa.String(length=100), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='general'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(length=20), nullable=False, server_default='string'),
        sa.Column('is_editable', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key')
    )

    # SystemConfig 索引
    op.create_index('ix_system_configs_config_key', 'system_configs', ['config_key'])
    op.create_index('ix_system_configs_category', 'system_configs', ['category'])
    op.create_index('ix_system_configs_is_active', 'system_configs', ['is_active'])

    # PostgreSQL特定优化：添加表注释
    if is_postgres:
        op.execute("COMMENT ON TABLE system_configs IS '系统配置表'")
        op.execute("COMMENT ON COLUMN system_configs.config_key IS '配置键（唯一标识符）'")
        op.execute("COMMENT ON COLUMN system_configs.config_value IS '配置值（JSON字符串或纯文本）'")
        op.execute("COMMENT ON COLUMN system_configs.category IS '配置分类：general=通用 auth=认证 security=安全 email=邮件 storage=存储'")
        op.execute("COMMENT ON COLUMN system_configs.value_type IS '值类型：string=字符串 int=整数 float=浮点数 bool=布尔 json=JSON对象'")
        op.execute("COMMENT ON COLUMN system_configs.is_editable IS '是否可通过界面编辑'")
        op.execute("COMMENT ON COLUMN system_configs.is_sensitive IS '是否为敏感配置（如密码、密钥）'")
        op.execute("COMMENT ON COLUMN system_configs.updated_by IS '最后更新用户ID'")

        # 更新users表注释
        op.execute("COMMENT ON COLUMN users.role IS '角色：admin=管理员 user=普通用户'")
        op.execute("COMMENT ON COLUMN users.is_active IS '是否激活：True=激活 False=禁用'")
        op.execute("COMMENT ON COLUMN users.last_login IS '最后登录时间'")
        op.execute("COMMENT ON COLUMN users.login_count IS '登录次数'")
        op.execute("COMMENT ON COLUMN users.failed_login_attempts IS '连续登录失败次数'")
        op.execute("COMMENT ON COLUMN users.locked_until IS '账户锁定截止时间'")

    print("✅ 用户认证和系统配置迁移完成")


def downgrade():
    """回滚迁移"""

    # 删除 SystemConfig 表
    op.drop_index('ix_system_configs_is_active', table_name='system_configs')
    op.drop_index('ix_system_configs_category', table_name='system_configs')
    op.drop_index('ix_system_configs_config_key', table_name='system_configs')
    op.drop_table('system_configs')

    # 删除 User 表新增字段和索引
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'login_count')
    op.drop_index('ix_users_last_login', table_name='users')
    op.drop_column('users', 'last_login')
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_column('users', 'is_active')
    op.drop_index('ix_users_role', table_name='users')
    op.drop_column('users', 'role')

    # 恢复 password_hash 字段长度
    op.alter_column('users', 'password_hash',
                    existing_type=sa.String(length=255),
                    type_=sa.String(length=200),
                    nullable=True)

    print("✅ 用户认证和系统配置回滚完成")

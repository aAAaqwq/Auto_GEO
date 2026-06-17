"""
账号增强迁移：分组、标签、健康度、操作日志
- 创建 account_groups 表
- 创建 account_operation_logs 表
- accounts 表新增字段：group_id, tags, health_score, last_check_time, auth_expires_at, browser_type, adspower_profile_id

Revision ID: 0004_account_enhancements
Revises: 0003_add_user_auth_system_config
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0004_account_enhancements'
down_revision = '0003_add_user_auth_system_config'
branch_labels = None
depends_on = None


def upgrade():
    """账号增强迁移"""

    # 检测是否为 PostgreSQL
    dialect = op.get_context().dialect.name
    is_postgres = dialect == 'postgresql'

    # ==================== 创建 account_groups 表 ====================

    op.create_table(
        'account_groups',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, comment='分组名称'),
        sa.Column('icon', sa.String(50), nullable=True, comment='分组图标'),
        sa.Column('color', sa.String(20), nullable=True, server_default='#409EFF', comment='分组颜色'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='所属用户ID'),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0', comment='排序权重'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_account_groups_user_id', 'account_groups', ['user_id'])

    # ==================== 创建 account_operation_logs 表 ====================

    op.create_table(
        'account_operation_logs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('account_id', sa.Integer(), nullable=True, comment='账号ID'),
        sa.Column('user_id', sa.Integer(), nullable=True, comment='操作用户ID'),
        sa.Column('operation', sa.String(50), nullable=False, comment='操作类型'),
        sa.Column('detail', sa.JSON(), nullable=True, comment='操作详情'),
        sa.Column('ip_address', sa.String(50), nullable=True, comment='操作IP'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_aol_account_id', 'account_operation_logs', ['account_id'])
    op.create_index('ix_aol_user_id', 'account_operation_logs', ['user_id'])
    op.create_index('ix_aol_operation', 'account_operation_logs', ['operation'])

    # ==================== accounts 表新增字段 ====================

    # 分组
    op.add_column('accounts', sa.Column('group_id', sa.Integer(), nullable=True, comment='账号分组ID'))
    op.create_foreign_key('fk_accounts_group_id', 'accounts', 'account_groups', ['group_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_accounts_group_id', 'accounts', ['group_id'])

    # 标签
    if is_postgres:
        op.add_column('accounts', sa.Column('tags', sa.JSON(), nullable=True, comment='标签列表'))
    else:
        # SQLite 兼容：使用 Text 存 JSON
        op.add_column('accounts', sa.Column('tags', sa.Text(), nullable=True, comment='标签列表(JSON)'))

    # 健康度
    op.add_column('accounts', sa.Column('health_score', sa.Integer(), nullable=True, server_default='100', comment='健康度评分'))
    op.add_column('accounts', sa.Column('last_check_time', sa.DateTime(), nullable=True, comment='最后检测时间'))
    op.add_column('accounts', sa.Column('auth_expires_at', sa.DateTime(), nullable=True, comment='预估过期时间'))

    # 浏览器类型
    op.add_column('accounts', sa.Column('browser_type', sa.String(20), nullable=True, server_default='playwright', comment='浏览器类型'))
    op.add_column('accounts', sa.Column('adspower_profile_id', sa.String(100), nullable=True, comment='AdsPower Profile ID'))

    # PostgreSQL 特定注释
    if is_postgres:
        op.execute("COMMENT ON TABLE account_groups IS '账号分组表'")
        op.execute("COMMENT ON TABLE account_operation_logs IS '账号操作日志表'")

    print("✅ 账号增强迁移完成（分组、标签、健康度、操作日志）")


def downgrade():
    """回滚迁移"""

    # 删除 accounts 新增字段
    op.drop_column('accounts', 'adspower_profile_id')
    op.drop_column('accounts', 'browser_type')
    op.drop_column('accounts', 'auth_expires_at')
    op.drop_column('accounts', 'last_check_time')
    op.drop_column('accounts', 'health_score')
    op.drop_column('accounts', 'tags')

    op.drop_index('ix_accounts_group_id', table_name='accounts')
    op.drop_constraint('fk_accounts_group_id', 'accounts')
    op.drop_column('accounts', 'group_id')

    # 删除新表
    op.drop_index('ix_aol_operation', table_name='account_operation_logs')
    op.drop_index('ix_aol_user_id', table_name='account_operation_logs')
    op.drop_index('ix_aol_account_id', table_name='account_operation_logs')
    op.drop_table('account_operation_logs')

    op.drop_index('ix_account_groups_user_id', table_name='account_groups')
    op.drop_table('account_groups')

    print("✅ 账号增强迁移已回滚")

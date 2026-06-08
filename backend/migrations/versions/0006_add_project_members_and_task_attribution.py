"""
添加项目成员表和任务归属字段
- 新增 project_members 表（项目成员权限）
- auto_publish_tasks 新增字段：triggered_by_user_id, feishu_event_id

Revision ID: 0006_add_project_members_and_task_attribution
Revises: 0005_feishu_optimization
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '0006_add_project_members_and_task_attribution'
down_revision = '0005_feishu_optimization'
branch_labels = None
depends_on = None


def upgrade():
    """添加项目成员表和任务归属字段"""

    # 检测是否为 PostgreSQL
    dialect = op.get_context().dialect.name
    is_postgres = dialect == 'postgresql'

    # ==================== 创建 project_members 表 ====================

    op.create_table(
        'project_members',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=False, comment='项目ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
        sa.Column('role', sa.String(20), server_default='owner', comment='角色：owner=拥有者 editor=编辑者 viewer=观察者'),
        sa.Column('status', sa.Integer(), server_default='1', comment='状态：1=正常 0=已移除'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pm_project_id', 'project_members', ['project_id'])
    op.create_index('ix_pm_user_id', 'project_members', ['user_id'])

    # ==================== 创建 feishu_binding_codes 表 ====================

    op.create_table(
        'feishu_binding_codes',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('code', sa.String(20), nullable=False, comment='绑定码（6位随机字符）'),
        sa.Column('system_user_id', sa.Integer(), nullable=False, comment='待绑定的系统用户ID'),
        sa.Column('status', sa.Integer(), server_default='0', comment='状态：0=待使用 1=已使用 -1=已过期'),
        sa.Column('used_by_open_id', sa.String(200), nullable=True, comment='使用此码的飞书 open_id'),
        sa.Column('expires_at', sa.DateTime(), nullable=False, comment='过期时间（生成后30分钟有效）'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('used_at', sa.DateTime(), nullable=True, comment='使用时间'),
        sa.ForeignKeyConstraint(['system_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fbc_code', 'feishu_binding_codes', ['code'], unique=True)
    op.create_index('ix_fbc_system_user_id', 'feishu_binding_codes', ['system_user_id'])

    # ==================== auto_publish_tasks 新增字段 ====================

    op.add_column(
        'auto_publish_tasks',
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True, comment='触发此任务的系统用户ID'),
    )
    op.create_index('ix_apt_triggered_by_user_id', 'auto_publish_tasks', ['triggered_by_user_id'])
    op.create_foreign_key(
        'fk_apt_triggered_by_user_id',
        'auto_publish_tasks', 'users',
        ['triggered_by_user_id'], ['id'],
        ondelete='SET NULL',
    )

    op.add_column(
        'auto_publish_tasks',
        sa.Column('feishu_event_id', sa.String(200), nullable=True, comment='关联的飞书事件ID（可追溯）'),
    )

    # PostgreSQL 特定注释
    if is_postgres:
        op.execute("COMMENT ON TABLE project_members IS '项目成员表'")
        op.execute("COMMENT ON COLUMN auto_publish_tasks.triggered_by_user_id IS '触发此任务的系统用户ID'")
        op.execute("COMMENT ON COLUMN auto_publish_tasks.feishu_event_id IS '关联的飞书事件ID'")

    print("✅ 项目成员表和任务归属字段迁移完成")


def downgrade():
    """回滚迁移"""

    # auto_publish_tasks 字段回滚
    op.drop_constraint('fk_apt_triggered_by_user_id', 'auto_publish_tasks', type_='foreignkey')
    op.drop_index('ix_apt_triggered_by_user_id', table_name='auto_publish_tasks')
    op.drop_column('auto_publish_tasks', 'feishu_event_id')
    op.drop_column('auto_publish_tasks', 'triggered_by_user_id')

    # feishu_binding_codes 回滚
    op.drop_index('ix_fbc_system_user_id', table_name='feishu_binding_codes')
    op.drop_index('ix_fbc_code', table_name='feishu_binding_codes')
    op.drop_table('feishu_binding_codes')

    # project_members 回滚
    op.drop_index('ix_pm_user_id', table_name='project_members')
    op.drop_index('ix_pm_project_id', table_name='project_members')
    op.drop_table('project_members')

    print("✅ 项目成员表和任务归属字段迁移已回滚")

"""
飞书自动化发布系统优化迁移
- 新增 feishu_user_bindings 表（飞书用户绑定）
- 新增 feishu_events 表（飞书事件持久化）
- 新增 keyword_usage_records 表（关键词使用记录）
- geo_articles 表新增字段：fact_risk_score, duplication_score, platform_risk_score

Revision ID: 0005_feishu_optimization
Revises: 0004_account_enhancements
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '0005_feishu_optimization'
down_revision = '0004_account_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    """飞书优化迁移"""

    # 检测是否为 PostgreSQL
    dialect = op.get_context().dialect.name
    is_postgres = dialect == 'postgresql'

    # ==================== 创建 feishu_user_bindings 表 ====================

    op.create_table(
        'feishu_user_bindings',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('open_id', sa.String(200), nullable=False, comment='飞书用户 open_id'),
        sa.Column('union_id', sa.String(200), nullable=True, comment='飞书 union_id'),
        sa.Column('system_user_id', sa.Integer(), nullable=False, comment='绑定的系统用户ID'),
        sa.Column('default_client_id', sa.Integer(), nullable=True, comment='默认客户ID'),
        sa.Column('default_project_id', sa.Integer(), nullable=True, comment='默认项目ID'),
        sa.Column('status', sa.Integer(), server_default='1', comment='绑定状态：1=已绑定 0=已解绑'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['system_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['default_client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['default_project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fub_open_id', 'feishu_user_bindings', ['open_id'], unique=True)
    op.create_index('ix_fub_system_user_id', 'feishu_user_bindings', ['system_user_id'])

    # ==================== 创建 feishu_events 表 ====================

    op.create_table(
        'feishu_events',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('event_id', sa.String(200), nullable=False, comment='飞书事件唯一ID'),
        sa.Column('message_id', sa.String(200), nullable=True, comment='飞书消息ID'),
        sa.Column('open_id', sa.String(200), nullable=True, comment='发送者 open_id'),
        sa.Column('chat_id', sa.String(200), nullable=True, comment='会话ID'),
        sa.Column('event_type', sa.String(100), nullable=True, comment='事件类型'),
        sa.Column('raw_payload', sa.Text(), nullable=True, comment='原始请求体'),
        sa.Column('raw_text', sa.Text(), nullable=True, comment='提取的用户消息文本'),
        sa.Column('status', sa.String(20), server_default='received', comment='处理状态'),
        sa.Column('error_msg', sa.Text(), nullable=True, comment='处理错误信息'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(), nullable=True, comment='处理完成时间'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fe_event_id', 'feishu_events', ['event_id'], unique=True)
    op.create_index('ix_fe_open_id', 'feishu_events', ['open_id'])

    # ==================== 创建 keyword_usage_records 表 ====================

    op.create_table(
        'keyword_usage_records',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=True, comment='所属项目ID'),
        sa.Column('keyword_id', sa.Integer(), nullable=True, comment='关键词ID'),
        sa.Column('keyword_text', sa.String(200), nullable=False, comment='关键词文本'),
        sa.Column('article_id', sa.Integer(), nullable=True, comment='生成的文章ID'),
        sa.Column('source', sa.String(50), server_default='auto', comment='使用来源'),
        sa.Column('used_by_user_id', sa.Integer(), nullable=True, comment='触发使用的用户ID'),
        sa.Column('used_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['keyword_id'], ['keywords.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['article_id'], ['geo_articles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['used_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_kur_project_id', 'keyword_usage_records', ['project_id'])
    op.create_index('ix_kur_keyword_id', 'keyword_usage_records', ['keyword_id'])
    op.create_index('ix_kur_used_by_user_id', 'keyword_usage_records', ['used_by_user_id'])

    # ==================== geo_articles 表新增字段 ====================

    op.add_column('geo_articles', sa.Column('fact_risk_score', sa.Integer(), nullable=True, comment='事实风险评估 0-100'))
    op.add_column('geo_articles', sa.Column('duplication_score', sa.Integer(), nullable=True, comment='与历史文章重复度 0-100'))
    op.add_column('geo_articles', sa.Column('platform_risk_score', sa.Integer(), nullable=True, comment='平台合规风险 0-100'))

    # PostgreSQL 特定注释
    if is_postgres:
        op.execute("COMMENT ON TABLE feishu_user_bindings IS '飞书用户绑定表'")
        op.execute("COMMENT ON TABLE feishu_events IS '飞书事件持久化表'")
        op.execute("COMMENT ON TABLE keyword_usage_records IS '关键词使用记录表'")

    print("✅ 飞书自动化发布系统优化迁移完成")


def downgrade():
    """回滚迁移"""

    # geo_articles 字段回滚
    op.drop_column('geo_articles', 'platform_risk_score')
    op.drop_column('geo_articles', 'duplication_score')
    op.drop_column('geo_articles', 'fact_risk_score')

    # keyword_usage_records 回滚
    op.drop_index('ix_kur_used_by_user_id', table_name='keyword_usage_records')
    op.drop_index('ix_kur_keyword_id', table_name='keyword_usage_records')
    op.drop_index('ix_kur_project_id', table_name='keyword_usage_records')
    op.drop_table('keyword_usage_records')

    # feishu_events 回滚
    op.drop_index('ix_fe_open_id', table_name='feishu_events')
    op.drop_index('ix_fe_event_id', table_name='feishu_events')
    op.drop_table('feishu_events')

    # feishu_user_bindings 回滚
    op.drop_index('ix_fub_system_user_id', table_name='feishu_user_bindings')
    op.drop_index('ix_fub_open_id', table_name='feishu_user_bindings')
    op.drop_table('feishu_user_bindings')

    print("✅ 飞书自动化发布系统优化迁移已回滚")

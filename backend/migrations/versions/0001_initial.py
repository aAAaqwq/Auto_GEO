"""
初始数据库迁移
创建所有核心表结构
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建初始表结构"""

    # 检测是否为PostgreSQL
    dialect = op.get_context().dialect.name
    is_postgres = dialect == 'postgresql'

    # accounts 表
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('account_name', sa.String(length=100), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('cookies', sa.Text(), nullable=True),
        sa.Column('storage_state', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.Integer(), default=1),
        sa.Column('last_auth_time', sa.DateTime(), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_accounts_platform', 'accounts', ['platform'])
    op.create_index('idx_accounts_status', 'accounts', ['status'])

    # clients 表
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('contact_person', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Integer(), default=1),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # projects 表
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('domain_keyword', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('status', sa.Integer(), default=1),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_projects_client_id', 'projects', ['client_id'])

    # keywords 表
    op.create_table(
        'keywords',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('keyword', sa.String(length=200), nullable=False),
        sa.Column('difficulty_score', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_keywords_project_id', 'keywords', ['project_id'])

    # geo_articles 表
    op.create_table(
        'geo_articles',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('keyword_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('ai_score', sa.Integer(), nullable=True),
        sa.Column('readability_score', sa.Integer(), nullable=True),
        sa.Column('quality_status', sa.String(length=20), default='pending'),
        sa.Column('platform', sa.String(length=50), nullable=True),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('publish_status', sa.String(length=20), default='draft'),
        sa.Column('publish_time', sa.DateTime(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('target_platforms', sa.JSON(), nullable=True),
        sa.Column('publish_strategy', sa.String(length=20), default='draft'),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('publish_logs', sa.Text(), nullable=True),
        sa.Column('platform_url', sa.String(length=500), nullable=True),
        sa.Column('index_status', sa.String(length=20), default='uncheck'),
        sa.Column('last_check_time', sa.DateTime(), nullable=True),
        sa.Column('index_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['keyword_id'], ['keywords.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_geo_articles_keyword_id', 'geo_articles', ['keyword_id'])
    op.create_index('idx_geo_articles_project_id', 'geo_articles', ['project_id'])
    op.create_index('idx_geo_articles_publish_status', 'geo_articles', ['publish_status'])
    op.create_index('idx_geo_articles_created_at', 'geo_articles', ['created_at'])

    # publish_records 表
    op.create_table(
        'publish_records',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('publish_status', sa.Integer(), default=0),
        sa.Column('platform_url', sa.String(length=500), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['article_id'], ['geo_articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_publish_records_article_id', 'publish_records', ['article_id'])
    op.create_index('idx_publish_records_account_id', 'publish_records', ['account_id'])

    # 其他表的创建...（根据需要添加）

    # PostgreSQL特定优化
    if is_postgres:
        # 添加表注释
        op.execute("COMMENT ON TABLE accounts IS '账号表'")
        op.execute("COMMENT ON TABLE clients IS '客户表'")
        op.execute("COMMENT ON TABLE projects IS '项目表'")
        op.execute("COMMENT ON TABLE keywords IS '关键词表'")
        op.execute("COMMENT ON TABLE geo_articles IS 'GEO文章表'")
        op.execute("COMMENT ON TABLE publish_records IS '发布记录表'")

    print("✅ 初始表结构创建完成")


def downgrade() -> None:
    """回滚：删除所有表"""
    op.drop_table('publish_records')
    op.drop_table('geo_articles')
    op.drop_table('keywords')
    op.drop_table('projects')
    op.drop_table('clients')
    op.drop_table('accounts')
    print("✅ 所有表已删除")

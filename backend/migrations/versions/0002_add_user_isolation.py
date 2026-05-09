"""
用户级数据隔离迁移
添加user_id关联到各业务表

Revision ID: 0002_add_user_isolation
Revises: 0001_initial
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '0002_add_user_isolation'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    """添加用户级数据隔离"""

    # accounts表添加user_id
    op.add_column('accounts', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_accounts_user_id', 'accounts', 'users', ['user_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_accounts_user_id', 'accounts', ['user_id'])

    # geo_articles表添加user_id
    op.add_column('geo_articles', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_geo_articles_user_id', 'geo_articles', 'users', ['user_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_geo_articles_user_id', 'geo_articles', ['user_id'])

    # projects表添加user_id
    op.add_column('projects', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_projects_user_id', 'projects', 'users', ['user_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # site_projects表添加user_id
    op.add_column('site_projects', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_site_projects_user_id', 'site_projects', 'users', ['user_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_site_projects_user_id', 'site_projects', ['user_id'])

    # 添加软删除字段
    for table in ['accounts', 'geo_articles', 'projects', 'site_projects']:
        op.add_column(table, sa.Column('deleted_at', sa.DateTime(), nullable=True))
        op.create_index(f'ix_{table}_deleted_at', table, ['deleted_at'])


def downgrade():
    """回滚迁移"""

    # 删除软删除字段
    for table in ['accounts', 'geo_articles', 'projects', 'site_projects']:
        op.drop_index(f'ix_{table}_deleted_at', table_name=table)
        op.drop_column(table, 'deleted_at')

    # 删除user_id相关
    op.drop_index('ix_site_projects_user_id', table_name='site_projects')
    op.drop_constraint('fk_site_projects_user_id', 'site_projects')
    op.drop_column('site_projects', 'user_id')

    op.drop_index('ix_projects_user_id', table_name='projects')
    op.drop_constraint('fk_projects_user_id', 'projects')
    op.drop_column('projects', 'user_id')

    op.drop_index('ix_geo_articles_user_id', table_name='geo_articles')
    op.drop_constraint('fk_geo_articles_user_id', 'geo_articles')
    op.drop_column('geo_articles', 'user_id')

    op.drop_index('ix_accounts_user_id', table_name='accounts')
    op.drop_constraint('fk_accounts_user_id', 'accounts')
    op.drop_column('accounts', 'user_id')

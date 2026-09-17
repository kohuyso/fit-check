"""Initial schema with users, closet, outfits, calendar, chat, and pgvector

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-09 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Kích hoạt extension vector nếu trên PostgreSQL
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Tạo bảng users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('google_id', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('preferred_style', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)

    # 3. Tạo bảng clothing_items
    op.create_table(
        'clothing_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('color_name', sa.String(), nullable=True),
        sa.Column('color_code', sa.String(), nullable=False),
        sa.Column('style_tag', sa.String(), nullable=False),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_ai_fixed', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('description_text', sa.Text(), nullable=True),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clothing_items_id'), 'clothing_items', ['id'], unique=False)
    op.create_index(op.f('ix_clothing_items_user_id'), 'clothing_items', ['user_id'], unique=False)
    op.create_index(op.f('ix_clothing_items_category'), 'clothing_items', ['category'], unique=False)
    op.create_index(op.f('ix_clothing_items_style_tag'), 'clothing_items', ['style_tag'], unique=False)

    if conn.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS clothing_items_embedding_hnsw_idx "
            "ON clothing_items USING hnsw (embedding vector_cosine_ops);"
        )

    # 4. Tạo bảng outfit_combos
    op.create_table(
        'outfit_combos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('style_type', sa.String(), nullable=True),
        sa.Column('is_bookmarked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outfit_combos_id'), 'outfit_combos', ['id'], unique=False)

    # 5. Tạo bảng trung gian outfit_item_association
    op.create_table(
        'outfit_item_association',
        sa.Column('outfit_id', sa.Integer(), nullable=True),
        sa.Column('clothing_item_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['clothing_item_id'], ['clothing_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outfit_id'], ['outfit_combos.id'], ondelete='CASCADE')
    )

    # 6. Tạo bảng user_calendar
    op.create_table(
        'user_calendar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('outfit_combo_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('event_title', sa.String(), nullable=True),
        sa.Column('weather_status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['outfit_combo_id'], ['outfit_combos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_calendar_id'), 'user_calendar', ['id'], unique=False)

    # 7. Tạo bảng chat_messages
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('suggested_outfit_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.String(), nullable=True),
        sa.Column('feedback_comment', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['suggested_outfit_id'], ['outfit_combos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('user_calendar')
    op.drop_table('outfit_item_association')
    op.drop_table('outfit_combos')
    op.drop_table('clothing_items')
    op.drop_table('users')

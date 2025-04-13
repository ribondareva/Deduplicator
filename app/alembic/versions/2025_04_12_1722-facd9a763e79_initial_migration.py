"""Initial migration

Revision ID: facd9a763e79
Revises: 
Create Date: 2025-04-12 17:22:06.039186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'facd9a763e79'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        'events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('client_id', sa.String(), nullable=True),
        sa.Column('event_datetime', sa.DateTime(timezone=True), nullable=True),
        sa.Column('inserted_dt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sid', sa.String(), nullable=True),
        sa.Column('r', sa.String(), nullable=True),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('event_hash', sa.String(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(op.f('ix_events_client_id'), 'events', ['client_id'], unique=False)
    op.create_index(op.f('ix_events_event_id'), 'events', ['event_id'], unique=False)
    op.create_index(op.f('ix_events_event_hash'), 'events', ['event_hash'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_events_event_id'), table_name='events')
    op.drop_index(op.f('ix_events_client_id'), table_name='events')
    op.drop_index(op.f('ix_events_event_hash'), table_name='events')
    op.drop_table('events')
    # ### end Alembic commands ###

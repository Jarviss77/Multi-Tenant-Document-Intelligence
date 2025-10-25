"""start end char int

Revision ID: 3731b21f4b6d
Revises: 50e5b8530ad1
Create Date: 2025-10-23 15:41:22.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3731b21f4b6d'
down_revision = '50e5b8530ad1'
branch_labels = None
depends_on = None


def upgrade():
    # Simple conversion with explicit casting
    op.alter_column('chunks', 'start_char',
               existing_type=sa.VARCHAR(),
               type_=sa.Integer(),
               postgresql_using='start_char::integer')

    op.alter_column('chunks', 'end_char',
               existing_type=sa.VARCHAR(),
               type_=sa.Integer(),
               postgresql_using='end_char::integer')


def downgrade():
    # Convert back to VARCHAR
    op.alter_column('chunks', 'start_char',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR())

    op.alter_column('chunks', 'end_char',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR())
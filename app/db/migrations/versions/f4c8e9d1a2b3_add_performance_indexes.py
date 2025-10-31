"""Add performance indexes

Revision ID: f4c8e9d1a2b3
Revises: bf218b260b3b
Create Date: 2025-10-31 21:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c8e9d1a2b3'
down_revision: Union[str, Sequence[str], None] = 'bf218b260b3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for performance optimization."""
    
    # Add error_message column to embedding_jobs if not exists
    # This column is used by the task processor
    with op.batch_alter_table('embedding_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('error_message', sa.String(), nullable=True))
    
    # Add indexes on chunks table
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'], unique=False)
    op.create_index('ix_chunks_tenant_id', 'chunks', ['tenant_id'], unique=False)
    op.create_index('idx_chunks_tenant_document', 'chunks', ['tenant_id', 'document_id'], unique=False)
    
    # Add indexes on documents table
    op.create_index('ix_documents_tenant_id', 'documents', ['tenant_id'], unique=False)
    op.create_index('ix_documents_created_at', 'documents', ['created_at'], unique=False)
    
    # Add indexes on embedding_jobs table
    op.create_index('ix_embedding_jobs_document_id', 'embedding_jobs', ['document_id'], unique=False)
    op.create_index('ix_embedding_jobs_tenant_id', 'embedding_jobs', ['tenant_id'], unique=False)
    op.create_index('ix_embedding_jobs_chunk_id', 'embedding_jobs', ['chunk_id'], unique=False)
    op.create_index('ix_embedding_jobs_status', 'embedding_jobs', ['status'], unique=False)
    op.create_index('idx_embedding_jobs_tenant_status', 'embedding_jobs', ['tenant_id', 'status'], unique=False)


def downgrade() -> None:
    """Remove performance indexes."""
    
    # Drop indexes on embedding_jobs table
    op.drop_index('idx_embedding_jobs_tenant_status', table_name='embedding_jobs')
    op.drop_index('ix_embedding_jobs_status', table_name='embedding_jobs')
    op.drop_index('ix_embedding_jobs_chunk_id', table_name='embedding_jobs')
    op.drop_index('ix_embedding_jobs_tenant_id', table_name='embedding_jobs')
    op.drop_index('ix_embedding_jobs_document_id', table_name='embedding_jobs')
    
    # Drop indexes on documents table
    op.drop_index('ix_documents_created_at', table_name='documents')
    op.drop_index('ix_documents_tenant_id', table_name='documents')
    
    # Drop indexes on chunks table
    op.drop_index('idx_chunks_tenant_document', table_name='chunks')
    op.drop_index('ix_chunks_tenant_id', table_name='chunks')
    op.drop_index('ix_chunks_document_id', table_name='chunks')
    
    # Drop error_message column from embedding_jobs
    with op.batch_alter_table('embedding_jobs', schema=None) as batch_op:
        batch_op.drop_column('error_message')

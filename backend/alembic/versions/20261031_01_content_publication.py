"""Independent textbook page index and traceable content publication."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '20261031_01'
down_revision = '20261018_01'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('content_citations',sa.Column('verification_origin',sa.String(32),nullable=False,server_default='native'))
    op.execute("""UPDATE content_citations SET verification_origin=CASE
      WHEN status IN ('verified','disputed') AND (verified_by IS NULL OR verified_at IS NULL)
        THEN 'legacy_unattributed'
      WHEN status IN ('verified','disputed') THEN 'attributed' ELSE 'unreviewed' END""")
    op.create_table('chapter_textbook_pages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chapter_id', sa.Integer(), sa.ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_key', sa.String(64), sa.ForeignKey('textbook_sources.key', ondelete='RESTRICT'), nullable=False),
        sa.Column('page', sa.Integer(), nullable=False),
        sa.CheckConstraint('page > 0', name='ck_chapter_textbook_page_positive'),
        sa.UniqueConstraint('chapter_id','source_key','page', name='uq_chapter_textbook_page'))
    op.create_index('ix_chapter_textbook_pages_chapter_id','chapter_textbook_pages',['chapter_id'])
    op.create_index('ix_chapter_textbook_pages_source_key','chapter_textbook_pages',['source_key'])
    op.create_table('content_publications',sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('manifest_sha256',sa.String(64),nullable=False),sa.Column('receipt',JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table('citation_metadata_history',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('citation_id',sa.Integer(),nullable=False),sa.Column('reason',sa.String(100),nullable=False),
        sa.Column('previous',JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_citation_metadata_history_citation_id','citation_metadata_history',['citation_id'])
    # Freeze the existing visible gallery once; later Citation edits do not mutate it.
    op.execute("""INSERT INTO chapter_textbook_pages(chapter_id,source_key,page)
      SELECT DISTINCT c.target_id,c.source_key,p
      FROM content_citations c JOIN chapters ch ON ch.id=c.target_id
      CROSS JOIN LATERAL generate_series(c.page_start,COALESCE(c.page_end,c.page_start)) p
      WHERE c.target_type='chapter' AND c.status='verified' AND c.page_start>0
        AND COALESCE(c.page_end,c.page_start) BETWEEN c.page_start AND c.page_start+200
      ON CONFLICT DO NOTHING""")
    # Retain real historical attribution before removing contradictory active metadata.
    op.execute("""INSERT INTO citation_metadata_history(citation_id,reason,previous)
      SELECT id,'unverified_with_attribution',jsonb_build_object('status',status,
        'verified_by',verified_by,'verified_at',verified_at,'updated_at',updated_at)
      FROM content_citations WHERE status='unverified'
        AND (verified_by IS NOT NULL OR verified_at IS NOT NULL)""")
    op.execute("UPDATE content_citations SET verified_by=NULL,verified_at=NULL WHERE status='unverified' AND (verified_by IS NOT NULL OR verified_at IS NOT NULL)")

def downgrade():
    # Previous application images ignore these additive tables. Keep receipts and
    # attribution history during code rollback; data rollback needs a scoped plan.
    raise RuntimeError('Forward-only audit migration: roll back the application image; preserve publication and attribution history')

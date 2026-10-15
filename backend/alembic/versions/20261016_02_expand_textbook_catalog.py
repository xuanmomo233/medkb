"""expand tenth-edition textbook catalog

Revision ID: 20261016_02
Revises: 20261016_01
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20261016_02"
down_revision = "20261016_01"
branch_labels = None
depends_on = None

TEXTBOOKS = (
    ("rjws-pathophysiology-10", "病理生理学", "病理生理学"),
    ("rjws-pediatrics-10", "儿科学", "儿科学"),
    ("rjws-dermatology-venereology-10", "皮肤性病学", "皮肤性病学"),
    ("rjws-parasitology-10", "人体寄生虫学", "人体寄生虫学"),
    ("rjws-pharmacology-10", "药理学", "药理学"),
    ("rjws-obstetrics-gynecology-10", "妇产科学", "妇产科学"),
    ("rjws-histology-embryology-10", "组织学与胚胎学", "组织学与胚胎学"),
)


def upgrade() -> None:
    source_table = sa.table(
        "textbook_sources", sa.column("key"), sa.column("title"), sa.column("subject"),
        sa.column("publisher"), sa.column("edition"), sa.column("active"),
    )
    op.bulk_insert(source_table, [
        {"key": key, "title": title, "subject": subject, "publisher": "人民卫生出版社",
         "edition": "第十版", "active": True}
        for key, title, subject in TEXTBOOKS
    ])


def downgrade() -> None:
    source_table = sa.table("textbook_sources", sa.column("key"))
    op.execute(source_table.delete().where(source_table.c.key.in_([row[0] for row in TEXTBOOKS])))

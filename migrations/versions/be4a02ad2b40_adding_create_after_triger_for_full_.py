"""Adding create_after triger for full text search of Marks table

Revision ID: be4a02ad2b40
Revises: c6b2fd1e0983
Create Date: 2024-02-13 16:19:34.629125

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be4a02ad2b40'
down_revision = 'c6b2fd1e0983'
branch_labels = None
depends_on = None

add_full_text_search_sql = """
    ALTER TABLE marks \
    ADD FULLTEXT INDEX `fulltext_marks` \
    (`title`, `description`, `full_html`, `url`)
"""

remove_full_text_search_sql = """
    ALTER TABLE marks \
    DROP FULLTEXT INDEX `fulltext_marks`
"""


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute(add_full_text_search_sql)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # with op.batch_alter_table('marks', schema=None) as batch_op:
    #     batch_op.drop_column('deleted')
    op.execute(add_full_text_search_sql)
    # ### end Alembic commands ###

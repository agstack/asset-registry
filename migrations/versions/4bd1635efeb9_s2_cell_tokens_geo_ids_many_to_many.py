"""S2 cell tokens, Geo Ids many to many

Revision ID: 4bd1635efeb9
Revises: 
Create Date: 2022-12-20 00:39:48.252677

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '4bd1635efeb9'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('geo_ids',
    sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
    sa.Column('geo_id', sa.String(), nullable=True),
    sa.Column('geo_data', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('geo_id')
    )
    op.create_table('s2_cell_tokens',
    sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
    sa.Column('cell_token', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cell_token')
    )
    op.create_table('cells_geo_ids',
    sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
    sa.Column('geo_id', UUID(), nullable=True),
    sa.Column('cell_id', UUID(), nullable=True),
    sa.ForeignKeyConstraint(['cell_id'], ['s2_cell_tokens.id'], ),
    sa.ForeignKeyConstraint(['geo_id'], ['geo_ids.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('cells_geo_ids')
    op.drop_table('s2_cell_tokens')
    op.drop_table('geo_ids')
    # ### end Alembic commands ###

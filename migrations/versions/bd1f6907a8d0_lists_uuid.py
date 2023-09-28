"""lists_uuid

Revision ID: bd1f6907a8d0
Revises: cf6ed137b0e4
Create Date: 2023-09-28 21:22:51.707992

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bd1f6907a8d0'
down_revision = 'cf6ed137b0e4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('lists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('uuid', sa.String(), nullable=False))
        batch_op.create_unique_constraint(None, ['uuid'])
        batch_op.drop_column('updated_at')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('lists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='unique')
        batch_op.drop_column('uuid')

    # ### end Alembic commands ###

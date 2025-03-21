"""lists of geoids

Revision ID: cf6ed137b0e4
Revises: 2742e8bafcc6
Create Date: 2023-09-20 08:31:04.271804

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'cf6ed137b0e4'
down_revision = '2742e8bafcc6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('lists',
     sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lists', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lists_id'), ['id'], unique=False)

    op.create_table('list_geo_ids',
     sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
    sa.Column('list_id', UUID(), nullable=True),
    sa.Column('geo_id', UUID(), nullable=True),
    sa.ForeignKeyConstraint(['geo_id'], ['geo_ids.id'], ),
    sa.ForeignKeyConstraint(['list_id'], ['lists.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('list_geo_ids', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_list_geo_ids_id'), ['id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('list_geo_ids', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_list_geo_ids_id'))

    op.drop_table('list_geo_ids')
    with op.batch_alter_table('lists', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lists_id'))

    op.drop_table('lists')
    # ### end Alembic commands ###

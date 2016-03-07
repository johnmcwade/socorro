"""Adding ADU by build ID.

Revision ID: 58d0dc2f6aa4
Revises: 3a5471a358bf
Create Date: 2013-12-02 10:41:26.866644

"""

# revision identifiers, used by Alembic.
revision = '58d0dc2f6aa4'
down_revision = '46c7fb8a8671'

from alembic import op
from socorrolib.lib import citexttype, jsontype
from socorrolib.lib.migrations import fix_permissions, load_stored_proc

import sqlalchemy as sa
from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column




def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table(u'crash_adu_by_build_signature',
    sa.Column(u'crash_adu_by_build_signature_id', sa.INTEGER(), nullable=False),
    sa.Column(u'signature_id', sa.INTEGER(), nullable=False),
    sa.Column(u'signature', citexttype.CitextType(), nullable=False),
    sa.Column(u'adu_date', sa.DATE(), nullable=False),
    sa.Column(u'build_date', sa.DATE(), nullable=False),
    sa.Column(u'buildid', sa.NUMERIC(), server_default='0', nullable=False),
    sa.Column(u'crash_count', sa.INTEGER(), server_default='0', nullable=False),
    sa.Column(u'adu_count', sa.INTEGER(), server_default='0', nullable=False),
    sa.Column(u'os_name', citexttype.CitextType(), nullable=False),
    sa.Column(u'channel', citexttype.CitextType(), nullable=False),
    sa.PrimaryKeyConstraint(u'crash_adu_by_build_signature_id')
    )
    ### end Alembic commands ###
    load_stored_proc(op, ['backfill_crash_adu_by_build_signature.sql',
                          'backfill_matviews.sql',
                          'update_crash_adu_by_build_signature.sql'])
    fix_permissions(op, 'crash_adu_by_build_signature')


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table(u'adu_by_build')
    ### end Alembic commands ###
    load_stored_proc(op, ['backfill_crash_adu_by_build_signature.sql',
                          'backfill_matviews.sql',
                          'update_crash_adu_by_build_signature.sql'])
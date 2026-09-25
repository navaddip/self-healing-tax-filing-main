from alembic import op
import sqlalchemy as sa
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("submissions", sa.Column("filing_details_json", sa.Text()))

def downgrade():
    op.drop_column("submissions", "filing_details_json")

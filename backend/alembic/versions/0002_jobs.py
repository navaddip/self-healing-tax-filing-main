from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("workflow_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.Float(), nullable=False),
        sa.Column("token", sa.String(36)))

def downgrade():
    op.drop_table("workflow_jobs")

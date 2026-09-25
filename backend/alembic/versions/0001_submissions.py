from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("upload_path", sa.Text(), nullable=False),
        sa.Column("report_path", sa.Text()), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("result_json", sa.Text()), sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table("submissions")

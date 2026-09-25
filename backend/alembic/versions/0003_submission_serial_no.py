from alembic import op
import sqlalchemy as sa
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("submissions", sa.Column("serial_no", sa.Integer()))
    op.execute("""
        UPDATE submissions SET serial_no = (
            SELECT COUNT(*) FROM submissions AS earlier
            WHERE earlier.created_at < submissions.created_at
               OR (earlier.created_at = submissions.created_at AND earlier.id <= submissions.id)
        )
    """)
    op.create_index("ix_submissions_serial_no", "submissions", ["serial_no"], unique=True)

def downgrade():
    op.drop_index("ix_submissions_serial_no", table_name="submissions")
    op.drop_column("submissions", "serial_no")

"""Add document-scoped AI consent records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_privacy_controls"
down_revision = "0002_agent_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_consents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("document_id", sa.String(240), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model_or_route", sa.String(160), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False, server_default="CONFIDENTIAL"),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.String(160), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_consents_organization_id", "ai_consents", ["organization_id"])
    op.create_index("ix_ai_consents_project_id", "ai_consents", ["project_id"])
    op.create_index("ix_ai_consents_document_id", "ai_consents", ["document_id"])


def downgrade() -> None:
    op.drop_table("ai_consents")

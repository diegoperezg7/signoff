"""Add durable agent runs, checkpoints, approvals and organization policy."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002_agent_runtime"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _id():
    return UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "agent_policies",
        sa.Column("organization_id", _id(), sa.ForeignKey("organizations.id"), primary_key=True),
        sa.Column("mode", sa.String(32), nullable=False, server_default="max_autonomy"),
        sa.Column("config_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", _id(), primary_key=True),
        sa.Column("organization_id", _id(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", _id(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("agent_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("classification", sa.String(40), nullable=False, server_default="CONFIDENTIAL"),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("input_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("result_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_runs_organization_id", "agent_runs", ["organization_id"])
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    for table, columns in (
        ("agent_steps", [("run_id", _id(), "agent_runs.id"), ("ordinal", sa.Integer(), None), ("tool", sa.String(100), None), ("status", sa.String(32), None), ("input_json", JSONB, None), ("output_json", JSONB, None), ("error", sa.Text(), None), ("duration_ms", sa.Integer(), None)]),
        ("agent_checkpoints", [("run_id", _id(), "agent_runs.id"), ("ordinal", sa.Integer(), None), ("state_json", JSONB, None)]),
        ("agent_approvals", [("organization_id", _id(), "organizations.id"), ("run_id", _id(), "agent_runs.id"), ("tool", sa.String(100), None), ("reason", sa.Text(), None), ("status", sa.String(32), None), ("decided_by", sa.String(160), None), ("comment", sa.Text(), None)]),
    ):
        cols = [sa.Column("id", _id(), primary_key=True)]
        for name, typ, foreign in columns:
            cols.append(sa.Column(name, typ, sa.ForeignKey(foreign) if foreign else None, nullable=False if name not in {"error", "decided_by"} else True))
        cols.extend([sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now())])
        op.create_table(table, *cols)
        for name, _, _ in columns:
            if name.endswith("_id") or name == "run_id":
                op.create_index(f"ix_{table}_{name}", table, [name])


def downgrade() -> None:
    for table in ("agent_approvals", "agent_checkpoints", "agent_steps", "agent_runs", "agent_policies"):
        op.drop_table(table)

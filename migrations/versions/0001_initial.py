"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("raw_paths", sa.JSON(), nullable=False),
    )
    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("dataset_versions.id")),
        sa.Column("sku_id", sa.String(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("forecast_mean", sa.Float(), nullable=False),
        sa.Column("forecast_p10", sa.Float(), nullable=False),
        sa.Column("forecast_p90", sa.Float(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
    )
    op.create_index("ix_forecasts_sku_id", "forecasts", ["sku_id"])
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("dataset_versions.id")),
        sa.Column("sku_id", sa.String(), nullable=False),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("recommended_order_units", sa.Integer(), nullable=False),
        sa.Column("reorder_point", sa.Float(), nullable=False),
        sa.Column("safety_stock", sa.Float(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("expected_cash_freed", sa.Float(), nullable=False),
        sa.Column("expected_stockout_risk_change", sa.Float(), nullable=False),
        sa.Column("abc_class", sa.String(), nullable=False),
    )
    op.create_index("ix_recommendations_sku_id", "recommendations", ["sku_id"])
    op.create_table(
        "overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendations.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("new_order_qty", sa.Integer(), nullable=False),
        sa.Column("reason_text", sa.String(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("overrides")
    op.drop_index("ix_recommendations_sku_id", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_forecasts_sku_id", table_name="forecasts")
    op.drop_table("forecasts")
    op.drop_table("dataset_versions")

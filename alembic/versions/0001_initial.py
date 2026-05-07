"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


comparison_mode = postgresql.ENUM(
    "strict", "similar", "mixed", name="comparison_mode", create_type=False
)
parser_status = postgresql.ENUM(
    "active", "partial", "disabled", "broken", name="parser_status", create_type=False
)
price_type = postgresql.ENUM(
    "regular", "promo", "card", "promo_card", "unknown", name="price_type", create_type=False
)
price_source = postgresql.ENUM(
    "website", "app_public_api", "html", "manual_seed", name="price_source", create_type=False
)
scrape_run_status = postgresql.ENUM(
    "started", "success", "partial", "failed", name="scrape_run_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    comparison_mode.create(bind, checkfirst=True)
    parser_status.create(bind, checkfirst=True)
    price_type.create(bind, checkfirst=True)
    price_source.create(bind, checkfirst=True)
    scrape_run_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("chain_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("parser_status", parser_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stores_slug", "stores", ["slug"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_name", sa.String(length=500), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("quantity_value", sa.Numeric(12, 3), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("normalized_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enabled_store_slugs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("has_smart_card", sa.Boolean(), nullable=False),
        sa.Column("has_magnit_card", sa.Boolean(), nullable=False),
        sa.Column("has_spar_card", sa.Boolean(), nullable=False),
        sa.Column("has_pyaterochka_card", sa.Boolean(), nullable=False),
        sa.Column("has_fix_price_card", sa.Boolean(), nullable=False),
        sa.Column("comparison_mode", comparison_mode, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )

    op.create_table(
        "store_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "store_id",
            sa.Integer(),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_title", sa.String(length=1000), nullable=False),
        sa.Column("normalized_title", sa.String(length=1000), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("quantity_value", sa.Numeric(12, 3), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_store_products_store_id", "store_products", ["store_id"])
    op.create_index("ix_store_products_normalized_title", "store_products", ["normalized_title"])

    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "store_product_id",
            sa.Integer(),
            sa.ForeignKey("store_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("regular_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("old_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("promo_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("card_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("final_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_type", price_type, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit_price_unit", sa.String(length=32), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=True),
        sa.Column("source", price_source, nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_price_snapshots_store_product_id", "price_snapshots", ["store_product_id"])
    op.create_index("ix_price_snapshots_scraped_at", "price_snapshots", ["scraped_at"])

    op.create_table(
        "baskets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "basket_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "basket_id",
            sa.Integer(),
            sa.ForeignKey("baskets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.String(length=1000), nullable=False),
        sa.Column("parsed_name", sa.String(length=1000), nullable=False),
        sa.Column("desired_quantity_value", sa.Numeric(12, 3), nullable=True),
        sa.Column("desired_quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "store_id",
            sa.Integer(),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", scrape_run_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("products_found", sa.Integer(), nullable=False),
        sa.Column("prices_found", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scrape_runs")
    op.drop_table("basket_items")
    op.drop_table("baskets")
    op.drop_index("ix_price_snapshots_scraped_at", table_name="price_snapshots")
    op.drop_index("ix_price_snapshots_store_product_id", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_index("ix_store_products_normalized_title", table_name="store_products")
    op.drop_index("ix_store_products_store_id", table_name="store_products")
    op.drop_table("store_products")
    op.drop_table("user_settings")
    op.drop_table("products")
    op.drop_index("ix_stores_slug", table_name="stores")
    op.drop_table("stores")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    bind = op.get_bind()
    scrape_run_status.drop(bind, checkfirst=True)
    price_source.drop(bind, checkfirst=True)
    price_type.drop(bind, checkfirst=True)
    parser_status.drop(bind, checkfirst=True)
    comparison_mode.drop(bind, checkfirst=True)

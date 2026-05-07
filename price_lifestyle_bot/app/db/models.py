from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utc_now


class ComparisonMode(StrEnum):
    strict = "strict"
    similar = "similar"
    mixed = "mixed"


class ParserStatus(StrEnum):
    active = "active"
    partial = "partial"
    disabled = "disabled"
    broken = "broken"


class PriceType(StrEnum):
    regular = "regular"
    promo = "promo"
    card = "card"
    promo_card = "promo_card"
    unknown = "unknown"


class PriceSource(StrEnum):
    website = "website"
    app_public_api = "app_public_api"
    html = "html"
    manual_seed = "manual_seed"


class ScrapeRunStatus(StrEnum):
    started = "started"
    success = "success"
    partial = "partial"
    failed = "failed"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str] = mapped_column(String(255), default="Бор")

    settings: Mapped[UserSettings] = relationship(back_populates="user", uselist=False)
    baskets: Mapped[list[Basket]] = relationship(back_populates="user")
    bot_sessions: Mapped[list[BotSession]] = relationship(back_populates="user")


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    enabled_store_slugs: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: ["smart", "magnit", "spar", "pyaterochka", "fix_price"]
    )
    has_smart_card: Mapped[bool] = mapped_column(Boolean, default=False)
    has_magnit_card: Mapped[bool] = mapped_column(Boolean, default=False)
    has_spar_card: Mapped[bool] = mapped_column(Boolean, default=False)
    has_pyaterochka_card: Mapped[bool] = mapped_column(Boolean, default=False)
    has_fix_price_card: Mapped[bool] = mapped_column(Boolean, default=False)
    comparison_mode: Mapped[ComparisonMode] = mapped_column(
        Enum(ComparisonMode, name="comparison_mode"), default=ComparisonMode.mixed
    )

    user: Mapped[User] = relationship(back_populates="settings")


class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    chain_name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255), default="Бор")
    address: Mapped[str | None] = mapped_column(String(500))
    website_url: Mapped[str] = mapped_column(String(500))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    parser_status: Mapped[ParserStatus] = mapped_column(
        Enum(ParserStatus, name="parser_status"), default=ParserStatus.partial
    )

    products: Mapped[list[StoreProduct]] = relationship(back_populates="store")
    scrape_runs: Mapped[list[ScrapeRun]] = relationship(back_populates="store")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255))
    quantity_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    quantity_unit: Mapped[str | None] = mapped_column(String(32))
    barcode: Mapped[str | None] = mapped_column(String(64))
    normalized_key: Mapped[str | None] = mapped_column(String(500))

    store_products: Mapped[list[StoreProduct]] = relationship(back_populates="product")


class StoreProduct(Base, TimestampMixin):
    __tablename__ = "store_products"
    __table_args__ = (
        Index("ix_store_products_store_id", "store_id"),
        Index("ix_store_products_normalized_title", "normalized_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    external_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    raw_title: Mapped[str] = mapped_column(String(1000))
    normalized_title: Mapped[str] = mapped_column(String(1000))
    brand: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255))
    quantity_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    quantity_unit: Mapped[str | None] = mapped_column(String(32))
    barcode: Mapped[str | None] = mapped_column(String(64))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    store: Mapped[Store] = relationship(back_populates="products")
    product: Mapped[Product | None] = relationship(back_populates="store_products")
    prices: Mapped[list[PriceSnapshot]] = relationship(back_populates="store_product")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index("ix_price_snapshots_store_product_id", "store_product_id"),
        Index("ix_price_snapshots_scraped_at", "scraped_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_product_id: Mapped[int] = mapped_column(
        ForeignKey("store_products.id", ondelete="CASCADE")
    )
    regular_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    promo_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    card_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    final_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_type: Mapped[PriceType] = mapped_column(Enum(PriceType, name="price_type"))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit_price_unit: Mapped[str | None] = mapped_column(String(32))
    in_stock: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[PriceSource] = mapped_column(Enum(PriceSource, name="price_source"))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    store_product: Mapped[StoreProduct] = relationship(back_populates="prices")


class Basket(Base):
    __tablename__ = "baskets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="baskets")
    items: Mapped[list[BasketItem]] = relationship(back_populates="basket")


class BasketItem(Base):
    __tablename__ = "basket_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(String(1000))
    parsed_name: Mapped[str] = mapped_column(String(1000))
    desired_quantity_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    desired_quantity_unit: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    basket: Mapped[Basket] = relationship(back_populates="items")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    status: Mapped[ScrapeRunStatus] = mapped_column(Enum(ScrapeRunStatus, name="scrape_run_status"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    products_found: Mapped[int] = mapped_column(default=0)
    prices_found: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    store: Mapped[Store] = relationship(back_populates="scrape_runs")


class BotSession(Base, TimestampMixin):
    __tablename__ = "bot_sessions"
    __table_args__ = (
        Index("ix_bot_sessions_session_key", "session_key", unique=True),
        Index("ix_bot_sessions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(64), default="telegram")
    chat_id: Mapped[str] = mapped_column(String(255))
    session_key: Mapped[str] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="bot_sessions")
    messages: Mapped[list[BotMessage]] = relationship(back_populates="session")


class BotMessage(Base):
    __tablename__ = "bot_messages"
    __table_args__ = (
        Index("ix_bot_messages_session_id", "session_id"),
        Index("ix_bot_messages_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("bot_sessions.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(16))
    message_type: Mapped[str] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(Text)
    command: Mapped[str | None] = mapped_column(String(128))
    raw_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[BotSession] = relationship(back_populates="messages")

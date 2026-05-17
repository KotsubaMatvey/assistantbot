from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.db.models import PriceType
from app.services.assistant_jobs import AssistantJobStore
from app.services.assistant_personas import format_personas, get_persona
from app.services.automation import enable_automation, list_automation_templates
from app.services.basket_parser import parse_basket
from app.services.daily_brief import DailyBrief, format_daily_brief
from app.services.family import FamilyStore
from app.services.finance import FinanceStore
from app.services.pantry import PantryStore, parse_pantry_item
from app.services.price_alerts import (
    CONDITION_BELOW_AVERAGE,
    CONDITION_DISCOUNT_PERCENT,
    PriceAlertStore,
    evaluate_price_alerts,
    parse_price_alert_request,
)
from app.services.price_comparator import PriceOffer, ProductInfo, StoreInfo
from app.services.spending import SpendingStore, parse_receipt_text


def test_pantry_add_consume_expiring_and_suggestions(tmp_path) -> None:
    store = PantryStore(str(tmp_path))
    name, quantity, unit, expires_at = parse_pantry_item("молоко 2 л 2026-05-09")

    item = store.add_item(
        user_id=123,
        name=name,
        quantity=quantity,
        unit=unit,
        expires_at=expires_at,
    )
    changed = store.consume(user_id=123, item_ref=item.id, quantity=Decimal("1"))

    assert changed is True
    assert store.list_items(user_id=123)[0].quantity == Decimal("1")
    assert store.expiring_items(user_id=123, today=datetime(2026, 5, 8, tzinfo=UTC).date())
    assert "яйца" in store.shopping_suggestions(user_id=123)


def test_spending_receipt_and_budget_summary(tmp_path) -> None:
    receipt_store = SpendingStore(str(tmp_path))
    store_name, items = parse_receipt_text("магазин: Smart\nмолоко 100.50\nхлеб 45\nкофе 300")
    receipt_store.add_receipt(
        user_id=123,
        store=store_name,
        items=items,
        purchased_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )
    receipt_store.set_budget(user_id=123, month="2026-05", amount=Decimal("1000"))

    summary = receipt_store.budget_summary(user_id=123, month="2026-05")

    assert summary.spent == Decimal("445.50")
    assert summary.remaining == Decimal("554.50")
    assert summary.top_items[0] == ("молоко", 1)
    assert summary.category_totals[0] == ("напитки", Decimal("300"))
    assert items[0].category == "молочные"


def test_spending_plan_vs_actual(tmp_path) -> None:
    receipt_store = SpendingStore(str(tmp_path))
    _, items = parse_receipt_text("молоко 100\nкофе 300\nшоколад 90")
    receipt_store.add_receipt(
        user_id=123,
        store="Smart",
        items=items,
        purchased_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )

    report = receipt_store.plan_vs_actual(
        user_id=123,
        planned_items=parse_basket("молоко 1 л\nхлеб"),
        month="2026-05",
    )

    assert report.matched[0].name == "молоко"
    assert report.missing == ["хлеб"]
    assert report.unplanned[0].name == "кофе"


def test_finance_store_cashflow_accounts_and_subscriptions(tmp_path) -> None:
    store = FinanceStore(str(tmp_path))
    store.upsert_account(user_id=123, name="Cash", balance=Decimal("10000"))
    store.upsert_subscription(user_id=123, name="Music", amount=Decimal("299"))
    store.add_transaction(
        user_id=123,
        kind="income",
        amount=Decimal("5000"),
        category="salary",
        created_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )
    store.add_transaction(
        user_id=123,
        kind="expense",
        amount=Decimal("1000"),
        category="food",
        created_at=datetime(2026, 5, 9, 9, 0, tzinfo=UTC),
    )

    summary = store.cashflow_summary(
        user_id=123,
        month="2026-05",
        receipt_expenses=Decimal("500"),
    )

    assert store.list_accounts(user_id=123)[0].balance == Decimal("10000")
    assert store.list_subscriptions(user_id=123)[0].amount == Decimal("299")
    assert summary.income == Decimal("5000")
    assert summary.expenses == Decimal("1000")
    assert summary.forecast == Decimal("13201")


def test_price_alerts_evaluate_current_offers(tmp_path) -> None:
    item_text, threshold = parse_price_alert_request("молоко 2.5 1 л < 90")
    alert = PriceAlertStore(str(tmp_path)).add_alert(
        user_id=123,
        item_text=item_text,
        threshold=threshold,
        now=datetime(2026, 5, 8, 8, 0, tzinfo=UTC),
    )

    hits = evaluate_price_alerts(
        [alert],
        settings=SimpleNamespace(enabled_store_slugs=["smart"], comparison_mode="mixed"),
        offers=[
            PriceOffer(
                store_product=ProductInfo(
                    id=1,
                    store=StoreInfo(slug="smart", display_name="Smart"),
                    raw_title="молоко 2.5 1 л",
                    normalized_title="молоко 2.5 1 л",
                    quantity_value=Decimal("1000"),
                    quantity_unit="мл",
                ),
                regular_price=Decimal("89"),
                old_price=None,
                promo_price=None,
                card_price=None,
                final_price=Decimal("89"),
                price_type=PriceType.regular,
                unit_price=None,
                unit_price_unit=None,
                in_stock=True,
                scraped_at=datetime.now(UTC),
            )
        ],
        freshness_hours=24,
    )

    assert hits[0].alert.id == alert.id
    assert hits[0].price == Decimal("89")


def test_price_alerts_parse_smart_conditions() -> None:
    average = parse_price_alert_request("молоко 2.5 1 л ниже обычного")
    discount = parse_price_alert_request("кофе 95 г скидка > 20%")

    assert average.item_text == "молоко 2.5 1 л"
    assert average.condition == CONDITION_BELOW_AVERAGE
    assert discount.item_text == "кофе 95 г"
    assert discount.condition == CONDITION_DISCOUNT_PERCENT
    assert discount.discount_percent == Decimal("20")


def test_price_alerts_evaluate_below_average_history(tmp_path) -> None:
    spec = parse_price_alert_request("молоко 2.5 1 л ниже обычного")
    alert = PriceAlertStore(str(tmp_path)).add_alert(
        user_id=123,
        item_text=spec.item_text,
        condition=spec.condition,
    )

    hits = evaluate_price_alerts(
        [alert],
        settings=SimpleNamespace(enabled_store_slugs=["smart"], comparison_mode="mixed"),
        offers=[
            PriceOffer(
                store_product=ProductInfo(
                    id=1,
                    store=StoreInfo(slug="smart", display_name="Smart"),
                    raw_title="молоко 2.5 1 л",
                    normalized_title="молоко 2.5 1 л",
                    quantity_value=Decimal("1000"),
                    quantity_unit="мл",
                ),
                regular_price=Decimal("89"),
                old_price=None,
                promo_price=None,
                card_price=None,
                final_price=Decimal("89"),
                price_type=PriceType.regular,
                unit_price=None,
                unit_price_unit=None,
                in_stock=True,
                scraped_at=datetime.now(UTC),
                history_average_price=Decimal("100"),
                history_min_price=Decimal("89"),
                history_max_price=Decimal("120"),
                history_samples_count=3,
            )
        ],
        freshness_hours=24,
    )

    assert hits[0].reason.startswith("минимум за период")


def test_family_automation_personas_and_daily_brief(tmp_path) -> None:
    family_store = FamilyStore(str(tmp_path))
    family = family_store.create_family(owner_id=1, name="Home")
    joined = family_store.join_family(user_id=2, invite_code=family.invite_code)
    updated = family_store.add_shared_item(user_id=2, text="купить кофе")
    job = enable_automation(
        jobs=AssistantJobStore(str(tmp_path)),
        user_id=1,
        name="morning_digest",
    )
    brief = format_daily_brief(
        DailyBrief(
            agenda="Agenda",
            markets="Рынки\nBTC: 1",
            price_alerts="Alerts",
            pantry="Pantry",
            budget="Budget",
        )
    )

    assert joined is not None and 2 in joined.members
    assert updated is not None and "купить кофе" in updated.shared_items
    assert job.delivery_mode == "morning"
    assert "morning_digest" in {template.name for template in list_automation_templates()}
    assert get_persona("buyer") is not None
    assert "buyer" in format_personas()
    assert "Утренний дайджест" in brief

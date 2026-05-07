from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.db.repositories.prices import get_latest_prices_by_store_products
from app.db.repositories.users import get_or_create_user, get_settings_for_user
from app.db.session import SessionLocal
from app.services.agenda import build_agenda
from app.services.assistant_jobs import AssistantJobStore
from app.services.assistant_personas import format_personas, get_persona
from app.services.assistant_runtime import AssistantRuntimeStore
from app.services.automation import (
    enable_automation,
    format_automations,
    list_automation_templates,
)
from app.services.daily_brief import DailyBrief, format_daily_brief
from app.services.family import FamilyStore, format_family
from app.services.market_watch import fetch_market_watch, format_market_watch
from app.services.obsidian_memory import ObsidianMemory
from app.services.pantry import (
    PantryStore,
    format_pantry,
    format_pantry_suggestions,
    parse_pantry_item,
)
from app.services.price_alerts import (
    PriceAlertStore,
    evaluate_price_alerts,
    format_price_alert_hits,
    format_price_alerts,
    parse_price_alert_request,
)
from app.services.price_comparator import offer_from_snapshot
from app.services.spending import (
    SpendingStore,
    current_month,
    format_budget_summary,
    format_receipt,
    parse_receipt_text,
)

router = Router()


@router.message(Command("watch_price"))
async def watch_price_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        item_text, threshold = parse_price_alert_request(
            (message.text or "").partition(" ")[2]
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    alert = PriceAlertStore(get_settings().obsidian_vault_path).add_alert(
        user_id=message.from_user.id,
        item_text=item_text,
        threshold=threshold,
    )
    await message.answer(f"Price alert сохранён: {alert.id} — {item_text} <= {threshold} ₽")


@router.message(Command("price_alerts"))
async def price_alerts_handler(message: Message) -> None:
    if message.from_user is None:
        return
    alerts = PriceAlertStore(get_settings().obsidian_vault_path).list_alerts(
        user_id=message.from_user.id
    )
    await message.answer(format_price_alerts(alerts))


@router.message(Command("price_unwatch"))
async def price_unwatch_handler(message: Message) -> None:
    if message.from_user is None:
        return
    alert_id = (message.text or "").partition(" ")[2].strip()
    if not alert_id:
        await message.answer("Использование: /price_unwatch <alert_id>")
        return
    deleted = PriceAlertStore(get_settings().obsidian_vault_path).delete_alert(
        user_id=message.from_user.id,
        alert_id=alert_id,
    )
    await message.answer("Price alert удалён." if deleted else "Price alert не найден.")


@router.message(Command("check_alerts"))
async def check_alerts_handler(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(await _price_alert_report(message))


@router.message(Command("pantry"))
async def pantry_handler(message: Message) -> None:
    if message.from_user is None:
        return
    items = PantryStore(get_settings().obsidian_vault_path).list_items(user_id=message.from_user.id)
    await message.answer(format_pantry(items))


@router.message(Command("pantry_add"))
async def pantry_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        name, quantity, unit, expires_at = parse_pantry_item(
            (message.text or "").partition(" ")[2]
        )
        item = PantryStore(get_settings().obsidian_vault_path).add_item(
            user_id=message.from_user.id,
            name=name,
            quantity=quantity,
            unit=unit,
            expires_at=expires_at,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(f"Добавил в склад: {item.name} — {item.quantity} {item.unit}")


@router.message(Command("pantry_use"))
async def pantry_use_handler(message: Message) -> None:
    if message.from_user is None:
        return
    args = (message.text or "").partition(" ")[2].strip().split(maxsplit=1)
    if not args:
        await message.answer("Использование: /pantry_use <id|name> [кол-во]")
        return
    quantity = Decimal("1")
    item_ref = args[0]
    if len(args) == 2:
        try:
            quantity = Decimal(args[1].replace(",", "."))
        except Exception:
            await message.answer("Количество должно быть числом.")
            return
    try:
        changed = PantryStore(get_settings().obsidian_vault_path).consume(
            user_id=message.from_user.id,
            item_ref=item_ref,
            quantity=quantity,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer("Склад обновлён." if changed else "Товар не найден.")


@router.message(Command("pantry_plan"))
async def pantry_plan_handler(message: Message) -> None:
    if message.from_user is None:
        return
    store = PantryStore(get_settings().obsidian_vault_path)
    expiring = store.expiring_items(user_id=message.from_user.id)
    suggestions = store.shopping_suggestions(user_id=message.from_user.id)
    lines = ["План по дому:"]
    if expiring:
        lines.append("Скоро истекает:")
        lines.extend(f"- {item.name}: до {item.expires_at}" for item in expiring)
    lines.append(format_pantry_suggestions(suggestions))
    await message.answer("\n".join(lines))


@router.message(Command("receipt"))
async def receipt_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /receipt <строки чека: товар цена>")
        return
    try:
        store, items = parse_receipt_text(text)
        receipt = SpendingStore(get_settings().obsidian_vault_path).add_receipt(
            user_id=message.from_user.id,
            store=store,
            items=items,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(format_receipt(receipt))


@router.message(Command("budget"))
async def budget_handler(message: Message) -> None:
    if message.from_user is None:
        return
    month = (message.text or "").partition(" ")[2].strip() or current_month()
    summary = SpendingStore(get_settings().obsidian_vault_path).budget_summary(
        user_id=message.from_user.id,
        month=month,
    )
    await message.answer(format_budget_summary(summary))


@router.message(Command("budget_set"))
async def budget_set_handler(message: Message) -> None:
    if message.from_user is None:
        return
    args = (message.text or "").partition(" ")[2].strip().split()
    if len(args) != 2:
        await message.answer("Использование: /budget_set YYYY-MM сумма")
        return
    try:
        amount = Decimal(args[1].replace(",", "."))
        SpendingStore(get_settings().obsidian_vault_path).set_budget(
            user_id=message.from_user.id,
            month=args[0],
            amount=amount,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(f"Бюджет {args[0]}: {amount} ₽")


@router.message(Command("morning"))
async def morning_handler(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(await _morning_report(message))


@router.message(Command("family"))
async def family_handler(message: Message) -> None:
    if message.from_user is None:
        return
    family = FamilyStore(get_settings().obsidian_vault_path).family_for_user(
        user_id=message.from_user.id
    )
    await message.answer(format_family(family))


@router.message(Command("family_create"))
async def family_create_handler(message: Message) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").partition(" ")[2].strip() or "Home"
    family = FamilyStore(get_settings().obsidian_vault_path).create_family(
        owner_id=message.from_user.id,
        name=name,
    )
    await message.answer(format_family(family))


@router.message(Command("family_join"))
async def family_join_handler(message: Message) -> None:
    if message.from_user is None:
        return
    code = (message.text or "").partition(" ")[2].strip()
    if not code:
        await message.answer("Использование: /family_join <invite_code>")
        return
    family = FamilyStore(get_settings().obsidian_vault_path).join_family(
        user_id=message.from_user.id,
        invite_code=code,
    )
    await message.answer(format_family(family) if family else "Invite code не найден.")


@router.message(Command("family_add"))
async def family_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /family_add <пункт общего списка>")
        return
    family = FamilyStore(get_settings().obsidian_vault_path).add_shared_item(
        user_id=message.from_user.id,
        text=text,
    )
    await message.answer(format_family(family))


@router.message(Command("automations"))
async def automations_handler(message: Message) -> None:
    await message.answer(format_automations(list_automation_templates()))


@router.message(Command("automation_enable"))
async def automation_enable_handler(message: Message) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").partition(" ")[2].strip()
    if not name:
        await message.answer("Использование: /automation_enable <template>")
        return
    settings = get_settings()
    try:
        job = enable_automation(
            jobs=AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone),
            user_id=message.from_user.id,
            name=name,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    next_run = job.next_run_at.astimezone(ZoneInfo(settings.timezone))
    await message.answer(
        f"Automation включена: {name}\n"
        f"Job: {job.id}\n"
        f"Next: {next_run:%Y-%m-%d %H:%M}"
    )


@router.message(Command("assistants"))
async def assistants_handler(message: Message) -> None:
    if message.from_user is None:
        return
    active = AssistantRuntimeStore(get_settings().obsidian_vault_path).get_state(
        user_id=message.from_user.id
    ).mode
    await message.answer(format_personas(active=active))


@router.message(Command("assistant_pick"))
async def assistant_pick_handler(message: Message) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").partition(" ")[2].strip()
    persona = get_persona(name)
    if persona is None:
        await message.answer("Ассистент не найден. Используй /assistants.")
        return
    AssistantRuntimeStore(get_settings().obsidian_vault_path).set_mode(
        user_id=message.from_user.id,
        mode=persona.name,
    )
    await message.answer(f"Активный ассистент: {persona.title}")


@router.message(Command("voice_note"))
async def voice_note_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /voice_note <текст расшифровки>")
        return
    path = ObsidianMemory(get_settings().obsidian_vault_path).remember_user_note(
        user_id=message.from_user.id,
        text=text,
        note_type="voice",
        extra_tags=["voice", "capture"],
        title="Voice note transcript",
    )
    await message.answer(f"Voice note сохранён: {path.name}")


@router.message(F.voice)
async def voice_message_handler(message: Message) -> None:
    if message.from_user is None:
        return
    caption = (message.caption or "").strip()
    if caption:
        path = ObsidianMemory(get_settings().obsidian_vault_path).remember_user_note(
            user_id=message.from_user.id,
            text=caption,
            note_type="voice",
            extra_tags=["voice", "capture"],
            title="Voice note caption",
        )
        await message.answer(f"Подпись к voice note сохранена: {path.name}")
        return
    await message.answer(
        "Voice получен. STT ещё не подключён; отправь расшифровку через /voice_note <текст>."
    )


@router.message(Command("decisions"))
async def decisions_handler(message: Message) -> None:
    if message.from_user is None:
        return
    notes = ObsidianMemory(get_settings().obsidian_vault_path).collection_notes(
        user_id=message.from_user.id,
        collection="decision",
        limit=10,
    )
    if not notes:
        await message.answer("Decision log пока пуст. Создай решение через /decide.")
        return
    lines = ["Decision log:"]
    lines.extend(f"- {note.snippet}\n  {note.citation}" for note in notes)
    await message.answer("\n".join(lines)[:3900])


async def _price_alert_report(message: Message) -> str:
    if message.from_user is None:
        return ""
    settings = get_settings()
    alerts = PriceAlertStore(settings.obsidian_vault_path).list_alerts(user_id=message.from_user.id)
    if not alerts:
        return "Price alerts пока нет."
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        user_settings = await get_settings_for_user(session, user.id)
        snapshots = await get_latest_prices_by_store_products(session)
        await session.commit()
    hits = evaluate_price_alerts(
        alerts,
        settings=user_settings,
        offers=[offer_from_snapshot(snapshot) for snapshot in snapshots],
        freshness_hours=settings.price_freshness_hours,
    )
    return format_price_alert_hits(hits)


async def _morning_report(message: Message) -> str:
    if message.from_user is None:
        return ""
    settings = get_settings()
    user_id = message.from_user.id
    memory = ObsidianMemory(settings.obsidian_vault_path)
    markets = format_market_watch(await fetch_market_watch())
    agenda = build_agenda(
        memory=memory,
        jobs=AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone),
        user_id=user_id,
        timezone_name=settings.timezone,
    )
    pantry = format_pantry_suggestions(
        PantryStore(settings.obsidian_vault_path).shopping_suggestions(user_id=user_id)
    )
    budget = format_budget_summary(
        SpendingStore(settings.obsidian_vault_path).budget_summary(user_id=user_id)
    )
    return format_daily_brief(
        DailyBrief(
            agenda=agenda,
            markets=markets,
            price_alerts=await _price_alert_report(message),
            pantry=pantry,
            budget=budget,
        )
    )[:3900]

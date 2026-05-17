from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from app.services.agenda import build_agenda
from app.services.assistant_jobs import AssistantJobStore, parse_job_request
from app.services.assistant_tools import ToolUsageStore, format_tool_registry, list_tools, run_tool
from app.services.audit_log import AuditLogStore
from app.services.conversation_summary import summarize_conversation
from app.services.memory_transfer import export_user_memory, import_user_memory
from app.services.mini_app import (
    MAX_ASSISTANT_TEXT_CHARS,
    MAX_BASKET_TEXT_CHARS,
    mini_app_manifest,
    parse_mini_app_payload,
)
from app.services.mini_app_server import validate_telegram_init_data
from app.services.mini_app_state import (
    add_mini_app_task,
    add_mini_app_transaction,
    build_mini_app_state,
    update_mini_app_account,
)
from app.services.object_store import ObjectStore
from app.services.obsidian_memory import ObsidianMemory
from app.services.secret_scanner import scan_for_secrets
from app.services.source_trust import build_source_trust
from app.services.standing_orders import StandingOrderStore


def test_memory_export_import_roundtrip_dry_run_and_apply(tmp_path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    memory = ObsidianMemory(str(source))
    memory.remember_user_note(user_id=123, text="portable note")

    exported = export_user_memory(vault_path=str(source), user_id=123)
    dry_run = import_user_memory(
        vault_path=str(target),
        user_id=123,
        archive_path=str(exported.path),
    )
    applied = import_user_memory(
        vault_path=str(target),
        user_id=123,
        archive_path=str(exported.path),
        dry_run=False,
    )

    assert exported.files_count >= 2
    assert dry_run.files_count == applied.files_count
    assert (target / "users" / "123").exists()


def test_standing_orders_and_audit_log(tmp_path) -> None:
    orders = StandingOrderStore(str(tmp_path))
    audit = AuditLogStore(str(tmp_path))

    order = orders.add_order(user_id=123, text="Always extract follow-ups.")
    event = audit.record(user_id=123, action="order_add", detail=order.id)

    assert orders.list_orders(user_id=123)[0].text == "Always extract follow-ups."
    assert audit.list_events()[0].id == event.id
    assert orders.delete_order(user_id=123, order_id=order.id) is True


def test_audit_log_skips_corrupted_lines(tmp_path) -> None:
    audit = AuditLogStore(str(tmp_path))
    event = audit.record(user_id=123, action="ok", detail="safe")
    with audit.path.open("a", encoding="utf-8") as file:
        file.write("{broken json\n")

    assert audit.list_events()[0].id == event.id


def test_secret_scanner_redacts_findings(tmp_path) -> None:
    path = tmp_path / "config.txt"
    token = "1234567890:" + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"
    path.write_text(f"BOT_TOKEN={token}\n", encoding="utf-8")

    findings = scan_for_secrets(str(tmp_path))

    assert findings
    assert findings[0].kind in {"telegram_bot_token", "generic_api_key"}
    assert "..." in findings[0].preview


def test_job_delivery_mode_parser_and_tools(tmp_path) -> None:
    schedule_type, schedule_value, delivery_mode, message = parse_job_request(
        "daily 09:00 digest morning brief"
    )
    job = AssistantJobStore(str(tmp_path)).add_job(
        user_id=123,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        delivery_mode=delivery_mode,
        message=message,
        now=datetime(2026, 5, 6, 6, 0, tzinfo=UTC),
    )

    assert job.delivery_mode == "digest"
    assert job.message == "morning brief"
    assert run_tool(name="calc", text="2 + 2 * 3") == "8"

    _, _, market_mode, market_message = parse_job_request("daily 08:00 markets morning markets")
    assert market_mode == "markets"
    assert market_message == "morning markets"
    _, _, morning_mode, _ = parse_job_request("daily 08:00 morning daily brief")
    assert morning_mode == "morning"


def test_tool_registry_tracks_usage_metadata(tmp_path) -> None:
    store = ToolUsageStore(str(tmp_path))
    store.record_success("calc")

    text = format_tool_registry(list_tools(), store.list_usage())

    assert "Tools registry:" in text
    assert "calc [assistant, risk:low" in text
    assert "last_used:" in text


def test_filtered_search_inbox_tags_source_trust_and_agenda(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="alpha plain note")
    task = memory.create_task(user_id=123, text="write alpha plan")
    memory.remember_user_note(
        user_id=123,
        text="alpha source",
        source_type="web",
        source_url="https://example.com/a",
    )
    jobs = AssistantJobStore(str(tmp_path))

    assert memory.filtered_search(user_id=123, query="type:task alpha")[0].path == task
    assert memory.add_note_tag(user_id=123, note_id=task.stem, tag="work") is True
    assert memory.inbox_review(user_id=123)
    assert build_source_trust(memory.list_sources(user_id=123))[0].domain == "example.com"
    assert "Open tasks" in build_agenda(
        memory=memory,
        jobs=jobs,
        user_id=123,
        timezone_name="Europe/Moscow",
    )


def test_object_store_indexes_memory_and_receipts(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_person_note(user_id=123, person_name="Ivan", text="likes email updates")
    memory.create_task(user_id=123, text="ship object system")
    memory.remember_user_note(
        user_id=123,
        text="Source note",
        source_type="web",
        source_url="https://example.com/source",
    )
    store = ObjectStore(str(tmp_path))
    store.index_receipt(
        user_id=123,
        receipt_id="r1",
        store="Magnit",
        total="120",
        items=[("milk 2.5", "120", "dairy")],
        purchased_at=datetime(2026, 5, 8, 9, 0, tzinfo=UTC),
    )

    stats = store.stats(user_id=123)
    object_types = {object_type for object_type, _ in stats.by_type}

    assert {"person", "task", "source", "receipt", "product"} <= object_types
    assert store.list_objects(user_id=123, object_type="person")[0].title == "Person: Ivan"
    assert store.list_objects(user_id=123, object_type="product")[0].title == "milk 2.5"


def test_mini_app_state_uses_live_local_stores(tmp_path) -> None:
    update_mini_app_account(
        vault_path=str(tmp_path),
        user_id=123,
        name="Cash",
        balance="1000",
    )
    add_mini_app_transaction(
        vault_path=str(tmp_path),
        user_id=123,
        kind="expense",
        amount="250",
        category="food",
    )
    add_mini_app_task(vault_path=str(tmp_path), user_id=123, text="real mini app task")
    AuditLogStore(str(tmp_path)).record(
        user_id=123,
        action="mini_app_task_create",
        detail="real mini app task",
    )

    state = build_mini_app_state(
        vault_path=str(tmp_path),
        user_id=123,
        timezone_name="Europe/Moscow",
    )

    assert state["finance"]["balance"] == "1000.00"
    assert state["finance"]["expenses"] == "250.00"
    assert state["today"]["tasks"][0]["snippet"] == "real mini app task"
    assert state["memory"]["events"][0]["action"] == "mini_app_task_create"


def test_telegram_init_data_validation_extracts_user_id() -> None:
    init_data = _signed_init_data(bot_token="123:token", user_id=987)

    assert validate_telegram_init_data(init_data, bot_token="123:token") == 987


def test_conversation_summary_and_mini_app_manifest() -> None:
    summary = summarize_conversation(["надо написать план", "решили выбрать вариант A"])
    manifest = mini_app_manifest("https://example.com/app")
    command_payload = parse_mini_app_payload('{"type":"command","command":"markets"}')
    brief_payload = parse_mini_app_payload('{"type":"command","command":"market_brief"}')
    center_payload = parse_mini_app_payload(
        '{"type":"command","command":"capability_center"}'
    )
    tree_payload = parse_mini_app_payload('{"type":"command","command":"memory_tree"}')
    source_payload = parse_mini_app_payload('{"type":"command","command":"source_list"}')
    pantry_payload = parse_mini_app_payload('{"type":"command","command":"pantry_deals"}')
    budget_payload = parse_mini_app_payload('{"type":"command","command":"budget_plan"}')
    cashflow_payload = parse_mini_app_payload('{"type":"command","command":"cashflow"}')
    people_payload = parse_mini_app_payload('{"type":"command","command":"people"}')
    evening_payload = parse_mini_app_payload('{"type":"command","command":"evening"}')
    context_payload = parse_mini_app_payload(
        '{"type":"command","command":"lifestyle_context"}'
    )
    today_payload = parse_mini_app_payload('{"type":"command","command":"today"}')
    basket_payload = parse_mini_app_payload('{"type":"basket_compare","text":"молоко"}')
    assistant_payload = parse_mini_app_payload('{"type":"assistant_message","text":"btc"}')
    task_payload = parse_mini_app_payload('{"type":"task_create","text":"ship mini app"}')
    note_payload = parse_mini_app_payload('{"type":"note_create","text":"remember this"}')
    reminder_payload = parse_mini_app_payload(
        '{"type":"reminder_create","text":"tomorrow call Ivan"}'
    )
    person_payload = parse_mini_app_payload(
        '{"type":"person_note","name":"Ivan","note":"prefers email"}'
    )
    finance_payload = parse_mini_app_payload(
        '{"type":"finance_transaction","kind":"expense","amount":"100","category":"food","note":"milk"}'
    )
    account_payload = parse_mini_app_payload(
        '{"type":"finance_account","name":"Cash","balance":"1000"}'
    )
    subscription_payload = parse_mini_app_payload(
        '{"type":"finance_subscription","name":"Music","amount":"199"}'
    )
    receipt_payload = parse_mini_app_payload('{"type":"receipt_save","text":"store\\nmilk 100"}')

    assert "Possible tasks" in summary.body
    assert "Possible decisions" in summary.body
    assert manifest.enabled is True
    assert "tasks" in manifest.features
    assert "market_watch" in manifest.features
    assert "market_brief" in manifest.features
    assert "capability_center" in manifest.features
    assert "memory_tree" in manifest.features
    assert "connected_sources" in manifest.features
    assert "pixel_assistant" in manifest.features
    assert "lifestyle_context" in manifest.features
    assert "finance" in manifest.features
    assert "mini_app_event_log" in manifest.features
    assert "mini_app_telegram_fallback" in manifest.features
    assert "people" in manifest.features
    assert "objects" in manifest.features
    assert "daily_command_center" in manifest.features
    assert command_payload.command == "markets"
    assert brief_payload.command == "market_brief"
    assert center_payload.command == "capability_center"
    assert tree_payload.command == "memory_tree"
    assert source_payload.command == "source_list"
    assert pantry_payload.command == "pantry_deals"
    assert budget_payload.command == "budget_plan"
    assert cashflow_payload.command == "cashflow"
    assert people_payload.command == "people"
    assert evening_payload.command == "evening"
    assert context_payload.command == "lifestyle_context"
    assert today_payload.command == "today"
    assert basket_payload.text == "молоко"
    assert assistant_payload.text == "btc"
    assert task_payload.text == "ship mini app"
    assert note_payload.text == "remember this"
    assert reminder_payload.text == "tomorrow call Ivan"
    assert person_payload.data["name"] == "Ivan"
    assert person_payload.data["note"] == "prefers email"
    assert finance_payload.data["kind"] == "expense"
    assert finance_payload.data["amount"] == "100"
    assert account_payload.data["name"] == "Cash"
    assert subscription_payload.data["amount"] == "199"
    assert receipt_payload.text == "store\nmilk 100"


def test_mini_app_payload_rejects_oversized_text() -> None:
    long_basket = "м" * (MAX_BASKET_TEXT_CHARS + 1)
    long_assistant = "a" * (MAX_ASSISTANT_TEXT_CHARS + 1)

    with pytest.raises(ValueError, match="basket text is too large"):
        parse_mini_app_payload(
            '{"type":"basket_compare","text":"' + long_basket + '"}'
        )
    with pytest.raises(ValueError, match="assistant message is too large"):
        parse_mini_app_payload(
            '{"type":"assistant_message","text":"' + long_assistant + '"}'
        )
    with pytest.raises(ValueError, match="text is empty"):
        parse_mini_app_payload('{"type":"task_create","text":" "}')
    with pytest.raises(ValueError, match="transaction kind"):
        parse_mini_app_payload(
            '{"type":"finance_transaction","kind":"transfer","amount":"1","category":"x"}'
        )


def _signed_init_data(*, bot_token: str, user_id: int) -> str:
    pairs = {
        "auth_date": "1710000000",
        "query_id": "q",
        "user": json.dumps({"id": user_id}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(
        secret,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(pairs)

from __future__ import annotations

from datetime import UTC, datetime

from app.services.agenda import build_agenda
from app.services.assistant_jobs import AssistantJobStore, parse_job_request
from app.services.assistant_tools import run_tool
from app.services.audit_log import AuditLogStore
from app.services.conversation_summary import summarize_conversation
from app.services.memory_transfer import export_user_memory, import_user_memory
from app.services.mini_app import mini_app_manifest, parse_mini_app_payload
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


def test_conversation_summary_and_mini_app_manifest() -> None:
    summary = summarize_conversation(["надо написать план", "решили выбрать вариант A"])
    manifest = mini_app_manifest("https://example.com/app")
    command_payload = parse_mini_app_payload('{"type":"command","command":"markets"}')
    basket_payload = parse_mini_app_payload('{"type":"basket_compare","text":"молоко"}')
    assistant_payload = parse_mini_app_payload('{"type":"assistant_message","text":"btc"}')

    assert "Possible tasks" in summary.body
    assert "Possible decisions" in summary.body
    assert manifest.enabled is True
    assert "tasks" in manifest.features
    assert "market_watch" in manifest.features
    assert "pixel_assistant" in manifest.features
    assert command_payload.command == "markets"
    assert basket_payload.text == "молоко"
    assert assistant_payload.text == "btc"

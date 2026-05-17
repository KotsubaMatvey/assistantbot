from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from aiohttp import web

from app.config import Settings
from app.logging_config import get_logger
from app.services.audit_log import AuditLogStore
from app.services.market_watch import analyze_market_watch, fetch_market_watch
from app.services.mini_app_state import (
    add_mini_app_note,
    add_mini_app_person,
    add_mini_app_receipt,
    add_mini_app_reminder,
    add_mini_app_source,
    add_mini_app_task,
    add_mini_app_transaction,
    build_mini_app_state,
    delete_mini_app_source,
    update_mini_app_account,
    update_mini_app_subscription,
)
from app.services.obsidian_memory import ObsidianMemory
from app.services.source_connectors import SourceStore

logger = get_logger(__name__)


class MiniAppHttpServer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    async def start(self) -> None:
        if not self.settings.mini_app_api_enabled:
            return
        app = create_mini_app_web_app(self.settings)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(
            self.runner,
            self.settings.mini_app_api_host,
            self.settings.mini_app_api_port,
        )
        await self.site.start()
        logger.info(
            "mini_app_api_started",
            host=self.settings.mini_app_api_host,
            port=self.settings.mini_app_api_port,
        )

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()


def create_mini_app_web_app(settings: Settings) -> web.Application:
    app = web.Application(middlewares=[_cors_middleware])
    app["settings"] = settings
    app.router.add_get("/api/health", _health)
    app.router.add_get("/api/miniapp/state", _state)
    app.router.add_get("/api/miniapp/markets", _markets)
    app.router.add_post("/api/miniapp/event", _event)
    app.router.add_post("/api/miniapp/finance/transaction", _finance_transaction)
    app.router.add_post("/api/miniapp/finance/account", _finance_account)
    app.router.add_post("/api/miniapp/finance/subscription", _finance_subscription)
    app.router.add_post("/api/miniapp/task", _task)
    app.router.add_post("/api/miniapp/note", _note)
    app.router.add_post("/api/miniapp/reminder", _reminder)
    app.router.add_post("/api/miniapp/person", _person)
    app.router.add_post("/api/miniapp/receipt", _receipt)
    app.router.add_post("/api/miniapp/source", _source)
    app.router.add_post("/api/miniapp/source/delete", _source_delete)
    app.router.add_post("/api/miniapp/source/sync", _source_sync)
    app.router.add_route("OPTIONS", "/{tail:.*}", _options)
    _add_static_routes(app, settings)
    return app


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def _state(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    return _state_response(request, user_id)


async def _markets(request: web.Request) -> web.Response:
    _user_id_from_request(request)
    result = await fetch_market_watch()
    brief = analyze_market_watch(result)
    return web.json_response(
        {
            "fetched_at": result.fetched_at.isoformat(),
            "sentiment_label": brief.sentiment_label,
            "sentiment_score": str(brief.sentiment_score),
            "risk_regime": brief.risk_regime,
            "quotes": [
                {
                    "key": quote.key,
                    "name": quote.name,
                    "value": str(quote.value) if quote.value is not None else "",
                    "unit": quote.unit,
                    "change_percent": (
                        str(quote.change_percent) if quote.change_percent is not None else ""
                    ),
                    "error": quote.error or "",
                }
                for quote in result.quotes
            ],
            "data_gaps": brief.data_gaps,
        }
    )


async def _event(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    name = str(payload.get("name", "")).strip().lower().replace(" ", "_")[:80]
    if not name:
        raise web.HTTPBadRequest(text="event name is empty")
    detail = _event_detail(payload.get("data", {}))
    _record_mini_app_event(request, user_id, f"mini_app_{name}", detail)
    return web.json_response({"ok": True})


async def _finance_transaction(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        add_mini_app_transaction(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            kind=str(payload.get("kind", "")),
            amount=str(payload.get("amount", "")),
            category=str(payload.get("category", "")),
            note=str(payload.get("note", "")),
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_finance_transaction",
        f"{payload.get('kind', '')} {payload.get('amount', '')} {payload.get('category', '')}",
    )
    return _state_response(request, user_id)


async def _finance_account(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        update_mini_app_account(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            name=str(payload.get("name", "")),
            balance=str(payload.get("balance", "")),
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_account_update",
        str(payload.get("name", "")),
    )
    return _state_response(request, user_id)


async def _finance_subscription(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        update_mini_app_subscription(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            name=str(payload.get("name", "")),
            amount=str(payload.get("amount", "")),
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_subscription_update",
        str(payload.get("name", "")),
    )
    return _state_response(request, user_id)


async def _task(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    text = str(payload.get("text", "")).strip()
    if not text:
        raise web.HTTPBadRequest(text="task text is empty")
    add_mini_app_task(vault_path=_settings(request).obsidian_vault_path, user_id=user_id, text=text)
    _record_mini_app_event(request, user_id, "mini_app_task_create", text)
    return _state_response(request, user_id)


async def _note(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    text = str(payload.get("text", "")).strip()
    if not text:
        raise web.HTTPBadRequest(text="note text is empty")
    add_mini_app_note(vault_path=_settings(request).obsidian_vault_path, user_id=user_id, text=text)
    _record_mini_app_event(request, user_id, "mini_app_note_create", text)
    return _state_response(request, user_id)


async def _reminder(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        add_mini_app_reminder(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            text=str(payload.get("text", "")),
            timezone_name=_settings(request).timezone,
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_reminder_create",
        str(payload.get("text", "")),
    )
    return _state_response(request, user_id)


async def _person(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        add_mini_app_person(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            name=str(payload.get("name", "")),
            note=str(payload.get("note", "")),
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(request, user_id, "mini_app_person_note", str(payload.get("name", "")))
    return _state_response(request, user_id)


async def _receipt(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        add_mini_app_receipt(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            text=str(payload.get("text", "")),
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_receipt_save",
        f"chars={len(str(payload.get('text', '')))}",
    )
    return _state_response(request, user_id)


async def _source(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    try:
        source = add_mini_app_source(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            source_type=str(payload.get("source_type", "")),
            target=str(payload.get("target", "")),
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_source_add",
        f"{source.type} {source.url}",
    )
    return _state_response(request, user_id)


async def _source_delete(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    source_id = str(payload.get("id", ""))
    try:
        deleted = delete_mini_app_source(
            vault_path=_settings(request).obsidian_vault_path,
            user_id=user_id,
            source_id=source_id,
        )
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    if not deleted:
        raise web.HTTPNotFound(text="source not found")
    _record_mini_app_event(request, user_id, "mini_app_source_delete", source_id)
    return _state_response(request, user_id)


async def _source_sync(request: web.Request) -> web.Response:
    user_id = _user_id_from_request(request)
    payload = await _json_payload(request)
    source_id = str(payload.get("id", "")).strip() or None
    store = SourceStore(_settings(request).obsidian_vault_path)
    results = await store.sync_sources(
        user_id=user_id,
        memory=ObsidianMemory(_settings(request).obsidian_vault_path),
        source_id=source_id,
    )
    ok_count = sum(1 for result in results if result.ok)
    _record_mini_app_event(
        request,
        user_id,
        "mini_app_source_sync",
        f"requested={source_id or 'all'} ok={ok_count}/{len(results)}",
    )
    return _state_response(request, user_id)


async def _options(request: web.Request) -> web.Response:
    return web.Response()


def _state_response(request: web.Request, user_id: int) -> web.Response:
    settings = _settings(request)
    state = build_mini_app_state(
        vault_path=settings.obsidian_vault_path,
        user_id=user_id,
        timezone_name=settings.timezone,
    )
    return web.json_response(state)


async def _json_payload(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(text="request body must be JSON") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="request body must be an object")
    return payload


def _user_id_from_request(request: web.Request) -> int:
    settings = _settings(request)
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query.get("initData", "")
    if init_data:
        return validate_telegram_init_data(init_data, bot_token=settings.bot_token)
    if settings.env == "local":
        raw_user_id = request.headers.get("X-Mini-App-Dev-User-Id") or request.query.get("user_id")
        if raw_user_id:
            return int(raw_user_id)
    raise web.HTTPUnauthorized(text="Telegram initData is required")


def validate_telegram_init_data(init_data: str, *, bot_token: str) -> int:
    if not bot_token:
        raise web.HTTPUnauthorized(text="BOT_TOKEN is required for Mini App auth")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise web.HTTPUnauthorized(text="Telegram initData hash is missing")
    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise web.HTTPUnauthorized(text="Telegram initData hash is invalid")
    try:
        user = json.loads(pairs.get("user", "{}"))
        user_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise web.HTTPUnauthorized(text="Telegram initData user is invalid") from exc
    return user_id


def _add_static_routes(app: web.Application, settings: Settings) -> None:
    static_dir = Path(settings.mini_app_static_dir).expanduser()
    index_path = static_dir / "index.html"
    assets_dir = static_dir / "assets"
    if not index_path.exists():
        return
    if assets_dir.exists():
        app.router.add_static("/assets", assets_dir)

    async def index(_: web.Request) -> web.FileResponse:
        return web.FileResponse(index_path)

    app.router.add_get("/", index)
    app.router.add_get("/{tail:(?!api/).*}", index)


def _settings(request: web.Request) -> Settings:
    return request.app["settings"]


def _record_mini_app_event(
    request: web.Request,
    user_id: int,
    action: str,
    detail: str,
) -> None:
    try:
        AuditLogStore(_settings(request).obsidian_vault_path).record(
            user_id=user_id,
            action=action,
            detail=detail,
        )
    except Exception as exc:
        logger.warning("mini_app_event_audit_failed", action=action, error=str(exc))


def _event_detail(raw: object) -> str:
    if isinstance(raw, dict):
        safe = {str(key)[:50]: str(value)[:120] for key, value in raw.items()}
        return json.dumps(safe, ensure_ascii=False, sort_keys=True)[:500]
    return str(raw)[:500]


@web.middleware
async def _cors_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, X-Telegram-Init-Data, X-Mini-App-Dev-User-Id"
    )
    return response

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram.types import BotCommand


@dataclass(frozen=True)
class CommandDef:
    name: str
    description: str
    category: str
    args_hint: str = ""
    admin_only: bool = False

    @property
    def usage(self) -> str:
        suffix = f" {self.args_hint}" if self.args_hint else ""
        return f"/{self.name}{suffix}"


COMMAND_REGISTRY: tuple[CommandDef, ...] = (
    CommandDef("agenda", "показать задачи, напоминания, jobs и важное", "Память"),
    CommandDef("export_memory", "экспортировать память пользователя", "Память"),
    CommandDef("import_memory", "импортировать память из zip", "Память", "[--apply] <zip_path>"),
    CommandDef("orders", "показать standing orders", "Память"),
    CommandDef("order_add", "добавить standing order", "Память", "<text>"),
    CommandDef("order_delete", "удалить standing order", "Память", "<id>"),
    CommandDef("inbox_review", "показать заметки для разбора", "Память"),
    CommandDef("session_summary", "сохранить сводку текущей переписки", "Память"),
    CommandDef("today_tasks", "показать задачи на сегодня", "Память"),
    CommandDef("task_search", "найти задачи", "Память", "<query>"),
    CommandDef("task_tag", "добавить тег задаче", "Память", "<task_id> <tag>"),
    CommandDef("task_due", "добавить due reminder к задаче", "Память", "<task_id> <when> <text>"),
    CommandDef("later", "отложить задачу через reminder", "Память", "<task_id> <when> <text>"),
    CommandDef("source_trust", "показать доверие к источникам", "Память"),
    CommandDef("tools", "показать локальные tools", "Память"),
    CommandDef("tool", "запустить локальный tool", "Память", "<name> <input>"),
    CommandDef("mini_app", "открыть или проверить TG Mini App", "Память"),
    CommandDef("markets", "BTC, BTC.D и главные мировые индексы", "Рынки"),
    CommandDef("morning", "утренний дайджест: agenda, рынки, pantry, бюджет", "Ассистент"),
    CommandDef("status", "краткий статус ассистента", "Ассистент"),
    CommandDef("new", "начать новую логическую сессию", "Ассистент"),
    CommandDef("compact", "сжать текущую переписку в сводку", "Ассистент"),
    CommandDef("assistants", "показать безопасных помощников", "Ассистент"),
    CommandDef(
        "assistant_pick",
        "выбрать помощника",
        "Ассистент",
        "<secretary|buyer|market_analyst>",
    ),
    CommandDef("automations", "показать шаблоны автоматизаций", "Ассистент"),
    CommandDef("automation_enable", "включить автоматизацию", "Ассистент", "<template>"),
    CommandDef(
        "mode",
        "выбрать режим ассистента",
        "Память",
        "<secretary|researcher|editor|analyst>",
    ),
    CommandDef("trace", "включить или выключить trace-режим", "Память", "on|off"),
    CommandDef("verbose", "включить или выключить подробные ответы", "Память", "on|off"),
    CommandDef("session_reset", "начать новую логическую сессию", "Память"),
    CommandDef("usage", "показать счётчики памяти и ассистента", "Память"),
    CommandDef("skills", "показать skills ассистента", "Память"),
    CommandDef("skill", "выбрать активный skill", "Память", "<name>"),
    CommandDef("skill_add", "создать skill в vault", "Память", "<name> <instructions>"),
    CommandDef(
        "job_add",
        "создать периодическую задачу",
        "Память",
        "<daily|every|once> <when> "
        "[message|digest|rss|doctor|silent|markets|morning|price_alerts] <text>",
    ),
    CommandDef("jobs", "показать периодические задачи", "Память"),
    CommandDef("job_runs", "показать историю запусков jobs", "Память"),
    CommandDef("job_delete", "удалить job", "Память", "<job_id>"),
    CommandDef(
        "preference",
        "сохранить предпочтение для покупок, быта или бюджета",
        "Память",
        "<текст>",
    ),
    CommandDef(
        "lifestyle_context",
        "показать связанный контекст покупок, быта и решений",
        "Память",
    ),
    CommandDef("task", "создать задачу в памяти", "Память", "<текст>"),
    CommandDef("journal", "сохранить запись личного журнала", "Память", "<текст>"),
    CommandDef("digest", "показать дайджест памяти за период", "Память", "[дней]"),
    CommandDef("person", "вести заметки о человеке", "Память", "<имя>[: заметка]"),
    CommandDef("decide", "создать черновик решения", "Память", "<вопрос; варианты>"),
    CommandDef("spaces", "показать пространства памяти", "Память"),
    CommandDef("space", "выбрать активное пространство памяти", "Память", "<name>"),
    CommandDef("sources", "показать источники памяти", "Память"),
    CommandDef("assistant_capabilities", "показать backend-возможности ассистента", "Память"),
    CommandDef("delete_memory", "запросить удаление заметки", "Память", "<note_id>"),
    CommandDef("approve", "подтвердить ожидающее действие", "Память", "<code>"),
    CommandDef("recent", "показать последние заметки", "Память"),
    CommandDef("collections", "показать коллекции по тегам и типам", "Память"),
    CommandDef("collection", "показать заметки одной коллекции", "Память", "<название>"),
    CommandDef("pin", "закрепить важную заметку", "Память", "<текст>"),
    CommandDef("pins", "показать важные заметки", "Память"),
    CommandDef("done", "закрыть задачу из памяти", "Память", "<ID или номер>"),
    CommandDef("remind", "создать напоминание", "Память", "<когда> <текст>"),
    CommandDef("reminders", "показать активные напоминания", "Память"),
    CommandDef("voice_note", "сохранить расшифровку голосовой заметки", "Память", "<текст>"),
    CommandDef("decisions", "показать журнал решений", "Память"),
    CommandDef("start", "первый запуск и краткая инструкция", "Основное"),
    CommandDef("help", "список команд и формат корзины", "Основное"),
    CommandDef("settings", "магазины, карты лояльности и режим сравнения", "Основное"),
    CommandDef("capture", "быстро сохранить мысль, задачу или факт", "Память", "<текст>"),
    CommandDef("today", "показать сегодняшнюю ленту памяти", "Память"),
    CommandDef("tasks", "показать открытые задачи из памяти", "Память"),
    CommandDef("context", "найти связанный контекст по теме", "Память", "<тема>"),
    CommandDef("remember", "сохранить заметку в память", "Память", "<заметка>"),
    CommandDef("memory", "найти заметку в памяти", "Память", "<запрос>"),
    CommandDef("ask", "ответить на вопрос по памяти", "Память", "<вопрос>"),
    CommandDef("learn_url", "сохранить страницу в память", "Память", "<ссылка>"),
    CommandDef("rss_add", "добавить RSS/Atom-подписку", "Память", "<ссылка>"),
    CommandDef("rss_digest", "прочитать RSS/Atom-подписки", "Память"),
    CommandDef("prices", "сравнить список покупок", "Покупки", "<список товаров>"),
    CommandDef("last", "повторить последнюю сохраненную корзину", "Покупки"),
    CommandDef("watch_price", "следить за ценой товара", "Покупки", "<товар> <цена>"),
    CommandDef("price_alerts", "показать ценовые сигналы", "Покупки"),
    CommandDef("price_unwatch", "удалить ценовой сигнал", "Покупки", "<alert_id>"),
    CommandDef("check_alerts", "проверить ценовые сигналы сейчас", "Покупки"),
    CommandDef("pantry", "показать домашний склад", "Дом"),
    CommandDef("pantry_add", "добавить продукт на склад", "Дом", "<товар> [кол-во] [ед] [дата]"),
    CommandDef("pantry_use", "списать продукт со склада", "Дом", "<id|name> [кол-во]"),
    CommandDef("pantry_plan", "что скоро истекает и что докупить", "Дом"),
    CommandDef("pantry_deals", "что докупить по выгодным текущим ценам", "Дом"),
    CommandDef("receipt", "сохранить текстовый чек", "Бюджет", "<товар цена...>"),
    CommandDef("budget", "показать бюджет месяца", "Бюджет", "[YYYY-MM]"),
    CommandDef("budget_set", "задать месячный бюджет", "Бюджет", "<YYYY-MM> <сумма>"),
    CommandDef("budget_plan", "сравнить последнюю корзину с чеками месяца", "Бюджет", "[YYYY-MM]"),
    CommandDef("family", "показать семейное пространство", "Семья"),
    CommandDef("family_create", "создать семейное пространство", "Семья", "<name>"),
    CommandDef("family_join", "войти в семейное пространство", "Семья", "<invite_code>"),
    CommandDef("family_add", "добавить пункт в общий список", "Семья", "<текст>"),
    CommandDef("admin_status", "состояние цен, магазинов и скрапинга", "Админ", admin_only=True),
    CommandDef("admin_diag", "диагностика бота и окружения", "Админ", admin_only=True),
    CommandDef("admin_doctor", "полная диагностика ассистента", "Админ", admin_only=True),
    CommandDef("admin_secret_scan", "локальный поиск возможных секретов", "Админ", admin_only=True),
    CommandDef("admin_audit", "показать audit log", "Админ", admin_only=True),
    CommandDef("admin_onboarding", "показать шаги настройки ассистента", "Админ", admin_only=True),
    CommandDef(
        "pairing_approve",
        "подтвердить pairing-код пользователя",
        "Админ",
        "<code>",
        admin_only=True,
    ),
    CommandDef("access_list", "показать allowlist пользователей", "Админ", admin_only=True),
    CommandDef(
        "admin_backup",
        "архив памяти и безопасных файлов проекта",
        "Админ",
        admin_only=True,
    ),
    CommandDef("admin_logs", "последние ошибки скрапинга", "Админ", admin_only=True),
    CommandDef("admin_deploy_check", "проверка self-hosting настроек", "Админ", admin_only=True),
    CommandDef("admin_refresh_prices", "обновить цены по всем магазинам", "Админ", admin_only=True),
    CommandDef(
        "admin_scraper_diag",
        "диагностика scraper-а без сохранения цен",
        "Админ",
        "<store_slug> [query]",
        admin_only=True,
    ),
    CommandDef(
        "admin_scrape_store",
        "обновить цены одного магазина",
        "Админ",
        "<store_slug>",
        admin_only=True,
    ),
)


def public_command_defs() -> list[CommandDef]:
    return [command for command in COMMAND_REGISTRY if not command.admin_only]


def public_bot_commands() -> list[BotCommand]:
    from aiogram.types import BotCommand

    return [
        BotCommand(command=command.name, description=command.description)
        for command in public_command_defs()
    ]


def help_text(*, include_admin: bool = False) -> str:
    lines = [
        "Пришли список товаров строками, через запятую или точку с запятой.",
        "",
        "Примеры:",
        "молоко 2.5 1 л",
        "яйца C1 10 шт",
        "сахар 1 кг",
        "",
        "Команды:",
    ]
    for command in COMMAND_REGISTRY:
        if command.admin_only and not include_admin:
            continue
        lines.append(f"{command.usage} — {command.description}")
    return "\n".join(lines)


def resolve_command(name: str) -> CommandDef | None:
    normalized = name.lower().lstrip("/")
    return next((command for command in COMMAND_REGISTRY if command.name == normalized), None)

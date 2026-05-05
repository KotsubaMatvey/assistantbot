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
    CommandDef("start", "первый запуск и краткая инструкция", "Основное"),
    CommandDef("help", "список команд и формат корзины", "Основное"),
    CommandDef("settings", "магазины, карты лояльности и режим сравнения", "Основное"),
    CommandDef("remember", "сохранить заметку в память", "Память", "<заметка>"),
    CommandDef("memory", "найти заметку в памяти", "Память", "<запрос>"),
    CommandDef("ask", "ответить на вопрос по памяти", "Память", "<вопрос>"),
    CommandDef("learn_url", "сохранить страницу в память", "Память", "<ссылка>"),
    CommandDef("rss_add", "добавить RSS/Atom-подписку", "Память", "<ссылка>"),
    CommandDef("rss_digest", "прочитать RSS/Atom-подписки", "Память"),
    CommandDef("prices", "сравнить список покупок", "Покупки", "<список товаров>"),
    CommandDef("last", "повторить последнюю сохраненную корзину", "Покупки"),
    CommandDef("admin_status", "состояние цен, магазинов и скрапинга", "Админ", admin_only=True),
    CommandDef("admin_diag", "диагностика бота и окружения", "Админ", admin_only=True),
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


def public_bot_commands() -> list["BotCommand"]:
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

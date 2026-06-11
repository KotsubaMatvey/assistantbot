from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.services.chat_dialogue import ChatDialogueEngine

NOW = datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
USER_ID = 123


def _callback(reply, verb: str) -> str:
    return next(
        button.data
        for row in reply.rows
        for button in row
        if button.data.startswith(f"chat:{verb}:")
    )


def test_dialogue_creates_reminders_directly_and_after_clarification(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    direct = engine.handle_text(
        user_id=USER_ID,
        text="напомни завтра в 9 позвонить врачу",
        now=NOW,
    )
    prompt = engine.handle_text(user_id=USER_ID, text="напомни купить подарок", now=NOW)
    clarified = engine.handle_text(user_id=USER_ID, text="В субботу после обеда", now=NOW)

    reminders = engine.memory.list_reminders(user_id=USER_ID)
    assert "25.05.2026 в 09:00" in direct.text
    assert "Когда напомнить" in prompt.text
    assert "30.05.2026 в 14:00" in clarified.text
    assert reminders[0].due_at == datetime(2026, 5, 25, 6, 0, tzinfo=UTC)
    assert reminders[1].due_at == datetime(2026, 5, 30, 11, 0, tzinfo=UTC)
    assert _callback(clarified, "snooze")


def test_dialogue_records_edits_and_undoes_expense(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    saved = engine.handle_text(
        user_id=USER_ID,
        text="Я потратил 740 рублей на продукты",
        now=NOW,
    )
    request_edit = engine.handle_callback(user_id=USER_ID, data=_callback(saved, "edit"))
    edited = engine.handle_text(user_id=USER_ID, text="транспорт", now=NOW)
    undone = engine.handle_callback(user_id=USER_ID, data=_callback(saved, "undo"))

    assert "740" in saved.text
    assert request_edit.text == "Напиши новую категорию расхода."
    assert "транспорт" in edited.text
    assert "Отменил" in undone.text
    assert engine.finance.list_transactions(user_id=USER_ID) == []


def test_dialogue_manages_shopping_list_and_compound_requests(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    shopping = engine.handle_text(
        user_id=USER_ID,
        text="добавь молоко и яйца в покупки",
        now=NOW,
    )
    listed = engine.handle_text(user_id=USER_ID, text="что купить", now=NOW)
    compound = engine.handle_text(
        user_id=USER_ID,
        text="Я потратил 1250 на продукты и ещё завтра надо забрать заказ",
        now=NOW,
    )
    completed = engine.handle_text(user_id=USER_ID, text="В 18", now=NOW)
    engine.handle_callback(user_id=USER_ID, data=_callback(shopping, "undo"))

    assert "молоко" in listed.text and "яйца" in listed.text
    assert "1250" in compound.text and "Во сколько завтра" in compound.text
    assert "25.05.2026 в 18:00" in completed.text
    assert engine.shopping.list_items(user_id=USER_ID) == []


def test_dialogue_answers_memory_with_source_and_can_forget_it(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    engine.handle_text(
        user_id=USER_ID,
        text="запомни, что мама предпочитает зелёный чай",
        now=NOW,
    )
    answer = engine.handle_text(user_id=USER_ID, text="что мама предпочитает?", now=NOW)
    confirm = engine.handle_callback(user_id=USER_ID, data=_callback(answer, "forget"))
    removed = engine.handle_callback(user_id=USER_ID, data=_callback(confirm, "delete"))

    assert "зелёный чай" in answer.text
    assert "Источник:" in answer.text
    assert "Удалить из памяти" in confirm.text
    assert removed.text == "Удалил из памяти."
    assert not engine.memory.search_user_notes(user_id=USER_ID, query="мама чай")
    assert not any(
        event.action == "chat_shopping_add"
        for event in engine.audit.list_events(user_id=USER_ID)
    )


def test_dialogue_profile_voice_and_photo_fallbacks(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    setting = engine.handle_text(user_id=USER_ID, text="вечером это в 20", now=NOW)
    reminder = engine.handle_text(
        user_id=USER_ID,
        text="напомни завтра вечером оплатить интернет",
        now=NOW,
    )
    engine.expect_voice_transcript(user_id=USER_ID)
    task = engine.handle_text(user_id=USER_ID, text="добавь задачу позвонить маме", now=NOW)
    photo = engine.expect_photo_receipt(user_id=USER_ID)
    receipt = engine.handle_text(
        user_id=USER_ID,
        text="магазин: Магнит\nмолоко 89.90\nхлеб 45",
        now=NOW,
    )
    engine.handle_callback(user_id=USER_ID, data=_callback(receipt, "undo"))

    assert "20:00" in setting.text and "25.05.2026 в 20:00" in reminder.text
    assert "задачу" in task.text
    assert "OCR не подключён" in photo.text
    assert "134.90" in receipt.text
    assert engine.spending.list_receipts(user_id=USER_ID) == []


def test_dialogue_applies_recognized_media_only_after_confirmation(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    voice = engine.confirm_media_text(
        user_id=USER_ID,
        text="добавь задачу позвонить маме",
        source="voice",
    )
    assert engine.memory.list_open_tasks(user_id=USER_ID) == []
    task = engine.handle_callback(user_id=USER_ID, data=_callback(voice, "apply"), now=NOW)
    receipt = engine.confirm_media_text(
        user_id=USER_ID,
        text="магазин: Магнит\nмолоко 89.90",
        source="receipt",
    )
    saved = engine.handle_text(user_id=USER_ID, text="да", now=NOW)

    assert "задачу" in task.text
    assert "89.90" in saved.text
    assert len(engine.memory.list_open_tasks(user_id=USER_ID)) == 1
    assert len(engine.spending.list_receipts(user_id=USER_ID)) == 1
    assert _callback(receipt, "apply") == "chat:apply:pending"


def test_dialogue_corrects_latest_expense_without_counting_transfer(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))
    engine.handle_text(user_id=USER_ID, text="потратил 400 на такси", now=NOW)

    corrected = engine.handle_text(user_id=USER_ID, text="не расход, а перевод", now=NOW)
    summary = engine.handle_text(
        user_id=USER_ID,
        text="сколько я потратил на такси в этом месяце?",
        now=NOW,
    )

    assert "Переводы не учитываю" in corrected.text
    assert "0 RUB" in summary.text
    assert sum(
        (item.amount for item in engine.finance.list_transactions(user_id=USER_ID)),
        Decimal("0"),
    ) == Decimal("0")


def test_dialogue_shows_today_memory_corrections_and_change_history(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))
    engine.handle_text(user_id=USER_ID, text="запомни, что маму зовут Ирина", now=NOW)

    corrected = engine.handle_text(user_id=USER_ID, text="исправь имя мамы на Ольга", now=NOW)
    today = engine.handle_text(
        user_id=USER_ID,
        text="покажи, что ты сегодня запомнил",
        now=NOW,
    )
    history = engine.handle_text(user_id=USER_ID, text="покажи историю изменений", now=NOW)
    answer = engine.handle_text(user_id=USER_ID, text="как зовут маму?", now=NOW)
    confirm = engine.handle_callback(user_id=USER_ID, data=_callback(answer, "forget"))
    engine.handle_callback(user_id=USER_ID, data=_callback(confirm, "delete"))
    after_delete = engine.handle_text(user_id=USER_ID, text="как зовут маму?", now=NOW)

    assert "Актуально: имя мамы = Ольга" in corrected.text
    assert "маму зовут Ирина" in today.text and "Ольга" in today.text
    assert "memory_create" in history.text
    assert "Ольга" in history.text
    assert "Ольга" in answer.text and "Ирина" not in answer.text
    assert "Ольга" not in after_delete.text


def test_dialogue_schedules_briefs_and_responds_to_delivered_reminders(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    morning = engine.handle_text(
        user_id=USER_ID,
        text="присылай утреннюю сводку в 8",
        now=NOW,
    )
    evening = engine.handle_text(
        user_id=USER_ID,
        text="каждый вечер в 20:30 подводи итоги",
        now=NOW,
    )
    delivered = engine.delivered_reminder_reply(
        user_id=USER_ID,
        reminder_id="sent-id",
        body="оплатить интернет",
        now=NOW,
    )
    tomorrow = engine.handle_callback(
        user_id=USER_ID,
        data=_callback(delivered, "rempost").replace(":60", ":1440"),
        now=NOW,
    )

    jobs = engine.jobs.list_jobs(user_id=USER_ID)
    assert "08:00" in morning.text and "20:30" in evening.text
    assert {job.delivery_mode for job in jobs} == {"morning", "evening"}
    assert "25.05.2026" in tomorrow.text


def test_dialogue_can_undo_latest_record_and_move_expense_to_yesterday(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))
    engine.handle_text(user_id=USER_ID, text="запомни временную заметку", now=NOW)

    undone = engine.handle_text(user_id=USER_ID, text="отмени последнюю запись", now=NOW)
    engine.handle_text(user_id=USER_ID, text="потратил 400 на такси", now=NOW)
    moved = engine.handle_text(user_id=USER_ID, text="этот расход был вчера", now=NOW)
    transaction = engine.finance.list_transactions(user_id=USER_ID)[0]

    assert undone.text == "Отменил последнее действие."
    assert not engine.memory.search_user_notes(user_id=USER_ID, query="временную")
    assert moved.text == "Перенёс последний расход на 23.05.2026."
    assert transaction.created_at == datetime(2026, 5, 23, 9, 0, tzinfo=UTC)
    assert any(
        event.action == "chat_expense_date"
        for event in engine.audit.list_events(user_id=USER_ID)
    )


def test_dialogue_records_income_and_undoes_it(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    saved = engine.handle_text(user_id=USER_ID, text="Получил 50000 зарплата", now=NOW)
    undone = engine.handle_text(user_id=USER_ID, text="отмени последнюю запись", now=NOW)

    assert "доход" in saved.text.lower()
    assert "50" in saved.text
    assert "Отменил" in undone.text
    assert engine.finance.list_transactions(user_id=USER_ID) == []


def test_dialogue_asks_income_source_when_missing(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    prompt = engine.handle_text(user_id=USER_ID, text="заработал 3000", now=NOW)
    saved = engine.handle_text(user_id=USER_ID, text="фриланс", now=NOW)

    assert "Откуда доход" in prompt.text
    assert "фриланс" in saved.text
    transactions = engine.finance.list_transactions(user_id=USER_ID, kind="income")
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("3000")


def test_dialogue_parses_bought_item_as_expense(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    saved = engine.handle_text(user_id=USER_ID, text="купил кофе за 300", now=NOW)

    assert "расход" in saved.text.lower()
    transactions = engine.finance.list_transactions(user_id=USER_ID, kind="expense")
    assert len(transactions) == 1
    assert transactions[0].category == "кофе"


def test_dialogue_summarizes_spending_for_periods(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))
    engine.handle_text(user_id=USER_ID, text="потратил 100 на еду", now=NOW)
    engine.handle_text(
        user_id=USER_ID,
        text="потратил 200 на еду",
        now=NOW.replace(day=20),
    )

    today = engine.handle_text(user_id=USER_ID, text="сколько потратил сегодня", now=NOW)
    week = engine.handle_text(user_id=USER_ID, text="сколько потратил за неделю", now=NOW)
    month = engine.handle_text(user_id=USER_ID, text="сколько потратил на еду", now=NOW)

    assert "Сегодня" in today.text and "100" in today.text
    assert "За неделю" in week.text and "300" in week.text
    assert "2026-05" in month.text and "300" in month.text


def test_dialogue_explains_capabilities(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    reply = engine.handle_text(user_id=USER_ID, text="что ты умеешь?", now=NOW)

    assert "second brain" in reply.text
    assert "запомни" in reply.text
    assert reply.event is None


def test_dialogue_routes_freeform_text_without_implicit_memory_capture(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    message = engine.handle_text(user_id=USER_ID, text="Расскажи, как лучше начать день", now=NOW)
    question = engine.handle_text(
        user_id=USER_ID,
        text="Что такое интервальное планирование?",
        now=NOW,
    )

    assert message.event == "freeform"
    assert question.event == "freeform"
    assert engine.memory.search_user_notes(user_id=USER_ID, query="начать день") == []
    assert engine.memory.search_user_notes(user_id=USER_ID, query="планирование") == []


def test_dialogue_keeps_explicit_memory_capture_in_conversation_first_mode(tmp_path) -> None:
    engine = ChatDialogueEngine(str(tmp_path))

    saved = engine.handle_text(
        user_id=USER_ID,
        text="Запомни, что лучше планировать день вечером",
        now=NOW,
    )

    assert "Запомнил" in saved.text
    assert engine.memory.search_user_notes(user_id=USER_ID, query="планировать день вечером")

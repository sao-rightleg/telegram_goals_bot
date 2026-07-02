from app.bot.messages import (
    INSIGHT_ADD_BUTTON,
    INSIGHT_CANCEL_BUTTON,
    INSIGHT_DONE_BUTTON,
    INSIGHT_DUPLICATE_TEXT,
    INSIGHT_EMPTY_LIST_TEXT,
    INSIGHT_EMPTY_TEXT,
    INSIGHT_LIST_BUTTON,
    INSIGHT_MISSING_ACTIVE_GOAL_TEXT,
    INSIGHT_MISSING_TEXT,
    INSIGHT_READ_FULL_TEXT,
    INSIGHT_SUCCESS_TEXT,
    INSIGHT_TITLE_PROMPT_TEXT,
    INSIGHT_TITLE_TOO_LONG_TEXT,
    INSIGHT_VOICE_NOT_AVAILABLE_TEXT,
    build_insight_menu_buttons,
    build_insight_text_buttons,
    format_full_insight_text,
    format_insight_page,
    make_insight_title_fallback,
)
from app.services.insight_models import InsightListItem, InsightPage, InsightScope


def test_insight_menu_copy_matches_user_spec() -> None:
    assert INSIGHT_ADD_BUTTON == "➕ Добавить инсайт"
    assert INSIGHT_LIST_BUTTON == "📜 Посмотреть инсайты"
    assert INSIGHT_CANCEL_BUTTON == "Отмена"
    assert INSIGHT_DONE_BUTTON == "✅ Готово"

    assert build_insight_menu_buttons() == (INSIGHT_ADD_BUTTON, INSIGHT_LIST_BUTTON)
    assert build_insight_text_buttons() == (INSIGHT_DONE_BUTTON, INSIGHT_CANCEL_BUTTON)


def test_insight_status_and_validation_copy_matches_user_spec() -> None:
    assert INSIGHT_SUCCESS_TEXT == "Инсайт сохранён."
    assert INSIGHT_DUPLICATE_TEXT == "Инсайт уже сохранён."
    assert INSIGHT_MISSING_TEXT == "Инсайт не найден."
    assert INSIGHT_EMPTY_LIST_TEXT == "У тебя пока нет сохранённых инсайтов."
    assert (
        INSIGHT_MISSING_ACTIVE_GOAL_TEXT
        == "Прости, у тебя не зафиксировано активной цели, обратись к капитану"
    )
    assert (
        INSIGHT_EMPTY_TEXT
        == "Я не получил текст инсайта. Отправь инсайт текстом и нажми ✅ Готово."
    )
    assert INSIGHT_TITLE_PROMPT_TEXT == "Как кратко озаглавить твой инсайт?"
    assert "120" in INSIGHT_TITLE_TOO_LONG_TEXT
    assert "Голосовые инсайты будут доступны позже" in INSIGHT_VOICE_NOT_AVAILABLE_TEXT

    for text in (
        INSIGHT_SUCCESS_TEXT,
        INSIGHT_DUPLICATE_TEXT,
        INSIGHT_MISSING_TEXT,
        INSIGHT_EMPTY_LIST_TEXT,
        INSIGHT_MISSING_ACTIVE_GOAL_TEXT,
        INSIGHT_EMPTY_TEXT,
        INSIGHT_TITLE_PROMPT_TEXT,
        INSIGHT_TITLE_TOO_LONG_TEXT,
        INSIGHT_VOICE_NOT_AVAILABLE_TEXT,
    ):
        assert "token" not in text.lower()
        assert "secret" not in text.lower()
        assert "participant_id" not in text
        assert "goal_id" not in text


def test_insight_scope_contract_is_current_week_only() -> None:
    assert InsightScope.CURRENT_WEEK.value == "current_week"
    assert [scope.value for scope in InsightScope] == ["current_week"]


def test_title_fallback_uses_first_100_characters_without_breaking_words() -> None:
    text = (
        "Сегодня я понял, что мне не хватает планирования, потому что утро снова "
        "уходит в ежедневную рутину и я забываю про цель."
    )

    title = make_insight_title_fallback(text)

    assert len(title) <= 100
    assert title.startswith("Сегодня я понял")
    assert title.endswith("...")


def test_insight_page_formatting_includes_read_full_action() -> None:
    item = InsightListItem(
        insight_id="I001",
        insight_date="2026-06-23",
        title="Нехватка планирования замедляет меня",
        text_preview=(
            "Сегодня я понял, что мне не хватает планирования, так как я начинаю утро "
            "и снова погружаюсь в ежедневную рутину."
        ),
    )
    page = InsightPage(items=(item,), page_index=0, page_size=10, total_count=16)

    text = format_insight_page(page)

    assert "Твои инсайты: 1-10 из 16" in text
    assert "23.06.2026" in text
    assert "Инсайт: Нехватка планирования замедляет меня" in text
    assert f"...{INSIGHT_READ_FULL_TEXT}" in text
    assert page.has_older is True
    assert page.has_newer is False


def test_empty_insight_page_uses_empty_list_copy() -> None:
    page = InsightPage(items=(), page_index=0, page_size=10, total_count=0)

    assert format_insight_page(page) == INSIGHT_EMPTY_LIST_TEXT
    assert page.has_older is False
    assert page.has_newer is False


def test_full_insight_text_format_includes_title_and_text() -> None:
    item = InsightListItem(
        insight_id="I001",
        insight_date="2026-06-23",
        title="Нехватка планирования замедляет меня",
        text_preview="Короткий текст",
        full_text="Полный текст инсайта\nсо второй строкой.",
    )

    text = format_full_insight_text(item)

    assert text == (
        "23.06.2026\n"
        "Инсайт: Нехватка планирования замедляет меня\n\n"
        "Полный текст инсайта\nсо второй строкой."
    )

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import INSIGHT_FULL_TEXT_CALLBACK_PREFIX
from app.bot.messages import INSIGHT_EMPTY_LIST_TEXT, INSIGHT_MISSING_TEXT
from app.services.insights import InsightService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.sqlite import initialize_schema


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
USER = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")


def test_empty_list_returns_approved_copy(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        insights=[],
    )

    response = service.list_insights(USER, page_index=0, now=NOW)

    assert response.text == INSIGHT_EMPTY_LIST_TEXT


def test_list_shows_current_participant_latest_10_first(tmp_path: Path) -> None:
    insights = [_insight(f"I{index:03d}", "P001", f"2026-07-{index:02d}") for index in range(1, 13)]
    insights.append(_insight("I999", "P002", "2026-07-20"))
    service, _gateway, _main_bot, _error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001), _participant("P002", 1002)],
        insights=insights,
    )

    response = service.list_insights(USER, page_index=0, now=NOW)

    assert "Твои инсайты: 1-10 из 12" in response.text
    assert "12.07.2026" in response.text
    assert "03.07.2026" in response.text
    assert "02.07.2026" not in response.text
    assert "20.07.2026" not in response.text


def test_list_sends_read_full_buttons_for_visible_insights(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        insights=[
            _insight("I001", "P001", "2026-07-02", text="Первый полный текст."),
            _insight("I002", "P001", "2026-07-03", text="Второй полный текст."),
        ],
    )

    response = service.list_insights(USER, page_index=0, now=NOW)

    assert response.buttons == main_bot.sent_messages[-1].buttons
    assert [button.text for button in response.buttons] == [
        "читать целиком: Инсайт I002",
        "читать целиком: Инсайт I001",
    ]
    assert [button.callback_data for button in response.buttons] == [
        f"{INSIGHT_FULL_TEXT_CALLBACK_PREFIX}I002",
        f"{INSIGHT_FULL_TEXT_CALLBACK_PREFIX}I001",
    ]


def test_list_uses_untitled_copy_when_insight_title_is_empty(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        insights=[
            _insight(
                "I001",
                "P001",
                "2026-07-02",
                title="",
                text="Не хватает планирования. Завтра начну с конкретного дела.",
            ),
        ],
    )

    response = service.list_insights(USER, page_index=0, now=NOW)

    assert response.parse_mode == "HTML"
    assert "Инсайт без названия 01" in response.text
    assert "Инсайт: Не хватает планирования" not in response.text
    assert response.text.count("Не хватает планирования") == 1
    assert "<blockquote expandable>" in response.text
    assert main_bot.sent_messages[-1].buttons[0].text == "читать целиком: Инсайт без названия 01"
    assert main_bot.sent_messages[-1].parse_mode == "HTML"


def test_full_text_uses_same_untitled_number_as_list(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        insights=[
            _insight("I001", "P001", "2026-07-01", title=""),
            _insight("I002", "P001", "2026-07-02", title=""),
        ],
    )

    response = service.get_full_text(USER, insight_id="I001", now=NOW)

    assert response.parse_mode == "HTML"
    assert "Инсайт без названия 02" in response.text
    assert "<blockquote expandable>" in response.text


def test_pagination_over_16_insights_is_bounded(tmp_path: Path) -> None:
    insights = [_insight(f"I{index:03d}", "P001", f"2026-07-{index:02d}") for index in range(1, 17)]
    service, _gateway, _main_bot, _error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        insights=insights,
    )

    first = service.list_insights(USER, page_index=0, now=NOW)
    second = service.list_insights(USER, page_index=1, now=NOW)
    too_far = service.list_insights(USER, page_index=99, now=NOW)
    too_low = service.list_insights(USER, page_index=-1, now=NOW)

    assert "Твои инсайты: 1-10 из 16" in first.text
    assert "16.07.2026" in first.text
    assert "07.07.2026" in first.text
    assert "Твои инсайты: 11-16 из 16" in second.text
    assert "06.07.2026" in second.text
    assert "01.07.2026" in second.text
    assert too_far.text == second.text
    assert too_low.text == first.text


def test_full_text_callback_returns_own_insight_only(tmp_path: Path) -> None:
    service, _gateway, _main_bot, error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001), _participant("P002", 1002)],
        insights=[
            _insight("I001", "P001", "2026-07-02", text="Полный текст своего инсайта."),
            _insight("I002", "P002", "2026-07-03", text="Чужой текст."),
        ],
    )

    own = service.get_full_text(USER, insight_id="I001", now=NOW)
    other = service.get_full_text(USER, insight_id="I002", now=NOW)

    assert "Полный текст своего инсайта." in own.text
    assert "Чужой текст" not in own.text
    assert other.text == INSIGHT_MISSING_TEXT
    assert len(error_bot.sent_messages) == 1
    assert "missing_insight_callback" in error_bot.sent_messages[0].text
    assert "Чужой текст" not in error_bot.sent_messages[0].text


def test_stale_callback_notifies_admin(tmp_path: Path) -> None:
    service, _gateway, _main_bot, error_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        insights=[],
    )

    response = service.get_full_text(USER, insight_id="I404", now=NOW)

    assert response.text == INSIGHT_MISSING_TEXT
    assert len(error_bot.sent_messages) == 1
    assert "missing_insight_callback" in error_bot.sent_messages[0].text
    assert "I404" in error_bot.sent_messages[0].text


def _build_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
    insights: list[dict[str, object]],
) -> tuple[InsightService, FakeSheetsGateway, FakeBotClient, FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(participants=participants, insights=insights)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    return (
        InsightService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            drafts=InsightDraftRepository(db_path),
        ),
        gateway,
        main_bot,
        error_bot,
    )


def _participant(participant_id: str, telegram_id: int) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": "participant",
        "team_id": "T001",
        "consent_given": True,
    }


def _insight(
    insight_id: str,
    participant_id: str,
    insight_date: str,
    *,
    text: str | None = None,
    title: str | None = None,
) -> dict[str, object]:
    return {
        "insight_id": insight_id,
        "participant_id": participant_id,
        "goal_id": "G001",
        "week_number": 4,
        "insight_scope": "current_week",
        "insight_title": f"Инсайт {insight_id}" if title is None else title,
        "insight_date": insight_date,
        "insight_text": text or f"Текст инсайта {insight_id}",
        "created_by_id": participant_id,
        "created_by_role": "participant",
        "created_at": f"{insight_date}T10:00:00+05:00",
    }

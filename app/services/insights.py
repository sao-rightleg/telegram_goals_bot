"""Participant personal insight service flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from app.bot.clients import BotClient, TelegramInlineButton
from app.bot.menus import INSIGHT_FULL_TEXT_CALLBACK_PREFIX, build_role_menu
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_DECLINE_BUTTON,
    CONSENT_TEXT,
    INSIGHT_DUPLICATE_TEXT,
    INSIGHT_EMPTY_TEXT,
    INSIGHT_MISSING_ACTIVE_GOAL_TEXT,
    INSIGHT_MISSING_TEXT,
    INSIGHT_READ_FULL_TEXT,
    INSIGHT_SUCCESS_TEXT,
    INSIGHT_TITLE_PROMPT_TEXT,
    INSIGHT_TITLE_TOO_LONG_TEXT,
    INSIGHT_VOICE_NOT_AVAILABLE_TEXT,
    TELEGRAM_HTML_PARSE_MODE,
    UNKNOWN_USER_TEXT,
    build_insight_menu_buttons,
    build_insight_text_buttons,
    format_full_insight_text,
    format_insight_page,
    format_untitled_insight_title,
)
from app.scheduler.calendar import current_challenge_week_number
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.insight_models import InsightListItem, InsightPage
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.voice_messages import VoiceMessageInput, VoiceMessageService
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.insight_drafts import InsightDraftRepository


@dataclass(frozen=True)
class InsightService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    drafts: InsightDraftRepository
    voice_messages: VoiceMessageService | None = None

    def show_menu(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        context = self._resolve_participant(user, now=now)
        if isinstance(context, FlowResponse):
            return context
        return self._send(user, text="Мои инсайты", buttons=build_insight_menu_buttons())

    def start_add(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        participant, participant_id, goal, week_number = context
        draft_id = _draft_id(participant_id, week_number)
        self.drafts.create_draft(
            draft_id=draft_id,
            telegram_id=user.telegram_id,
            participant_id=participant_id,
            goal_id=_string_value(goal.get("goal_id")),
            week_number=week_number,
            occurred_at=_occurred_at(now),
        )
        return self._send(
            user,
            text="Отправь инсайт текстом. Когда закончишь — нажми ✅ Инсайт готов.",
            buttons=build_insight_text_buttons(),
        )

    def add_text_message(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context
        if self.drafts.get_active_draft(user.telegram_id) is None:
            raise KeyError(f"Active insight draft not found for telegram_id={user.telegram_id}")

        self.drafts.append_text_message(
            user.telegram_id,
            text,
            occurred_at=_occurred_at(now),
            telegram_message_id=telegram_message_id,
        )
        return self._send(user, text="Текст добавлен. Можно отправить ещё или нажать ✅ Инсайт готов.")

    def add_voice_message(
        self,
        user: TelegramUserContext,
        *,
        telegram_file_id: str,
        duration_seconds: int,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context
        if self.drafts.get_active_draft(user.telegram_id) is None:
            raise KeyError(f"Active insight draft not found for telegram_id={user.telegram_id}")
        if self.voice_messages is None:
            return self.reject_voice_message(user, now=now)

        result = self.voice_messages.handle_voice(
            VoiceMessageInput(
                user=user,
                telegram_file_id=telegram_file_id,
                duration_seconds=duration_seconds,
                telegram_message_id=telegram_message_id,
                now=now,
            )
        )
        return self._send(user, text=result.text)

    def request_title(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            recent = self.drafts.get_recent_saved_draft(user.telegram_id)
            if recent is not None:
                return self._send(user, text=INSIGHT_DUPLICATE_TEXT)
            raise KeyError(f"Active insight draft not found for telegram_id={user.telegram_id}")
        if not draft.insight_text.strip():
            return self._send(user, text=INSIGHT_EMPTY_TEXT)
        self.drafts.request_title(user.telegram_id, occurred_at=_occurred_at(now))
        return self._send(user, text=INSIGHT_TITLE_PROMPT_TEXT)

    def set_title_and_save(
        self,
        user: TelegramUserContext,
        title: str,
        *,
        now: datetime,
    ) -> FlowResponse:
        if len(title) > 120:
            return self._send(user, text=INSIGHT_TITLE_TOO_LONG_TEXT)
        return self._save(user, title=title, now=now)

    def skip_title_and_save(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            recent = self.drafts.get_recent_saved_draft(user.telegram_id)
            if recent is not None:
                return self._send(user, text=INSIGHT_DUPLICATE_TEXT)
            raise KeyError(f"Active insight draft not found for telegram_id={user.telegram_id}")
        return self._save(user, title="", now=now)

    def cancel(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        context = self._resolve_participant(user, now=now)
        if isinstance(context, FlowResponse):
            return context
        participant = context
        self.drafts.clear_draft(user.telegram_id)
        return self._send(
            user,
            text=_menu_text(build_role_menu(_role(participant))),
            menu_items=build_role_menu(_role(participant)),
        )

    def reject_voice_message(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        return self._send(user, text=INSIGHT_VOICE_NOT_AVAILABLE_TEXT)

    def list_insights(
        self,
        user: TelegramUserContext,
        *,
        page_index: int,
        now: datetime,
    ) -> FlowResponse:
        participant = self._resolve_participant(user, now=now)
        if isinstance(participant, FlowResponse):
            return participant

        participant_id = _string_value(participant.get("participant_id"))
        rows = sorted(
            self.sheets.list_insights_for_participant(participant_id),
            key=lambda row: (
                str(row.get("insight_date") or ""),
                str(row.get("created_at") or ""),
            ),
            reverse=True,
        )
        page_size = 10
        bounded_page = _bounded_page_index(page_index, total_count=len(rows), page_size=page_size)
        start = bounded_page * page_size
        items = tuple(
            _insight_item_from_row(row, position=start + offset + 1)
            for offset, row in enumerate(rows[start : start + page_size])
        )
        page = InsightPage(
            items=items,
            page_index=bounded_page,
            page_size=page_size,
            total_count=len(rows),
        )
        return self._send(
            user,
            text=format_insight_page(page),
            parse_mode=TELEGRAM_HTML_PARSE_MODE,
        )

    def get_full_text(
        self,
        user: TelegramUserContext,
        *,
        insight_id: str,
        now: datetime,
    ) -> FlowResponse:
        participant = self._resolve_participant(user, now=now)
        if isinstance(participant, FlowResponse):
            return participant

        participant_id = _string_value(participant.get("participant_id"))
        rows = sorted(
            self.sheets.list_insights_for_participant(participant_id),
            key=lambda item: (
                str(item.get("insight_date") or ""),
                str(item.get("created_at") or ""),
            ),
            reverse=True,
        )
        row_with_position = next(
            (
                (row, index)
                for index, row in enumerate(rows, start=1)
                if _string_value(row.get("insight_id")) == insight_id
            ),
            None,
        )
        if row_with_position is None:
            self.notification_router.send(
                category=NotificationCategory.TECHNICAL_ERROR,
                text=(
                    "missing_insight_callback "
                    f"telegram_id={user.telegram_id} "
                    f"participant_id={participant_id} "
                    f"insight_id={insight_id} "
                    f"occurred_at={_occurred_at(now)}"
                ),
                recipients=(),
            )
            return self._send(user, text=INSIGHT_MISSING_TEXT)

        row, position = row_with_position
        return self._send(
            user,
            text=format_full_insight_text(_insight_item_from_row(row, position=position)),
            parse_mode=TELEGRAM_HTML_PARSE_MODE,
        )

    def _save(self, user: TelegramUserContext, *, title: str, now: datetime) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        participant, participant_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            recent = self.drafts.get_recent_saved_draft(user.telegram_id)
            if recent is not None:
                return self._send(user, text=INSIGHT_DUPLICATE_TEXT)
            raise KeyError(f"Active insight draft not found for telegram_id={user.telegram_id}")
        if not draft.insight_text.strip():
            return self._send(user, text=INSIGHT_EMPTY_TEXT)

        submitted_at = _occurred_at(now)
        insight_id = _insight_id(draft.draft_id)
        self.drafts.set_title(user.telegram_id, title, occurred_at=submitted_at)
        self.sheets.append_insight(
            {
                "insight_id": insight_id,
                "participant_id": participant_id,
                "goal_id": _string_value(goal.get("goal_id")),
                "week_number": week_number,
                "insight_scope": "current_week",
                "insight_title": title,
                "insight_date": now.astimezone().date().isoformat(),
                "insight_text": draft.insight_text,
                "transcription_text": _voice_transcription_text(draft),
                "audio_file_path": _voice_audio_file_path(draft),
                "audio_deleted_at": "",
                "created_by_id": participant_id,
                "created_by_role": _created_by_role(participant),
                "created_at": submitted_at,
            }
        )
        self.drafts.mark_saved(user.telegram_id, saved_insight_id=insight_id, saved_at=submitted_at)
        menu_items = build_role_menu(_role(participant))
        return self._send(user, text=INSIGHT_SUCCESS_TEXT, menu_items=menu_items)

    def _resolve_context(
        self,
        user: TelegramUserContext,
        *,
        now: datetime,
    ) -> tuple[SheetRow, str, SheetRow, int] | FlowResponse:
        participant = self._resolve_participant(user, now=now)
        if isinstance(participant, FlowResponse):
            return participant

        participant_id = _string_value(participant.get("participant_id"))
        goal = self.sheets.get_active_goal(participant_id)
        if goal is None:
            return self._handle_missing_goal(user, participant=participant, occurred_at=_occurred_at(now))

        return participant, participant_id, goal, current_challenge_week_number(now)

    def _resolve_participant(
        self,
        user: TelegramUserContext,
        *,
        now: datetime,
    ) -> SheetRow | FlowResponse:
        participant = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        occurred_at = _occurred_at(now)
        if participant is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)

        if not _consent_is_given(participant):
            return self._send(user, text=CONSENT_TEXT, buttons=(CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON))

        return participant

    def _handle_missing_goal(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        occurred_at: str,
    ) -> FlowResponse:
        response = self._send(user, text=INSIGHT_MISSING_ACTIVE_GOAL_TEXT)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_missing_data_error_text(user, participant, "active_goal", occurred_at),
            recipients=(),
        )
        return response

    def _handle_unknown_user(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        response = self._send(user, text=UNKNOWN_USER_TEXT)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_unknown_user_error_text(user, occurred_at),
            recipients=(),
        )
        return response

    def _send(
        self,
        user: TelegramUserContext,
        *,
        text: str,
        buttons: tuple[str, ...] = (),
        menu_items: tuple = (),
        parse_mode: str | None = None,
    ) -> FlowResponse:
        response = FlowResponse(
            chat_id=user.chat_id,
            text=text,
            buttons=buttons,
            menu_items=menu_items,
            parse_mode=parse_mode,
        )
        self.main_bot.send_message(
            chat_id=user.chat_id,
            text=text,
            buttons=buttons,
            menu_items=menu_items,
            parse_mode=parse_mode,
        )
        return response


def _draft_id(participant_id: str, week_number: int) -> str:
    return f"insight-{participant_id}-{week_number:02d}-{uuid4().hex}"


def _insight_id(draft_id: str) -> str:
    prefix = "insight-"
    if draft_id.startswith(prefix):
        return f"I-{draft_id[len(prefix):]}"
    return f"I-{draft_id}"


def _created_by_role(participant: SheetRow) -> str:
    role = _role(participant)
    return "captain" if role == "captain" else "participant"


def _role(participant: SheetRow) -> str:
    value = participant.get("role")
    return value if isinstance(value, str) else "participant"


def _menu_text(menu_items: tuple) -> str:
    return "\n".join(item.label for item in menu_items)


def _voice_transcription_text(draft) -> str:
    return "\n".join(
        attachment.transcription_text for attachment in draft.voice_attachments if attachment.transcription_text
    )


def _voice_audio_file_path(draft) -> str:
    return "\n".join(attachment.local_file_path for attachment in draft.voice_attachments)


def _consent_is_given(participant: SheetRow) -> bool:
    value = participant.get("consent_given")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "да"}
    return False


def _occurred_at(value: datetime) -> str:
    return value.isoformat()


def _unknown_user_error_text(user: TelegramUserContext, occurred_at: str) -> str:
    username = user.username if user.username else "unknown"
    return (
        "unknown_telegram_user "
        f"telegram_id={user.telegram_id} "
        f"username={username} "
        f"occurred_at={occurred_at}"
    )


def _missing_data_error_text(
    user: TelegramUserContext,
    participant: SheetRow,
    missing_type: str,
    occurred_at: str,
) -> str:
    participant_id = participant.get("participant_id") if participant.get("participant_id") else "unknown"
    return (
        "missing_required_data "
        f"type={missing_type} "
        f"telegram_id={user.telegram_id} "
        f"participant_id={participant_id} "
        f"occurred_at={occurred_at}"
    )


def _string_value(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("string value is required")
    return value


def _bounded_page_index(page_index: int, *, total_count: int, page_size: int) -> int:
    if total_count <= 0:
        return 0
    last_page = (total_count - 1) // page_size
    return max(0, min(page_index, last_page))


def _insight_item_from_row(row: SheetRow, *, position: int = 1) -> InsightListItem:
    text = str(row.get("insight_text") or row.get("transcription_text") or "")
    title = str(row.get("insight_title") or "").strip() or format_untitled_insight_title(position)
    return InsightListItem(
        insight_id=_string_value(row.get("insight_id")),
        insight_date=str(row.get("insight_date") or ""),
        title=title,
        text_preview=text,
        full_text=text,
    )


def _read_full_buttons(items: tuple[InsightListItem, ...]) -> tuple[TelegramInlineButton, ...]:
    return tuple(
        TelegramInlineButton(
            text=f"{INSIGHT_READ_FULL_TEXT}: {item.title or 'инсайт'}",
            callback_data=f"{INSIGHT_FULL_TEXT_CALLBACK_PREFIX}{item.insight_id}",
        )
        for item in items
    )

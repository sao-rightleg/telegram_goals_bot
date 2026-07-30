"""Telegram update parsing and runtime dispatch."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.bot.menus import (
    CAPTAIN_DONE_CALLBACK,
    CAPTAIN_MANUAL_REPORT_CALLBACK_PREFIX,
    CAPTAIN_STATUS_CALLBACK_PREFIX,
    CAPTAIN_STEPS_CALLBACK_PREFIX,
    CAPTAIN_TEAM_CALLBACK,
    CONSENT_ACCEPT_CALLBACK,
    INSIGHT_ADD_CALLBACK,
    INSIGHT_CANCEL_CALLBACK,
    INSIGHT_DONE_CALLBACK,
    INSIGHT_FULL_TEXT_CALLBACK_PREFIX,
    INSIGHT_LIST_CALLBACK_PREFIX,
    INSIGHT_MENU_CALLBACK,
    INSIGHT_SKIP_TITLE_CALLBACK,
    MENU_CALLBACK_PREFIX,
    WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX,
    WEEKLY_REPORT_DONE_CALLBACK,
    WEEKLY_REPORT_EDIT_STEP_CALLBACK_PREFIX,
    WEEKLY_REPORT_START_CALLBACK,
    WEEKLY_REPORT_START_STEP_CALLBACK_PREFIX,
    WEEKLY_REPORT_STATUS_CALLBACK_PREFIX,
    WEEKLY_REPORT_STEPS_CALLBACK_PREFIX,
    MenuAction,
)
from app.bot.messages import MESSAGE_WITHOUT_FLOW_TEXT, NOT_AVAILABLE_TEXT
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.weekly_report_models import WeeklyReportStatus
from app.storage.dialog_state import DialogStateRepository


def _default_now() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE_NAME))


class TelegramUpdateParseError(ValueError):
    """Raised when a Telegram update cannot be safely routed."""


class TelegramCallbackError(ValueError):
    """Raised when callback data is malformed or unsupported."""


@dataclass(frozen=True)
class TelegramMessage:
    message_id: int
    chat_id: str
    telegram_id: int
    username: str | None = None
    text: str | None = None
    command: str | None = None
    voice_file_id: str | None = None
    voice_duration_seconds: int | None = None


@dataclass(frozen=True)
class TelegramCallback:
    callback_query_id: str
    message_id: int | None
    chat_id: str
    telegram_id: int
    username: str | None
    data: str


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    message: TelegramMessage | None = None
    callback: TelegramCallback | None = None


@dataclass(frozen=True)
class TelegramUpdateDispatcher:
    participant_service: object
    weekly_report_service: object
    insight_service: object
    captain_service: object
    dialog_states: DialogStateRepository
    notification_router: NotificationRouter
    now_provider: Callable[[], datetime] = _default_now

    def dispatch_update(self, payload: Mapping[str, object]) -> FlowResponse | None:
        update = parse_telegram_update(payload)
        now = self.now_provider()

        if update.message is not None:
            return self._dispatch_message(update.message, now=now)
        if update.callback is not None:
            try:
                return self._dispatch_callback(update.callback, now=now)
            except TelegramCallbackError as exc:
                self._notify_malformed_callback(update.callback, now=now, error=exc)
                return FlowResponse(chat_id=update.callback.chat_id, text=NOT_AVAILABLE_TEXT)
        return None

    def _dispatch_message(self, message: TelegramMessage, *, now: datetime) -> FlowResponse | None:
        user = _user_from_message(message)
        if message.command in {"/start", "/menu"}:
            return self.participant_service.handle_start(user, occurred_at=now.isoformat())

        if message.voice_file_id is not None and message.voice_duration_seconds is not None:
            return self._dispatch_voice(message, user=user, now=now)

        if message.text is not None and message.text.strip():
            return self._dispatch_text(message, user=user, now=now)

        return None

    def _dispatch_text(
        self,
        message: TelegramMessage,
        *,
        user: TelegramUserContext,
        now: datetime,
    ) -> FlowResponse | None:
        state = self.dialog_states.get(user.telegram_id)
        if state is None:
            return self._send_message_without_flow(user)

        if state.flow == "weekly_report":
            return self.weekly_report_service.add_text_message(
                user,
                message.text or "",
                now=now,
                telegram_message_id=message.message_id,
            )
        if state.flow == "insight":
            if state.step == "awaiting_title":
                return self.insight_service.set_title_and_save(
                    user,
                    message.text or "",
                    now=now,
                )
            return self.insight_service.add_text_message(
                user,
                message.text or "",
                now=now,
                telegram_message_id=message.message_id,
            )
        if state.flow == "captain_manual":
            return self.captain_service.add_text_message(
                user,
                message.text or "",
                now=now,
                telegram_message_id=message.message_id,
            )

        return None

    def _send_message_without_flow(self, user: TelegramUserContext) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=MESSAGE_WITHOUT_FLOW_TEXT)
        self.notification_router.main_bot.send_message(chat_id=user.chat_id, text=response.text)
        return response

    def _dispatch_voice(
        self,
        message: TelegramMessage,
        *,
        user: TelegramUserContext,
        now: datetime,
    ) -> FlowResponse | None:
        state = self.dialog_states.get(user.telegram_id)
        if state is None:
            return None

        if state.flow == "weekly_report":
            return self.weekly_report_service.add_voice_message(
                user,
                telegram_file_id=message.voice_file_id or "",
                duration_seconds=message.voice_duration_seconds or 0,
                now=now,
                telegram_message_id=message.message_id,
            )
        if state.flow == "insight":
            return self.insight_service.add_voice_message(
                user,
                telegram_file_id=message.voice_file_id or "",
                duration_seconds=message.voice_duration_seconds or 0,
                now=now,
                telegram_message_id=message.message_id,
            )

        return None

    def _dispatch_callback(self, callback: TelegramCallback, *, now: datetime) -> FlowResponse | None:
        user = _user_from_callback(callback)
        data = callback.data

        if data == CONSENT_ACCEPT_CALLBACK:
            return self.participant_service.accept_consent(user, consent_given_at=now.isoformat())
        if data.startswith(WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX):
            return self.participant_service.select_weekly_focus(
                user,
                step_id=_required_suffix(data, WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX),
                occurred_at=now.isoformat(),
            )
        if data.startswith(MENU_CALLBACK_PREFIX):
            return self._dispatch_menu_callback(user, data, now=now)

        if data == WEEKLY_REPORT_START_CALLBACK:
            return self.weekly_report_service.start_report(user, now=now)
        if data.startswith(WEEKLY_REPORT_EDIT_STEP_CALLBACK_PREFIX):
            return self.weekly_report_service.start_edit_report_for_step(
                user,
                step_id=_required_suffix(data, WEEKLY_REPORT_EDIT_STEP_CALLBACK_PREFIX),
                now=now,
            )
        if data.startswith(WEEKLY_REPORT_START_STEP_CALLBACK_PREFIX):
            return self.weekly_report_service.start_report_for_step(
                user,
                step_id=_required_suffix(data, WEEKLY_REPORT_START_STEP_CALLBACK_PREFIX),
                now=now,
            )
        if data.startswith(WEEKLY_REPORT_STATUS_CALLBACK_PREFIX):
            status = _status_from_callback(data, WEEKLY_REPORT_STATUS_CALLBACK_PREFIX)
            return self.weekly_report_service.select_status(user, status, now=now)
        if data.startswith(WEEKLY_REPORT_STEPS_CALLBACK_PREFIX):
            step_ids = _csv_suffix(data, WEEKLY_REPORT_STEPS_CALLBACK_PREFIX)
            return self.weekly_report_service.select_steps(user, step_ids, now=now)
        if data == WEEKLY_REPORT_DONE_CALLBACK:
            return self.weekly_report_service.finalize_report(user, now=now)

        if data == INSIGHT_MENU_CALLBACK:
            return self.insight_service.show_menu(user, now=now)
        if data == INSIGHT_ADD_CALLBACK:
            return self.insight_service.start_add(user, now=now)
        if data.startswith(INSIGHT_LIST_CALLBACK_PREFIX):
            return self.insight_service.list_insights(
                user,
                page_index=_int_suffix(data, INSIGHT_LIST_CALLBACK_PREFIX),
                now=now,
            )
        if data.startswith(INSIGHT_FULL_TEXT_CALLBACK_PREFIX):
            return self.insight_service.get_full_text(
                user,
                insight_id=_required_suffix(data, INSIGHT_FULL_TEXT_CALLBACK_PREFIX),
                now=now,
            )
        if data == INSIGHT_DONE_CALLBACK:
            return self.insight_service.request_title(user, now=now)
        if data == INSIGHT_SKIP_TITLE_CALLBACK:
            return self.insight_service.skip_title_and_save(user, now=now)
        if data == INSIGHT_CANCEL_CALLBACK:
            return self.insight_service.cancel(user, now=now)

        if data == CAPTAIN_TEAM_CALLBACK:
            return self.captain_service.show_team(user, occurred_at=now.isoformat())
        if data.startswith(CAPTAIN_MANUAL_REPORT_CALLBACK_PREFIX):
            return self.captain_service.start_manual_report(
                user,
                _required_suffix(data, CAPTAIN_MANUAL_REPORT_CALLBACK_PREFIX),
                now=now,
            )
        if data.startswith(CAPTAIN_STATUS_CALLBACK_PREFIX):
            status = _status_from_callback(data, CAPTAIN_STATUS_CALLBACK_PREFIX)
            return self.captain_service.select_status(user, status, now=now)
        if data.startswith(CAPTAIN_STEPS_CALLBACK_PREFIX):
            step_ids = _csv_suffix(data, CAPTAIN_STEPS_CALLBACK_PREFIX)
            return self.captain_service.select_steps(user, step_ids, now=now)
        if data == CAPTAIN_DONE_CALLBACK:
            return self.captain_service.finalize_manual_report(user, now=now)

        raise TelegramCallbackError("unknown callback prefix")

    def _dispatch_menu_callback(
        self,
        user: TelegramUserContext,
        data: str,
        *,
        now: datetime,
    ) -> FlowResponse:
        action_value = _required_suffix(data, MENU_CALLBACK_PREFIX)
        try:
            action = MenuAction(action_value)
        except ValueError as exc:
            raise TelegramCallbackError("unknown menu action") from exc

        if action is MenuAction.START_WEEKLY_REPORT:
            return self.weekly_report_service.start_report(user, now=now)
        if action is MenuAction.VIEW_TEAM:
            return self.captain_service.show_team(user, occurred_at=now.isoformat())
        if action is MenuAction.CAPTAIN_MANUAL_REPORT:
            raise TelegramCallbackError("captain manual report callback requires participant id")
        return self.participant_service.handle_menu_action(user, action, occurred_at=now.isoformat())

    def _notify_malformed_callback(
        self,
        callback: TelegramCallback,
        *,
        now: datetime,
        error: Exception,
    ) -> None:
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=(
                "malformed_callback "
                f"telegram_id={callback.telegram_id} "
                f"callback_query_id={callback.callback_query_id} "
                f"error_type={type(error).__name__} "
                f"occurred_at={now.isoformat()}"
            ),
            recipients=(),
        )


def parse_telegram_update(payload: Mapping[str, object]) -> TelegramUpdate:
    update_id = _required_int(payload.get("update_id"), field_name="update_id")
    message_payload = payload.get("message")
    if isinstance(message_payload, Mapping):
        return TelegramUpdate(update_id=update_id, message=_parse_message(message_payload))

    callback_payload = payload.get("callback_query")
    if isinstance(callback_payload, Mapping):
        return TelegramUpdate(update_id=update_id, callback=_parse_callback(callback_payload))

    return TelegramUpdate(update_id=update_id)


def _parse_message(payload: Mapping[str, object]) -> TelegramMessage:
    message_id = _required_int(payload.get("message_id"), field_name="message.message_id")
    user_payload = _required_mapping(payload.get("from"), field_name="message.from")
    chat_payload = _required_mapping(payload.get("chat"), field_name="message.chat")
    text = payload.get("text") if isinstance(payload.get("text"), str) else None
    command = _command_from_text(text)

    voice = payload.get("voice")
    voice_file_id: str | None = None
    voice_duration_seconds: int | None = None
    if isinstance(voice, Mapping):
        raw_file_id = voice.get("file_id")
        if isinstance(raw_file_id, str) and raw_file_id:
            voice_file_id = raw_file_id
        voice_duration_seconds = _optional_int(voice.get("duration"))

    return TelegramMessage(
        message_id=message_id,
        chat_id=str(_required_scalar(chat_payload.get("id"), field_name="message.chat.id")),
        telegram_id=_required_int(user_payload.get("id"), field_name="message.from.id"),
        username=_optional_string(user_payload.get("username")),
        text=text,
        command=command,
        voice_file_id=voice_file_id,
        voice_duration_seconds=voice_duration_seconds,
    )


def _parse_callback(payload: Mapping[str, object]) -> TelegramCallback:
    user_payload = _required_mapping(payload.get("from"), field_name="callback_query.from")
    message_payload = payload.get("message")
    chat_id = str(_required_int(user_payload.get("id"), field_name="callback_query.from.id"))
    message_id: int | None = None
    if isinstance(message_payload, Mapping):
        message_id = _optional_int(message_payload.get("message_id"))
        chat = message_payload.get("chat")
        if isinstance(chat, Mapping):
            chat_id = str(_required_scalar(chat.get("id"), field_name="callback_query.message.chat.id"))

    data = payload.get("data")
    if not isinstance(data, str) or not data:
        raise TelegramUpdateParseError("callback_query.data is required")

    return TelegramCallback(
        callback_query_id=str(_required_scalar(payload.get("id"), field_name="callback_query.id")),
        message_id=message_id,
        chat_id=chat_id,
        telegram_id=_required_int(user_payload.get("id"), field_name="callback_query.from.id"),
        username=_optional_string(user_payload.get("username")),
        data=data,
    )


def _user_from_message(message: TelegramMessage) -> TelegramUserContext:
    return TelegramUserContext(
        telegram_id=message.telegram_id,
        chat_id=message.chat_id,
        username=message.username,
    )


def _user_from_callback(callback: TelegramCallback) -> TelegramUserContext:
    return TelegramUserContext(
        telegram_id=callback.telegram_id,
        chat_id=callback.chat_id,
        username=callback.username,
    )


def _command_from_text(text: str | None) -> str | None:
    if text is None:
        return None
    first_token = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    if not first_token.startswith("/"):
        return None
    return first_token.split("@", 1)[0]


def _required_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TelegramUpdateParseError(f"{field_name} is required")
    return value


def _required_scalar(value: object, *, field_name: str) -> object:
    if value is None or isinstance(value, (Mapping, list, tuple)):
        raise TelegramUpdateParseError(f"{field_name} is required")
    return value


def _required_int(value: object, *, field_name: str) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        raise TelegramUpdateParseError(f"{field_name} must be an integer")
    return parsed


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _status_from_callback(data: str, prefix: str) -> WeeklyReportStatus:
    status_code = _required_suffix(data, prefix)
    for status in WeeklyReportStatus:
        if status.code == status_code:
            return status
    raise TelegramCallbackError("unknown weekly status")


def _csv_suffix(data: str, prefix: str) -> list[str]:
    suffix = _required_suffix(data, prefix)
    values = [value for value in suffix.split(",") if value]
    if not values:
        raise TelegramCallbackError("callback list is empty")
    return values


def _int_suffix(data: str, prefix: str) -> int:
    suffix = _required_suffix(data, prefix)
    try:
        return int(suffix)
    except ValueError as exc:
        raise TelegramCallbackError("callback integer is invalid") from exc


def _required_suffix(data: str, prefix: str) -> str:
    suffix = data[len(prefix) :]
    if not suffix:
        raise TelegramCallbackError("callback suffix is missing")
    return suffix

"""Authorized manual broadcasts from RUPOR control bot to active participants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from time import sleep
from typing import Callable
from uuid import uuid4

from app.bot.clients import BotClient, TelegramInlineButton
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.rupor import RuporDraft, RuporRepository


SEND_PREFIX = "rupor:send:"
CANCEL_PREFIX = "rupor:cancel:"
MAX_BROADCAST_LENGTH = 3000
DRAFT_RETENTION_DAYS = 7
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuporService:
    sheets: SheetsGateway
    rupor_bot: BotClient
    delivery_bot: BotClient
    notification_router: NotificationRouter
    repository: RuporRepository
    allowed_telegram_ids: frozenset[int]
    delivery_pause_seconds: float = 0.05
    sleep_fn: Callable[[float], None] = sleep

    def resume_incomplete(self, *, occurred_at: str) -> int:
        drafts = self.repository.list_sending_drafts()
        for draft in drafts:
            self._audit(
                draft.operator_telegram_id, draft.broadcast_id, "startup_recovery", occurred_at
            )
            self._deliver(
                draft=draft,
                operator_chat_id=str(draft.operator_telegram_id),
                occurred_at=occurred_at,
            )
        return len(drafts)

    def handle_start(
        self, *, telegram_id: int, chat_id: str, occurred_at: str | None = None
    ) -> FlowResponse:
        denied = self._access_denial(telegram_id, chat_id, occurred_at=occurred_at)
        if denied is not None:
            return denied
        draft = self.repository.get_draft(telegram_id)
        if draft is not None and draft.status == "sending" and draft.message_text:
            when = occurred_at or draft.updated_at
            self._audit(telegram_id, draft.broadcast_id, "recovery_started", when)
            self._reply(chat_id, "Продолжаю незавершённую рассылку.")
            self._deliver(draft=draft, operator_chat_id=chat_id, occurred_at=when)
            return FlowResponse(chat_id=chat_id, text="Продолжаю незавершённую рассылку.")
        return self._reply(
            chat_id,
            "Отправь текст сообщения. Я покажу предпросмотр и попрошу подтверждение.",
        )

    def receive_text(
        self, *, telegram_id: int, chat_id: str, text: str, occurred_at: str
    ) -> FlowResponse:
        self._expire_old_drafts(occurred_at)
        denied = self._access_denial(telegram_id, chat_id, occurred_at=occurred_at)
        if denied is not None:
            return denied
        normalized = text.strip()
        if not normalized or len(normalized) > MAX_BROADCAST_LENGTH:
            return self._reply(chat_id, f"Текст должен содержать от 1 до {MAX_BROADCAST_LENGTH} символов.")
        current = self.repository.get_draft(telegram_id)
        if current is not None and current.status == "sending":
            return self._reply(chat_id, "Предыдущая рассылка ещё выполняется. Отправь /start для продолжения.")
        recipients = _eligible_recipients(self.sheets.list_participants())
        draft = RuporDraft(
            operator_telegram_id=telegram_id,
            broadcast_id=uuid4().hex,
            message_text=normalized,
            status="draft",
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        self.repository.save_draft(draft)
        self._audit(telegram_id, draft.broadcast_id, "created", occurred_at)
        return self._preview(chat_id, draft, recipient_count=len(recipients))

    def handle_callback(
        self, *, telegram_id: int, chat_id: str, callback_data: str, occurred_at: str
    ) -> FlowResponse:
        denied = self._access_denial(telegram_id, chat_id, occurred_at=occurred_at)
        if denied is not None:
            return denied
        if callback_data.startswith(CANCEL_PREFIX):
            return self._cancel(
                telegram_id, chat_id, callback_data.removeprefix(CANCEL_PREFIX), occurred_at
            )
        if callback_data.startswith(SEND_PREFIX):
            return self._confirm_or_resume(
                telegram_id, chat_id, callback_data.removeprefix(SEND_PREFIX), occurred_at
            )
        return self._reply(chat_id, "Кнопка устарела. Отправь сообщение заново.")

    def _confirm_or_resume(
        self, telegram_id: int, chat_id: str, broadcast_id: str, occurred_at: str
    ) -> FlowResponse:
        draft = self.repository.get_draft(telegram_id)
        if draft is None or draft.broadcast_id != broadcast_id or draft.message_text is None:
            return self._reply(chat_id, "Эта рассылка уже обработана.")
        if draft.status == "draft":
            recipients = _eligible_recipients(self.sheets.list_participants())
            for recipient in recipients:
                self.repository.ensure_delivery(
                    broadcast_id, _participant_id(recipient), updated_at=occurred_at
                )
            if not self.repository.claim_broadcast(
                telegram_id, broadcast_id=broadcast_id, updated_at=occurred_at
            ):
                return self._reply(chat_id, "Эта рассылка уже обрабатывается.")
            draft = self.repository.get_draft(telegram_id) or draft
            try:
                self._audit(telegram_id, broadcast_id, "confirmed", occurred_at)
            except Exception:
                logger.exception("failed to persist RUPOR confirmation audit")
            response = FlowResponse(
                chat_id=chat_id,
                text=f"Рассылка запущена. Получателей: {len(recipients)}.",
            )
        elif draft.status != "sending":
            return self._reply(chat_id, "Эта рассылка уже обработана.")
        else:
            response = FlowResponse(
                chat_id=chat_id,
                text="Продолжаю незавершённую рассылку.",
            )
        try:
            self._reply(chat_id, response.text)
        finally:
            self._deliver(draft=draft, operator_chat_id=chat_id, occurred_at=occurred_at)
        return response

    def _deliver(self, *, draft: RuporDraft, operator_chat_id: str, occurred_at: str) -> None:
        for participant_id in self.repository.list_delivery_participant_ids(draft.broadcast_id):
            status = self.repository.delivery_status(draft.broadcast_id, participant_id)
            if status in {"sent", "skipped", "unknown"}:
                continue
            participant = self.sheets.get_participant(participant_id)
            if not _recipient_is_eligible(participant):
                self.repository.mark_delivery(
                    draft.broadcast_id, participant_id, status="skipped",
                    error_type=None, updated_at=occurred_at,
                )
                continue
            self._send_one(draft, participant, occurred_at=occurred_at)
            if self.delivery_pause_seconds > 0:
                self.sleep_fn(self.delivery_pause_seconds)
        self._finish_or_report(draft, operator_chat_id=operator_chat_id, occurred_at=occurred_at)

    def _send_one(self, draft: RuporDraft, participant: SheetRow, *, occurred_at: str) -> None:
        participant_id = _participant_id(participant)
        # Persist an ambiguous state before crossing the Telegram boundary. If the
        # process loses the API response or the final SQLite write fails, an
        # automatic retry could duplicate a message already accepted by Telegram.
        self.repository.mark_delivery(
            draft.broadcast_id,
            participant_id,
            status="unknown",
            error_type=None,
            updated_at=occurred_at,
        )
        try:
            self.delivery_bot.send_message(
                chat_id=str(participant["telegram_id"]), text=draft.message_text or ""
            )
        except Exception as exc:
            self.repository.mark_delivery(
                draft.broadcast_id, participant_id, status="unknown",
                error_type=type(exc).__name__, updated_at=occurred_at,
            )
            self._notify_delivery_failure(draft.broadcast_id, participant_id, exc)
            return
        try:
            self.repository.mark_delivery(
                draft.broadcast_id, participant_id, status="sent",
                error_type=None, updated_at=occurred_at,
            )
        except Exception as exc:
            self._notify_delivery_failure(draft.broadcast_id, participant_id, exc)

    def _finish_or_report(
        self, draft: RuporDraft, *, operator_chat_id: str, occurred_at: str
    ) -> None:
        counts = self.repository.delivery_counts(draft.broadcast_id)
        if counts["failed"] == 0 and counts["pending"] == 0 and counts["unknown"] == 0:
            self.repository.finish_broadcast(
                draft.operator_telegram_id,
                broadcast_id=draft.broadcast_id,
                updated_at=occurred_at,
            )
            self._audit(draft.operator_telegram_id, draft.broadcast_id, "completed", occurred_at)
            suffix = "" if counts["skipped"] == 0 else f" Пропущено: {counts['skipped']}."
        else:
            self._audit(draft.operator_telegram_id, draft.broadcast_id, "retry_required", occurred_at)
            suffix = (
                f" Неопределённый статус: {counts['unknown']}. "
                "Автоповтор отключён, чтобы не отправить сообщение дважды."
            )
        self._reply(
            operator_chat_id,
            f"Рассылка завершена. Доставлено: {counts['sent']}. Ошибок: {counts['failed']}.{suffix}",
        )

    def _notify_delivery_failure(
        self, broadcast_id: str, participant_id: str, error: Exception
    ) -> None:
        try:
            self.notification_router.send(
                category=NotificationCategory.TECHNICAL_ERROR,
                text=(
                    "rupor_delivery_failed "
                    f"broadcast_id={broadcast_id} participant_id={participant_id} "
                    f"error_type={type(error).__name__}"
                ),
                recipients=(),
            )
        except Exception as notify_error:
            logger.exception(
                "failed to send RUPOR delivery alert",
                extra={
                    "broadcast_id": broadcast_id,
                    "participant_id": participant_id,
                    "error_type": type(notify_error).__name__,
                },
            )

    def _cancel(
        self, telegram_id: int, chat_id: str, broadcast_id: str, occurred_at: str
    ) -> FlowResponse:
        if not self.repository.cancel_broadcast(
            telegram_id, broadcast_id=broadcast_id, updated_at=occurred_at
        ):
            return self._reply(chat_id, "Эта рассылка уже обработана.")
        self._audit(telegram_id, broadcast_id, "cancelled", occurred_at)
        return self._reply(chat_id, "Рассылка отменена.")

    def _access_denial(
        self, telegram_id: int, chat_id: str, *, occurred_at: str | None
    ) -> FlowResponse | None:
        if telegram_id not in self.allowed_telegram_ids:
            # Ignore untrusted senders without a response or durable audit row.
            # Otherwise an arbitrary Telegram account could amplify traffic and
            # grow the technical database without bounds.
            return FlowResponse(chat_id=chat_id, text="")
        if chat_id != str(telegram_id):
            if occurred_at:
                self._audit(telegram_id, None, "group_chat_denied", occurred_at)
            return self._reply(chat_id, "Рассылку можно создавать только в личном чате с ботом.")
        return None

    def _preview(self, chat_id: str, draft: RuporDraft, *, recipient_count: int) -> FlowResponse:
        return self._reply(
            chat_id,
            f"Предпросмотр рассылки\n\nПолучателей: {recipient_count}\n\n"
            f"{draft.message_text}\n\nОтправить сообщение?",
            buttons=(
                TelegramInlineButton("Отправить всем", f"{SEND_PREFIX}{draft.broadcast_id}"),
                TelegramInlineButton("Отмена", f"{CANCEL_PREFIX}{draft.broadcast_id}"),
            ),
        )

    def _reply(
        self, chat_id: str, text: str, *, buttons: tuple[TelegramInlineButton, ...] = ()
    ) -> FlowResponse:
        self.rupor_bot.send_message(chat_id=chat_id, text=text, buttons=buttons)
        return FlowResponse(chat_id=chat_id, text=text, buttons=buttons)

    def _audit(
        self, operator_id: int, broadcast_id: str | None, action: str, occurred_at: str
    ) -> None:
        try:
            self.repository.add_audit(
                operator_telegram_id=operator_id,
                broadcast_id=broadcast_id,
                action=action,
                occurred_at=occurred_at,
            )
        except Exception:
            logger.exception("failed to persist RUPOR audit", extra={"action": action})

    def _expire_old_drafts(self, occurred_at: str) -> None:
        cutoff = (datetime.fromisoformat(occurred_at) - timedelta(days=DRAFT_RETENTION_DAYS)).isoformat()
        self.repository.expire_drafts_before(cutoff, occurred_at=occurred_at)


def _eligible_recipients(rows: list[SheetRow]) -> list[SheetRow]:
    recipients: list[SheetRow] = []
    seen_telegram_ids: set[int] = set()
    seen_participant_ids: set[str] = set()
    for row in rows:
        telegram_id = row.get("telegram_id")
        participant_id = str(row.get("participant_id") or "").strip()
        if (
            not _recipient_is_eligible(row)
            or telegram_id in seen_telegram_ids
            or participant_id in seen_participant_ids
        ):
            continue
        seen_telegram_ids.add(telegram_id)
        seen_participant_ids.add(participant_id)
        recipients.append(row)
    return recipients


def _recipient_is_eligible(row: SheetRow | None) -> bool:
    if row is None:
        return False
    telegram_id = row.get("telegram_id")
    return (
        str(row.get("role") or "").strip().lower() == "participant"
        and str(row.get("status") or "").strip().lower() == "active"
        and _strict_true(row.get("consent_given"))
        and isinstance(telegram_id, int)
        and telegram_id > 0
        and bool(str(row.get("participant_id") or "").strip())
    )


def _strict_true(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def _participant_id(row: SheetRow) -> str:
    return str(row["participant_id"])

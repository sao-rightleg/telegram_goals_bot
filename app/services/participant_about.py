"""Private, editable participant descriptions stored as business facts."""

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from collections.abc import Callable

from app.bot.clients import BotClient, TelegramInlineButton
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.sheets.gateway import SheetsGateway, SheetRow
from app.storage.dialog_state import DialogState, DialogStateRepository

from app.domain import MAX_ABOUT_LENGTH

PROFILE_MESSAGE_CHUNK_LENGTH = 1900
PROMPT = (
    "Расскажите о себе:\n"
    "• чем занимаетесь сейчас;\n• чем занимались раньше;\n"
    "• какие у вас ключевые компетенции;\n• чем можете помочь команде.\n\n"
    "Отправьте описание одним текстовым сообщением. До 12 000 символов."
)
CANCEL = (TelegramInlineButton("Отмена", "about:cancel"),)


@dataclass(frozen=True)
class AboutService:
    sheets: SheetsGateway
    states: DialogStateRepository
    bot: BotClient
    notifications: NotificationRouter
    resolve: Callable[[int], SheetRow | None]

    def handle(
        self,
        user: TelegramUserContext,
        action: str,
        *,
        occurred_at: str,
        text: str = "",
    ) -> FlowResponse:
        participant = None
        try:
            participant = self.resolve(user.telegram_id)
            if not self._allowed(user, participant):
                return self._send(
                    user,
                    "Раздел доступен активному участнику в личном чате с ботом после согласия.",
                )
            if action == "text":
                return self._save(user, participant, text, occurred_at)
            if action in {"replace", "append"}:
                self._set_state(user, participant, action, occurred_at)
                prefix = (
                    "Новый текст заменит описание целиком.\n\n"
                    if action == "replace"
                    else "Текст добавится к описанию новым абзацем.\n\n"
                )
                return self._send(user, prefix + PROMPT, CANCEL)
            if action in {"view", "cancel"}:
                self._set_state(user, participant, "view", occurred_at)
                return self._show(user, participant)
            return self._send(user, "Откройте «О себе» через меню.")
        except Exception as error:
            self.notifications.send(
                category=NotificationCategory.TECHNICAL_ERROR,
                text=(
                    f"Participant about operation failed: action={action}; "
                    f"telegram_id={user.telegram_id}; "
                    f"error_category={type(error).__name__}"
                ),
                recipients=(),
            )
            return self._send(
                user, "Не удалось загрузить или сохранить описание. Попробуйте ещё раз."
            )

    def _allowed(self, user: TelegramUserContext, participant: SheetRow | None) -> bool:
        if participant is None or user.chat_id != str(user.telegram_id):
            return False
        consent = participant.get("consent_given")
        return (
            (
                consent is True
                or str(consent).strip().lower() in {"true", "yes", "1", "да"}
            )
            and participant.get("status") == "active"
            and participant.get("role") in {"participant", "captain"}
            and bool(participant.get("flow_id"))
            and bool(participant.get("participant_id"))
        )

    def _save(self, user, participant, text: str, occurred_at: str) -> FlowResponse:
        state = self.states.get(user.telegram_id)
        if (
            state is None
            or state.flow != "participant_about"
            or state.step not in {"replace", "append"}
            or state.participant_id != participant["participant_id"]
            or state.flow_id != participant["flow_id"]
        ):
            return self._send(
                user, "Откройте «О себе» и выберите «Редактировать» или «Дополнить»."
            )
        text = text.strip()
        old = str(participant.get("about_me") or "")
        context = json.loads(state.context_data or "{}")
        if context.get("result_hash") == _text_hash(old):
            self._set_state(user, participant, "view", occurred_at)
            return self._send(user, "Описание сохранено.", self._buttons(old))
        if context.get("base_hash") != _text_hash(old):
            return self._send(
                user,
                "Описание уже изменилось. Откройте «О себе» и начните редактирование заново.",
            )
        updated = old + "\n\n" + text if old and state.step == "append" else text
        if not text or len(updated) > MAX_ABOUT_LENGTH:
            return self._send(
                user,
                "Нужен непустой текст. Общий объём описания — до 12 000 символов.",
                CANCEL,
            )
        context["result_hash"] = _text_hash(updated)
        self.states.upsert(
            replace(state, context_data=json.dumps(context), updated_at=occurred_at)
        )
        self.sheets.update_participant_about(
            str(participant["flow_id"]),
            str(participant["participant_id"]),
            updated,
        )
        self._set_state(user, participant, "view", occurred_at)
        return self._send(user, "Описание сохранено.", self._buttons(updated))

    def _set_state(self, user, participant, step: str, occurred_at: str) -> None:
        self.states.upsert(
            DialogState(
                telegram_id=user.telegram_id,
                participant_id=str(participant["participant_id"]),
                role=str(participant["role"]),
                flow="participant_about",
                step=step,
                flow_id=str(participant["flow_id"]),
                context_data=json.dumps(
                    {"base_hash": _text_hash(str(participant.get("about_me") or ""))}
                ),
                started_at=occurred_at,
                updated_at=occurred_at,
            )
        )

    def _show(self, user, participant) -> FlowResponse:
        text = str(participant.get("about_me") or "")
        content = (
            "О себе\n\n" + text if text else "Описание пока не заполнено.\n\n" + PROMPT
        )
        # 1,900 code points fit Telegram's 4,096 UTF-16-unit limit even with emoji.
        parts = [
            content[index : index + PROFILE_MESSAGE_CHUNK_LENGTH]
            for index in range(0, len(content), PROFILE_MESSAGE_CHUNK_LENGTH)
        ]
        for part in parts[:-1]:
            self._send(user, part)
        return self._send(user, parts[-1], self._buttons(text))

    def _buttons(self, text: str) -> tuple[TelegramInlineButton, ...]:
        if not text:
            return (TelegramInlineButton("Заполнить", "about:replace"),)
        return (
            TelegramInlineButton("Дополнить", "about:append"),
            TelegramInlineButton("Редактировать", "about:replace"),
        )

    def _send(self, user, text: str, buttons=()) -> FlowResponse:
        self.bot.send_message(chat_id=user.chat_id, text=text, buttons=buttons)
        return FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons)


def _text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()

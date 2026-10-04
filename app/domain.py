"""Shared challenge business constants."""

PLANNED_STEP_COUNT = 8

# Sheets numeric cells use doubles; larger integers may silently lose rubles.
MAX_EXACT_WORD_PRICE_RUB = 2**53 - 1


def parse_word_price(text: str) -> int | None:
    value = text.strip().lstrip("0")
    if not value or len(value) > 16 or not value.isascii() or not value.isdecimal():
        return None
    amount = int(value)
    return amount if amount <= MAX_EXACT_WORD_PRICE_RUB else None


def validate_word_price_row(row: dict[str, object]) -> None:
    amount = row.get("word_price_rub")
    if type(amount) is not int or not 0 < amount <= MAX_EXACT_WORD_PRICE_RUB:
        raise ValueError("Word price must be a positive, exactly representable integer")
    if not row.get("flow_id") or not row.get("participant_id"):
        raise ValueError("Word price participant scope is incomplete")

PLANNED_STEP_SYMBOLS = {"closed": "🟩", "partial": "🟦"}


def planned_step_score(status: object) -> float:
    normalized = str(status or "").strip().lower()
    if normalized == "closed":
        return 1.0
    if normalized == "partial":
        return 0.5
    return 0.0


def planned_steps_percent(statuses: list[object] | tuple[object, ...]) -> int:
    score = sum(planned_step_score(status) for status in statuses[:PLANNED_STEP_COUNT])
    return round(min(score, PLANNED_STEP_COUNT) / PLANNED_STEP_COUNT * 100)


def planned_steps_bar(statuses: list[object] | tuple[object, ...]) -> str:
    symbols = [PLANNED_STEP_SYMBOLS.get(str(status or "").strip().lower(), "⬜") for status in statuses]
    return "".join((symbols + ["⬜"] * PLANNED_STEP_COUNT)[:PLANNED_STEP_COUNT])


MAX_ABOUT_LENGTH = 12000

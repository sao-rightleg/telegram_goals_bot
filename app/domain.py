"""Shared challenge business constants."""

PLANNED_STEP_COUNT = 8

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

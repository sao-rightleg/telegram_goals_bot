from app.reports.aggregation import build_all_teams_report
from app.sheets.gateway import FakeSheetsGateway


def test_aggregation_builds_team_report_from_final_sheets_rows() -> None:
    gateway = _gateway()

    report = build_all_teams_report(gateway, week_number=5)
    team = report.teams[0]
    anna = team.participants[0]

    assert report.week_number == 5
    assert report.total_active_count == 2
    assert team.team_name == "Команда А"
    assert team.captain_name == "Ирина Капитан"
    assert team.active_count == 2
    assert team.dropped_count == 1
    assert team.status_distribution == {"green": 1, "blue": 1, "red": 0, "gray": 1}
    assert team.weekly_victory_percent == 75
    assert anna.full_name == "Анна Иванова"
    assert anna.status == "🟩"
    assert anna.progress_bar == "🟩🟦⬜⬜⬜⬜"
    assert anna.progress_percent == 25
    assert anna.goal_title == "Новый контракт"
    assert anna.weekly_focus_step == "Провести встречу"
    assert anna.report_text == "Провела встречу."
    assert anna.transcription_text == "Расшифровка отчёта."
    assert anna.insights == ("Лучше фиксировать договорённости.",)


def test_weekly_victory_percent_excludes_dropped_participants() -> None:
    gateway = _gateway(
        weekly_reports=[
            _weekly_report("WR001", "P001", "green", "🟩", 1),
            _weekly_report("WR002", "P002", "red", "🟥", 0),
            _weekly_report("WR003", "P003", "green", "🟩", 1),
        ]
    )

    team = build_all_teams_report(gateway, week_number=5).teams[0]

    assert team.active_count == 2
    assert team.dropped_count == 1
    assert team.weekly_victory_percent == 50
    assert team.status_distribution == {"green": 2, "blue": 0, "red": 1, "gray": 0}


def test_dropped_participants_are_visible_in_participant_sections() -> None:
    team = build_all_teams_report(_gateway(), week_number=5).teams[0]

    dropped = [participant for participant in team.participants if participant.is_dropped]

    assert len(dropped) == 1
    assert dropped[0].full_name == "Ольга Соколова"
    assert dropped[0].risk_state == "dropped"


def test_insights_do_not_change_progress_or_status() -> None:
    gateway = _gateway(
        insights=[
            {"insight_id": "I001", "participant_id": "P002", "week_number": 5, "insight_text": "Большой инсайт"},
        ],
        weekly_reports=[
            _weekly_report("WR001", "P001", "green", "🟩", 1),
            _weekly_report("WR002", "P002", "red", "🟥", 0),
        ],
    )

    team = build_all_teams_report(gateway, week_number=5).teams[0]
    participant = next(section for section in team.participants if section.participant_id == "P002")

    assert participant.insights == ("Большой инсайт",)
    assert participant.status == "🟥"
    assert participant.progress_percent == 0
    assert team.weekly_victory_percent == 50


def test_deleted_audio_path_is_not_opened_during_aggregation() -> None:
    gateway = _gateway(
        weekly_reports=[
            {
                **_weekly_report("WR001", "P001", "green", "🟩", 1),
                "audio_file_path": "/tmp/deleted-audio.ogg",
                "audio_deleted_at": "2026-07-15T10:00:00+05:00",
            }
        ]
    )

    team = build_all_teams_report(gateway, week_number=5).teams[0]

    assert team.participants[0].transcription_text == "Расшифровка отчёта."


def test_unfinished_sqlite_drafts_are_not_part_of_reports() -> None:
    gateway = _gateway(
        weekly_reports=[],
        insights=[],
    )

    team = build_all_teams_report(gateway, week_number=5).teams[0]

    assert team.weekly_victory_percent == 0
    assert "черновик" not in "\n".join(section.report_text or "" for section in team.participants).lower()


def _gateway(
    *,
    weekly_reports: list[dict[str, object]] | None = None,
    weekly_focus: list[dict[str, object]] | None = None,
    insights: list[dict[str, object]] | None = None,
) -> FakeSheetsGateway:
    return FakeSheetsGateway(
        teams=[
            {"team_id": "T001", "team_name": "Команда А", "captain_id": "C001"},
        ],
        participants=[
            _participant("P001", "Анна Иванова", "active"),
            _participant("P002", "Пётр Смирнов", "risk_zone"),
            _participant("P003", "Ольга Соколова", "dropped"),
            _participant("C001", "Ирина Капитан", "active", role="captain"),
        ],
        goals=[
            _goal("G001", "P001", "Новый контракт"),
            _goal("G002", "P002", "Публичное выступление"),
            _goal("G003", "P003", "Запуск продукта"),
        ],
        planned_steps=[
            _step("S001", "P001", "G001", 1, "Найти клиента", "closed"),
            _step("S002", "P001", "G001", 2, "Провести встречу", "partial"),
            _step("S003", "P001", "G001", 3, "Подписать договор", "open"),
            _step("S004", "P002", "G002", 1, "Подготовить тезисы", "open"),
        ],
        weekly_reports=weekly_reports
        if weekly_reports is not None
        else [
            _weekly_report("WR001", "P001", "green", "🟩", 1),
            _weekly_report("WR002", "P002", "blue", "🟦", 0.5),
        ],
        weekly_report_steps=[
            {"weekly_report_step_id": "WRS001", "weekly_report_id": "WR001", "step_id": "S001"},
            {"weekly_report_step_id": "WRS002", "weekly_report_id": "WR002", "step_id": "S004"},
        ],
        weekly_focus=weekly_focus
        if weekly_focus is not None
        else [
            {
                "focus_id": "WF:P001:week-05",
                "participant_id": "P001",
                "goal_id": "G001",
                "step_id": "S002",
                "week_number": 5,
                "focus_status": "active",
            }
        ],
        insights=insights
        if insights is not None
        else [
            {
                "insight_id": "I001",
                "participant_id": "P001",
                "week_number": 5,
                "insight_text": "Лучше фиксировать договорённости.",
            }
        ],
    )


def _participant(
    participant_id: str,
    full_name: str,
    status: str,
    *,
    role: str = "participant",
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": 1000 + len(participant_id),
        "username": participant_id.lower(),
        "full_name": full_name,
        "role": role,
        "team_id": "T001",
        "team_name": "Команда А",
        "captain_id": "C001",
        "tracker_id": "TR001",
        "status": status,
    }


def _goal(goal_id: str, participant_id: str, title: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "participant_id": participant_id,
        "goal_title": title,
        "goal_description": f"Описание: {title}",
        "goal_value_amount": "100000",
        "goal_value_currency": "RUB",
        "permission_condition": "Условие выполнено",
        "goal_status": "active",
    }


def _step(
    step_id: str,
    participant_id: str,
    goal_id: str,
    step_number: int,
    title: str,
    status: str,
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_number": step_number,
        "step_title": title,
        "step_status": status,
    }


def _weekly_report(
    weekly_report_id: str,
    participant_id: str,
    status_code: str,
    status_symbol: str,
    score: int | float,
) -> dict[str, object]:
    return {
        "weekly_report_id": weekly_report_id,
        "participant_id": participant_id,
        "team_id": "T001",
        "goal_id": "G001",
        "week_number": 5,
        "status_code": status_code,
        "status_symbol": status_symbol,
        "status_score": score,
        "report_text": "Провела встречу.",
        "transcription_text": "Расшифровка отчёта.",
    }

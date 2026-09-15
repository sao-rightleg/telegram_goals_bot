from dataclasses import replace

from app.reports.formatting import (
    format_admin_summary_text,
    format_captain_summary_text,
    format_full_summary_text,
    format_group_comparison_text,
    format_participant_line,
    format_sitnikov_summary_text,
    format_team_summary_text,
    format_tracker_summary_text,
)
from app.reports.models import (
    AllTeamsReportData,
    ParticipantReportSection,
    ReportDeliveryItem,
    ReportRecipient,
    ReportRunResult,
    ReportType,
    TeamReportData,
)
from app.reports.metrics import submission_metrics
import pytest


def _participant_section(
    *,
    participant_id: str = "P001",
    full_name: str = "Анна Иванова",
    status: str = "🟩",
    dropped: bool = False,
) -> ParticipantReportSection:
    return ParticipantReportSection(
        participant_id=participant_id,
        team_id="T001",
        full_name=full_name,
        username="anna",
        status=status,
        is_dropped=dropped,
        risk_state="ok",
        progress_bar="■■■□□□",
        progress_percent=50,
        goal_title="Новый контракт",
        goal_description="Заключить контракт с клиентом",
        goal_value="100000 RUB",
        permission_condition="Оплата получена",
        planned_steps=("Найти клиента", "Провести встречу"),
        completed_steps=("Найти клиента",),
        partial_steps=("Провести встречу",),
        weekly_focus_step="Провести встречу",
        report_text="Провела встречу и согласовала следующий шаг.",
        transcription_text="Голосовая расшифровка отчёта.",
        insights=("Лучше заранее фиксировать договорённости.",),
    )


def _team_report() -> TeamReportData:
    return TeamReportData(
        week_number=5,
        team_id="T001",
        team_name="Команда А",
        captain_id="C001",
        captain_name="Ирина Капитан",
        active_count=2,
        dropped_count=1,
        status_distribution={"green": 1, "blue": 1, "red": 0, "gray": 0},
        weekly_victory_percent=75,
        participants=(
            _participant_section(),
            _participant_section(participant_id="P002", full_name="Пётр Смирнов", status="🟦"),
            _participant_section(participant_id="P003", full_name="Ольга Соколова", status="⬛", dropped=True),
        ),
    )


def test_team_summary_text_contains_required_fields() -> None:
    text = format_team_summary_text(_team_report())

    assert "Неделя 5" in text
    assert "Команда: Команда А" in text
    assert "Капитан: Ирина Капитан" in text
    assert "Активных: 2" in text
    assert "Выбывших: 1" in text
    assert "Победы недели: 75%" in text
    assert "🟩 1" in text
    assert "🟦 1" in text
    assert "⬛ 0" in text
    assert "Анна Иванова — ■■■□□□ 50%" in text
    assert "Ольга Соколова — ■■■□□□ 50% · выбыл" in text


def test_captain_summary_has_fixed_submission_logic_and_missing_names() -> None:
    report = replace(
        _team_report(),
        active_count=3,
        status_distribution={"green": 1, "blue": 0, "red": 1, "gray": 1},
        participants=(
            _participant_section(),
            _participant_section(participant_id="P002", full_name="Пётр Смирнов", status="🟥"),
            _participant_section(participant_id="P003", full_name="Мария Орлова", status="⬛"),
        ),
    )

    text = format_captain_summary_text(report)

    assert "📊 Итоги недели 5" in text
    assert "✅ Сдали: 2 из 3 — 66,7%" in text
    assert "❌ Не сдали: 1 из 3 — 33,3%" in text
    assert "• Мария Орлова" in text
    assert "Пётр Смирнов — отчёт сдан, но победы недели нет" in text


def test_tracker_summary_contains_only_supplied_assigned_teams() -> None:
    assigned = (_team_report(), replace(_team_report(), team_id="T002", team_name="Команда Б"))

    text = format_tracker_summary_text(assigned, tracker_name="Мария Трекер", week_number=5)

    assert "Зона ответственности: 2 команды" in text
    assert "Команда А" in text
    assert "Команда Б" in text
    assert "✅ Сдали: 4 из 4 — 100%" in text


def test_admin_summary_contains_flow_totals_and_per_team_breakdown() -> None:
    report = AllTeamsReportData(5, (_team_report(),), 2, 1, 75)

    text = format_admin_summary_text(report, flow_name="Сентябрь 2026")

    assert "Полные итоги недели 5" in text
    assert "Поток «Сентябрь 2026»" in text
    assert "✅ Сдали: 2 из 2 — 100%" in text
    assert "Команда А — не сдали 0 из 2 (0%)" in text
    assert "технические" not in text.lower()


def test_sitnikov_summary_contains_comparison_but_no_technical_details() -> None:
    second = replace(_team_report(), team_id="T002", team_name="Команда Б", weekly_victory_percent=50)
    report = AllTeamsReportData(5, (_team_report(), second), 4, 2, 63)

    text = format_sitnikov_summary_text(report, flow_name="Сентябрь 2026")

    assert "Итоги недели 5" in text
    assert "1. Команда А — 75%" in text
    assert "2. Команда Б — 50%" in text
    assert "ошиб" not in text.lower()


def test_submission_metrics_reject_inconsistent_active_status_counts() -> None:
    report = replace(
        _team_report(), active_count=3,
        status_distribution={"green": 1, "blue": 0, "red": 0, "gray": 0},
    )

    with pytest.raises(ValueError, match="Active participant count"):
        submission_metrics(report)


def test_role_summary_never_exceeds_telegram_message_limit() -> None:
    participants = tuple(
        replace(
            _participant_section(), participant_id=f"P{index:03d}",
            full_name=f"Участник с очень длинными именем и фамилией номер {index}", status="⬛",
        )
        for index in range(100)
    )
    team = replace(
        _team_report(), active_count=100, dropped_count=0,
        status_distribution={"green": 0, "blue": 0, "red": 0, "gray": 100},
        participants=participants,
    )

    text = format_admin_summary_text(
        AllTeamsReportData(5, (team,), 100, 0, 0), flow_name="Большой поток"
    )

    assert len(text) <= 4096
    assert text.endswith("Полные данные находятся в прикреплённом PDF.")


def test_participant_line_contains_progress_status_goal_and_report_text() -> None:
    text = format_participant_line(_participant_section())

    assert "Анна Иванова" in text
    assert "@anna" in text
    assert "🟩" in text
    assert "■■■□□□ 50%" in text
    assert "Новый контракт" in text
    assert "Фокус недели: Провести встречу" in text
    assert "Провела встречу" in text
    assert "Голосовая расшифровка" in text
    assert "Лучше заранее" in text


def test_full_summary_text_contains_global_counts_without_private_routing_data() -> None:
    data = AllTeamsReportData(
        week_number=5,
        teams=(_team_report(),),
        total_active_count=2,
        total_dropped_count=1,
        average_victory_percent=75,
    )

    text = format_full_summary_text(data)

    assert "Итог недели 5" in text
    assert "Команд: 1" in text
    assert "Активных: 2" in text
    assert "Выбывших: 1" in text
    assert "Средний процент побед: 75%" in text
    assert "Команда А: 75%" in text
    assert "chat_id" not in text
    assert "telegram_id" not in text
    assert "token" not in text.lower()


def test_group_comparison_text_contains_only_team_level_fields() -> None:
    data = AllTeamsReportData(
        week_number=5,
        teams=(_team_report(),),
        total_active_count=2,
        total_dropped_count=1,
        average_victory_percent=75,
    )

    text = format_group_comparison_text(data)

    assert "Сравнение групп за неделю 5" in text
    assert "Команда А — 75%" in text
    assert "активных 2" in text
    assert "выбывших 1" in text
    assert "Анна Иванова" not in text
    assert "Провела встречу" not in text
    assert "Голосовая расшифровка" not in text


def test_report_models_are_plain_adapter_independent_contracts() -> None:
    recipient = ReportRecipient(
        recipient_type="captain",
        recipient_id="C001",
        chat_id="100500",
        team_scope_id="T001",
    )
    item = ReportDeliveryItem(
        report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
        scope_id="T001",
        recipient=recipient,
        text="summary",
    )
    result = ReportRunResult(generated_count=1, sent_count=1, skipped_count=0, failed_count=0)

    assert item.file_path is None
    assert item.text == "summary"
    assert result.sent_count == 1
    assert "bot" not in item.__dict__
    assert "sheets" not in item.__dict__
    assert "sqlite" not in item.__dict__

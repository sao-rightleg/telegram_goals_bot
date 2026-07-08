from app.reports.formatting import (
    format_full_summary_text,
    format_group_comparison_text,
    format_participant_line,
    format_team_summary_text,
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
        status_distribution={"green": 1, "blue": 1, "red": 0, "gray": 1},
        weekly_victory_percent=75,
        participants=(
            _participant_section(),
            _participant_section(participant_id="P002", full_name="Пётр Смирнов", status="🟦"),
            _participant_section(participant_id="P003", full_name="Ольга Соколова", status="⬜", dropped=True),
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
    assert "⬜ 1" in text
    assert "Анна Иванова — ■■■□□□ 50%" in text
    assert "Ольга Соколова — ■■■□□□ 50% · выбыл" in text


def test_participant_line_contains_progress_status_goal_and_report_text() -> None:
    text = format_participant_line(_participant_section())

    assert "Анна Иванова" in text
    assert "@anna" in text
    assert "🟩" in text
    assert "■■■□□□ 50%" in text
    assert "Новый контракт" in text
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

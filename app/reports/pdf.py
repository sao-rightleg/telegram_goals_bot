"""Role-specific PDF reports rendered with embedded Cyrillic fonts."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import os
from pathlib import Path
import tempfile
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import font_roboto

from app.reports.models import AllTeamsReportData, ParticipantReportSection, TeamReportData
from app.reports.metrics import submission_metrics
from app.storage.paths import StoragePathPolicy


FONT_NAME = "Roboto"
FONT_BOLD_NAME = "Roboto-Bold"
_ROBOTO_ROOT = Path(font_roboto.__file__).parent / "files"
FONT_PATHS = (
    _ROBOTO_ROOT / "Roboto-Regular.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
)
FONT_BOLD_PATHS = (
    _ROBOTO_ROOT / "Roboto-Bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
)

STATUS_LABELS = {
    "🟩": ("Победа недели", colors.HexColor("#2E7D32")),
    "🟦": ("Частичная победа", colors.HexColor("#1976D2")),
    "🟥": ("Нет победы", colors.HexColor("#C62828")),
    "⬛": ("Нет отчёта в срок", colors.HexColor("#424242")),
}


@dataclass(frozen=True)
class RenderedPdfReport:
    file_path: Path


@dataclass(frozen=True)
class LocalPdfRenderer:
    path_policy: StoragePathPolicy

    def render_team_report(
        self, report: TeamReportData, *, year: int = 2026, flow_id: str | None = None
    ) -> RenderedPdfReport:
        path = self.path_policy.pdf_path(
            year=year,
            week_number=report.week_number,
            team_slug=_scoped_slug(flow_id, report.team_id),
            file_name=f"{report.team_id}.pdf",
        )
        story = _report_heading("Отчёт капитана", report.week_number)
        story.extend(_team_story(report, include_participants=True))
        return _render(path, story, document_title=f"Отчёт капитана — {report.team_name}")

    def render_tracker_report(
        self,
        teams: Iterable[TeamReportData],
        *,
        tracker_id: str,
        tracker_name: str,
        week_number: int,
        year: int = 2026,
        flow_id: str | None = None,
    ) -> RenderedPdfReport:
        team_reports = tuple(teams)
        path = self.path_policy.pdf_path(
            year=year,
            week_number=week_number,
            team_slug=_scoped_slug(flow_id, f"tracker_{tracker_id}"),
            file_name=f"tracker_{tracker_id}.pdf",
        )
        story = _report_heading("Отчёт трекера", week_number, f"Трекер: {tracker_name}")
        story.extend(_multi_team_summary(team_reports))
        story.extend(_operational_summary(team_reports))
        for index, team in enumerate(team_reports):
            if index:
                story.append(PageBreak())
            story.extend(_team_story(team, include_participants=True))
        return _render(path, story, document_title=f"Отчёт трекера — {tracker_name}")

    def render_full_report(
        self, report: AllTeamsReportData, *, year: int = 2026, flow_id: str | None = None
    ) -> RenderedPdfReport:
        path = self.path_policy.pdf_path(
            year=year,
            week_number=report.week_number,
            team_slug=_scoped_slug(flow_id, "all_teams"),
            file_name="full_report.pdf",
        )
        story = _report_heading("Полный отчёт по потоку", report.week_number)
        styles = _styles()
        story.extend(
            [
                Paragraph(f"Всего активных: {report.total_active_count}", styles["Body"]),
                Paragraph(f"Всего выбывших: {report.total_dropped_count}", styles["Body"]),
                Paragraph(f"Средний процент побед: {report.average_victory_percent}%", styles["Body"]),
                Spacer(1, 5 * mm),
            ]
        )
        story.extend(_multi_team_summary(report.teams))
        story.extend(_operational_summary(report.teams))
        story.extend(_group_comparison(report.teams))
        for team in report.teams:
            story.append(PageBreak())
            story.extend(_team_story(team, include_participants=True))
        return _render(path, story, document_title="Полный отчёт по потоку")


def _render(path: Path, story: list[object], *, document_title: str) -> RenderedPdfReport:
    _register_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".pdf-", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        document = SimpleDocTemplate(
            str(temporary_path),
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=document_title,
            author="Смерть иллюзий",
        )
        document.build(story, onFirstPage=_footer, onLaterPages=_footer)
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return RenderedPdfReport(file_path=path)


def _register_fonts() -> None:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(_find_font(FONT_PATHS))))
    if FONT_BOLD_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, str(_find_font(FONT_BOLD_PATHS))))


def _find_font(candidates: tuple[Path, ...]) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError("A Cyrillic TrueType font is required for PDF reports")


def _styles() -> dict[str, ParagraphStyle]:
    _register_fonts()
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName=FONT_BOLD_NAME,
            fontSize=20, leading=24, textColor=colors.HexColor("#202124"), alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "H1": ParagraphStyle(
            "ReportH1", parent=base["Heading1"], fontName=FONT_BOLD_NAME,
            fontSize=15, leading=19, textColor=colors.HexColor("#202124"), spaceBefore=3 * mm, spaceAfter=3 * mm,
        ),
        "H2": ParagraphStyle(
            "ReportH2", parent=base["Heading2"], fontName=FONT_BOLD_NAME,
            fontSize=12, leading=15, textColor=colors.HexColor("#303F9F"), spaceBefore=3 * mm, spaceAfter=2 * mm,
        ),
        "Body": ParagraphStyle(
            "ReportBody", parent=base["BodyText"], fontName=FONT_NAME,
            fontSize=9.5, leading=13, textColor=colors.HexColor("#202124"), spaceAfter=1.5 * mm,
        ),
        "Small": ParagraphStyle(
            "ReportSmall", parent=base["BodyText"], fontName=FONT_NAME,
            fontSize=8, leading=10, textColor=colors.HexColor("#5F6368"),
        ),
    }


def _report_heading(title: str, week_number: int, subtitle: str | None = None) -> list[object]:
    styles = _styles()
    story: list[object] = [Paragraph(escape(title), styles["Title"])]
    if subtitle:
        story.append(Paragraph(escape(subtitle), styles["Body"]))
    story.extend((Paragraph(f"Неделя {week_number}", styles["Body"]), Spacer(1, 3 * mm)))
    return story


def _team_story(report: TeamReportData, *, include_participants: bool) -> list[object]:
    styles = _styles()
    story: list[object] = [Paragraph(f"Команда: {escape(report.team_name)}", styles["H1"])]
    story.extend(
        [
            Paragraph(f"Капитан: {escape(report.captain_name)}", styles["Body"]),
            Paragraph(f"Активных: {report.active_count}", styles["Body"]),
            Paragraph(f"Выбывших: {report.dropped_count}", styles["Body"]),
            _team_metrics_table(report),
            Spacer(1, 4 * mm),
        ]
    )
    active = tuple(item for item in report.participants if not item.is_dropped)
    dropped = tuple(item for item in report.participants if item.is_dropped)
    story.extend((Paragraph("Активные участники", styles["H2"]), _participant_overview(active)))
    risk_names = [item.full_name for item in active if item.risk_state != "ok"]
    if risk_names:
        story.append(_field("Зона риска", ", ".join(risk_names)))
    if dropped:
        story.extend((Paragraph("Выбывшие участники", styles["H2"]), _participant_overview(dropped)))
    if include_participants:
        for participant in (*active, *dropped):
            story.extend((Spacer(1, 4 * mm), *_participant_story(participant)))
    return story


def _team_metrics_table(report: TeamReportData) -> Table:
    distribution = report.status_distribution
    rows = [
        ["Активных", "Выбывших", "Победы недели"],
        [str(report.active_count), str(report.dropped_count), f"{report.weekly_victory_percent}%"],
        ["Победа", "Частичная", "Нет победы / ответа"],
        [
            str(distribution.get("green", 0)),
            str(distribution.get("blue", 0)),
            f"{distribution.get('red', 0)} / {distribution.get('gray', 0)}",
        ],
    ]
    table = Table(rows, colWidths=[55 * mm, 55 * mm, 55 * mm])
    table.setStyle(_table_style(header_rows=(0, 2)))
    return table


def _participant_overview(participants: Iterable[ParticipantReportSection]) -> Table:
    styles = _styles()
    rows: list[list[object]] = [["Участник", "Статус", "Прогресс", "Риск"]]
    for item in participants:
        status_label = STATUS_LABELS.get(item.status, (item.status, colors.black))[0]
        risk = "Выбыл" if item.is_dropped else ("Зона риска" if item.risk_state != "ok" else "—")
        rows.append(
            [
                Paragraph(escape(item.full_name), styles["Small"]),
                Paragraph(escape(status_label), styles["Small"]),
                Paragraph(f"{_plain_progress(item.progress_bar)} {item.progress_percent}%", styles["Small"]),
                Paragraph(risk, styles["Small"]),
            ]
        )
    table = Table(rows, colWidths=[58 * mm, 43 * mm, 38 * mm, 26 * mm], repeatRows=1)
    table.setStyle(_table_style(header_rows=(0,)))
    return table


def _participant_story(item: ParticipantReportSection) -> list[object]:
    styles = _styles()
    status_label, status_color = STATUS_LABELS.get(item.status, (item.status, colors.black))
    username = f" @{escape(item.username)}" if item.username else ""
    title = Paragraph(f"{escape(item.full_name)}{username}", styles["H2"])
    summary = Table(
        [["Статус", "Прогресс", "Состояние"], [status_label, f"{_plain_progress(item.progress_bar)} {item.progress_percent}%", _risk_label(item)]],
        colWidths=[55 * mm, 65 * mm, 45 * mm],
    )
    summary.setStyle(_table_style(header_rows=(0,)))
    summary.setStyle(TableStyle([("TEXTCOLOR", (0, 1), (0, 1), status_color)]))
    fixed = KeepTogether(
        [
            title,
            summary,
            Spacer(1, 2 * mm),
            _field("Цель", item.goal_title),
            _field("Описание", item.goal_description),
            _field("Ценность", item.goal_value),
            _field("Условие разрешения", item.permission_condition),
        ]
    )
    story: list[object] = [fixed]
    story.extend(_optional_field("Запланированные шаги", item.planned_steps))
    story.extend(_optional_field("Выполненные шаги", item.completed_steps))
    story.extend(_optional_field("Частично выполненные шаги", item.partial_steps))
    if item.weekly_focus_step:
        story.append(_field("Фокус недели", item.weekly_focus_step))
    if item.report_text:
        story.append(_field("Отчёт", item.report_text))
    if item.transcription_text:
        story.append(_field("Расшифровка", item.transcription_text))
    story.extend(_optional_field("Инсайты", item.insights))
    return story


def _multi_team_summary(teams: Iterable[TeamReportData]) -> list[object]:
    styles = _styles()
    rows: list[list[object]] = [["Команда", "Активных", "Сдали", "Не сдали", "Победы"]]
    for team in teams:
        # Red means a submitted report without a weekly victory; only gray is no answer.
        metrics = submission_metrics(team)
        missing = metrics.missing_count
        submitted = metrics.submitted_count
        rows.append(
            [
                Paragraph(escape(team.team_name), styles["Small"]),
                str(team.active_count),
                _count_percent(submitted, team.active_count),
                _count_percent(missing, team.active_count),
                f"{team.weekly_victory_percent}%",
            ]
        )
    table = Table(rows, colWidths=[58 * mm, 25 * mm, 30 * mm, 30 * mm, 25 * mm], repeatRows=1)
    table.setStyle(_table_style(header_rows=(0,)))
    return [Paragraph("Сводка по командам", styles["H1"]), table, Spacer(1, 4 * mm)]


def _operational_summary(teams: Iterable[TeamReportData]) -> list[object]:
    styles = _styles()
    team_reports = tuple(teams)
    total = sum(team.active_count for team in team_reports)
    metrics = tuple(submission_metrics(team) for team in team_reports)
    missing = sum(item.missing_count for item in metrics)
    submitted = sum(item.submitted_count for item in metrics)
    story: list[object] = [
        Paragraph("Исполнительская дисциплина", styles["H1"]),
        Paragraph(f"Всего сдали: {_count_percent(submitted, total)}", styles["Body"]),
        Paragraph(f"Всего не сдали: {_count_percent(missing, total)}", styles["Body"]),
    ]
    for team in team_reports:
        missing_names = [
            item.full_name for item in team.participants if not item.is_dropped and item.status == "⬛"
        ]
        risk_names = [
            item.full_name for item in team.participants if not item.is_dropped and item.risk_state != "ok"
        ]
        dropped_names = [item.full_name for item in team.participants if item.is_dropped]
        story.append(Paragraph(escape(team.team_name), styles["H2"]))
        story.append(_field("Не сдали", ", ".join(missing_names) if missing_names else "нет"))
        story.append(_field("Зона риска", ", ".join(risk_names) if risk_names else "нет"))
        story.append(_field("Выбывшие", ", ".join(dropped_names) if dropped_names else "нет"))
    return story


def _group_comparison(teams: Iterable[TeamReportData]) -> list[object]:
    styles = _styles()
    sorted_teams = sorted(teams, key=lambda item: item.weekly_victory_percent, reverse=True)
    story: list[object] = [Paragraph("Сравнение команд", styles["H1"])]
    story.extend(
        Paragraph(
            f"{position}. {escape(team.team_name)} — {team.weekly_victory_percent}% побед недели",
            styles["Body"],
        )
        for position, team in enumerate(sorted_teams, start=1)
    )
    return story


def _field(label: str, value: object) -> Paragraph:
    styles = _styles()
    return Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", styles["Body"])


def _optional_field(label: str, values: Iterable[str]) -> list[Paragraph]:
    items = [value for value in values if value]
    return [_field(label, "; ".join(items))] if items else []


def _table_style(*, header_rows: tuple[int, ...]) -> TableStyle:
    commands: list[tuple] = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DADCE0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row in header_rows:
        commands.extend(
            [
                ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#EEF1F8")),
                ("FONTNAME", (0, row), (-1, row), FONT_BOLD_NAME),
            ]
        )
    return TableStyle(commands)


def _footer(canvas: object, document: object) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(16 * mm, 10 * mm, "Смерть иллюзий")
    canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Страница {document.page}")
    canvas.restoreState()


def _plain_progress(value: str) -> str:
    return value.replace("🟩", "■").replace("🟦", "◐").replace("🟥", "×").replace("⬜", "□")


def _risk_label(item: ParticipantReportSection) -> str:
    if item.is_dropped:
        return "Выбыл"
    return "Зона риска" if item.risk_state != "ok" else "Активен"


def _count_percent(count: int, total: int) -> str:
    percent = 0 if total == 0 else round(count / total * 100, 1)
    return f"{count} из {total} ({percent:g}%)"


def _scoped_slug(flow_id: str | None, suffix: str) -> str:
    return suffix if flow_id is None else f"{flow_id}__{suffix}"

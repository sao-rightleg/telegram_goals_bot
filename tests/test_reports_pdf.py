from pathlib import Path

import pytest

from app.reports.generator import LocalReportGenerator, ReportRequest, ReportType
from app.reports.models import ParticipantReportSection, TeamReportData
from app.reports.pdf import LocalPdfRenderer
from app.storage.paths import StoragePathPolicy


def test_pdf_renderer_writes_team_report_under_storage_path_policy(tmp_path: Path) -> None:
    renderer = LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))

    generated = renderer.render_team_report(_team_report(), year=2026)

    assert generated.file_path == tmp_path / "reports" / "pdf" / "2026" / "week_05" / "T001" / "T001.pdf"
    assert generated.file_path.exists()


def test_pdf_renderer_creates_non_empty_pdf_file(tmp_path: Path) -> None:
    renderer = LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))

    generated = renderer.render_team_report(_team_report(), year=2026)

    data = generated.file_path.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert len(data) > 200


def test_pdf_renderer_includes_required_team_and_participant_content(tmp_path: Path) -> None:
    renderer = LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))

    generated = renderer.render_team_report(_team_report(), year=2026)

    text = generated.file_path.read_bytes().decode("utf-8", errors="ignore")
    assert "Команда: Команда А" in text
    assert "Капитан: Ирина Капитан" in text
    assert "Активных: 1" in text
    assert "Анна Иванова" in text
    assert "Новый контракт" in text
    assert "Расшифровка отчёта" in text


def test_pdf_renderer_does_not_open_audio_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    renderer = LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))

    def fail_on_deleted_audio(self: Path, *args: object, **kwargs: object) -> object:
        if str(self).endswith("deleted-audio.ogg"):
            raise AssertionError("audio file must not be opened")
        return original_open(self, *args, **kwargs)

    original_open = Path.open
    monkeypatch.setattr(Path, "open", fail_on_deleted_audio)

    generated = renderer.render_team_report(_team_report(transcription_text="deleted-audio.ogg"), year=2026)

    assert generated.file_path.exists()


def test_report_generator_boundary_can_generate_team_pdf(tmp_path: Path) -> None:
    renderer = LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))
    generator = LocalReportGenerator(pdf_renderer=renderer)

    generated = generator.generate_team_report(
        ReportRequest(
            report_type=ReportType.PDF_TEAM_REPORT,
            week_number=5,
            team_id="T001",
            year=2026,
            team_report=_team_report(),
        )
    )

    assert generated.report_type is ReportType.PDF_TEAM_REPORT
    assert generated.file_path == tmp_path / "reports" / "pdf" / "2026" / "week_05" / "T001" / "T001.pdf"
    assert generated.text is None


def _team_report(*, transcription_text: str = "Расшифровка отчёта") -> TeamReportData:
    return TeamReportData(
        week_number=5,
        team_id="T001",
        team_name="Команда А",
        captain_id="C001",
        captain_name="Ирина Капитан",
        active_count=1,
        dropped_count=0,
        status_distribution={"green": 1, "blue": 0, "red": 0, "gray": 0},
        weekly_victory_percent=100,
        participants=(
            ParticipantReportSection(
                participant_id="P001",
                team_id="T001",
                full_name="Анна Иванова",
                username="anna",
                status="🟩",
                is_dropped=False,
                risk_state="ok",
                progress_bar="🟩🟦⬜⬜⬜⬜",
                progress_percent=25,
                goal_title="Новый контракт",
                goal_description="Заключить контракт",
                goal_value="100000 RUB",
                permission_condition="Оплата получена",
                planned_steps=("Найти клиента", "Провести встречу"),
                completed_steps=("Найти клиента",),
                partial_steps=("Провести встречу",),
                report_text="Провела встречу.",
                transcription_text=transcription_text,
                insights=("Лучше фиксировать договорённости.",),
            ),
        ),
    )

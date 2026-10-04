import pytest

from app.sheets.gateway import FakeSheetsGateway, GoogleSheetsGateway
from tests.test_sheets_live_helpers import FakeSheetsService

HEADERS = ["flow_id", "participant_id", "about_me", "role", "formula"]
ROWS = [
    ["F1", "P1", "Старое", "participant", "=1+1"],
    ["F2", "P1", "Чужое", "participant", "=2+2"],
]


@pytest.fixture(params=["live", "fake"])
def gateway(request):
    if request.param == "live":
        return GoogleSheetsGateway(
            FakeSheetsService({"Participants": [HEADERS, *ROWS]}), "sheet"
        )
    return FakeSheetsGateway(participants=[dict(zip(HEADERS, row)) for row in ROWS])


def test_update_only_own_description_and_preserve_formula(gateway):
    gateway.update_participant_about("F1", "P1", "=Опыт <разработчика>")
    own = gateway.list_participants()[0]
    assert own["about_me"] == "=Опыт <разработчика>"
    assert own["formula"] == "=1+1" and own["role"] == "participant"
    assert gateway.list_participants()[1]["about_me"] == "Чужое"
    if isinstance(gateway, GoogleSheetsGateway):
        assert gateway.service.updated == [
            ("'Participants'!C2", [["=Опыт <разработчика>"]])
        ]
        assert gateway.service.value_input_options == [("update", "RAW")]


@pytest.mark.parametrize(
    "flow,participant,text",
    [
        ("", "P1", "text"),
        ("F1", "", "text"),
        ("F1", "P1", " "),
        ("F1", "P1", "x" * 12001),
    ],
)
def test_invalid_profile_rejected(gateway, flow, participant, text):
    before = gateway.list_participants()
    with pytest.raises(ValueError):
        gateway.update_participant_about(flow, participant, text)
    assert gateway.list_participants() == before


def test_unknown_scope_rejected(gateway):
    with pytest.raises(KeyError):
        gateway.update_participant_about("OTHER", "P1", "text")


@pytest.mark.parametrize("text", ["001", "TRUE", "FALSE", "1.5", "0"])
def test_description_read_preserves_literal_text(gateway, text):
    gateway.update_participant_about("F1", "P1", text)
    assert gateway.list_participants()[0]["about_me"] == text

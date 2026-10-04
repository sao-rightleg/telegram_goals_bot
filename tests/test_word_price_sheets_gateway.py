import pytest
from concurrent.futures import ThreadPoolExecutor

from app.sheets.gateway import FakeSheetsGateway, GoogleSheetsGateway
from app.domain import MAX_EXACT_WORD_PRICE_RUB
from tests.test_sheets_live_helpers import FakeSheetsService


HEADERS = ["flow_id", "participant_id", "word_price_rub", "created_at", "updated_at"]
ROW = {
    "flow_id": "F001",
    "participant_id": "P001",
    "word_price_rub": 5000,
    "created_at": "2026-10-04T10:00:00+05:00",
    "updated_at": "2026-10-04T10:00:00+05:00",
}


@pytest.fixture(params=["live", "fake"])
def gateway(request):
    if request.param == "live":
        return GoogleSheetsGateway(
            FakeSheetsService({"WordPrices": [HEADERS]}), "sheet-id"
        )
    return FakeSheetsGateway()


def test_word_price_save_is_idempotent_and_scoped_by_flow(gateway) -> None:
    gateway.save_word_price(ROW)
    gateway.save_word_price(ROW)
    gateway.save_word_price({**ROW, "flow_id": "F002", "word_price_rub": 100})
    assert gateway.find_word_price("F001", "P001")["word_price_rub"] == 5000
    assert gateway.find_word_price("F002", "P001")["word_price_rub"] == 100
    assert gateway.find_word_price("F001", "P_OTHER") is None
    if isinstance(gateway, GoogleSheetsGateway):
        assert len(gateway.service.sheets["WordPrices"]) == 3
        assert gateway.service.sheets["WordPrices"][1][2] == 5000
    else:
        assert len(gateway._word_prices) == 2


@pytest.mark.parametrize(
    "amount", [0, -1, 1.5, "5000", True, MAX_EXACT_WORD_PRICE_RUB + 1]
)
def test_gateway_rejects_invalid_word_price(gateway, amount) -> None:
    with pytest.raises(ValueError):
        gateway.save_word_price({**ROW, "word_price_rub": amount})
    assert gateway.find_word_price("F001", "P001") is None


def test_gateway_stores_maximum_exact_integer(gateway) -> None:
    gateway.save_word_price({**ROW, "word_price_rub": MAX_EXACT_WORD_PRICE_RUB})
    assert (
        gateway.find_word_price("F001", "P001")["word_price_rub"]
        == MAX_EXACT_WORD_PRICE_RUB
    )


def test_retry_with_different_amount_preserves_saved_declaration(gateway) -> None:
    gateway.save_word_price(ROW)
    gateway.save_word_price({**ROW, "word_price_rub": 100})
    assert gateway.find_word_price("F001", "P001") == ROW


@pytest.mark.parametrize("field", ["flow_id", "participant_id"])
def test_gateway_rejects_missing_scope(gateway, field) -> None:
    with pytest.raises(ValueError):
        gateway.save_word_price({**ROW, field: ""})
    assert gateway.find_word_price("F001", "P001") is None


def test_concurrent_retries_create_one_word_price(gateway) -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: gateway.save_word_price(ROW), range(8)))
    if isinstance(gateway, GoogleSheetsGateway):
        assert len(gateway.service.sheets["WordPrices"]) == 2
    else:
        assert len(gateway._word_prices) == 1

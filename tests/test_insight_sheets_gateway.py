from app.sheets.gateway import FakeSheetsGateway


def test_lists_insights_for_current_participant_only() -> None:
    gateway = FakeSheetsGateway(
        insights=[
            _insight("I001", "P001", "2026-06-23"),
            _insight("I002", "P002", "2026-06-24"),
            _insight("I003", "P001", "2026-06-25"),
        ]
    )

    rows = gateway.list_insights_for_participant("P001")

    assert [row["insight_id"] for row in rows] == ["I001", "I003"]
    assert all(row["participant_id"] == "P001" for row in rows)


def test_get_participant_insight_requires_participant_scope() -> None:
    gateway = FakeSheetsGateway(
        insights=[
            _insight("I001", "P001", "2026-06-23"),
            _insight("I002", "P002", "2026-06-24"),
        ]
    )

    assert gateway.get_participant_insight("P001", "I001") == _insight("I001", "P001", "2026-06-23")
    assert gateway.get_participant_insight("P001", "I002") is None
    assert gateway.get_participant_insight("P001", "I404") is None


def test_insight_rows_include_title_and_date_fields_without_mutation() -> None:
    gateway = FakeSheetsGateway()
    row = _insight("I001", "P001", "2026-06-23")

    gateway.append_insight(row)
    row["insight_title"] = "Mutated title"

    stored = gateway.get_participant_insight("P001", "I001")

    assert stored is not None
    assert stored["insight_title"] == "Нехватка планирования"
    assert stored["insight_date"] == "2026-06-23"

    stored["insight_title"] = "Mutated again"
    assert gateway.get_participant_insight("P001", "I001")["insight_title"] == "Нехватка планирования"


def test_existing_insight_append_and_list_behavior_is_preserved() -> None:
    gateway = FakeSheetsGateway()

    gateway.append_insight({"insight_id": "I001", "participant_id": "P001"})

    assert gateway.list_insights() == [{"insight_id": "I001", "participant_id": "P001"}]
    assert gateway.list_insights_for_participant("P001") == [
        {"insight_id": "I001", "participant_id": "P001"}
    ]


def _insight(insight_id: str, participant_id: str, insight_date: str) -> dict[str, object]:
    return {
        "insight_id": insight_id,
        "participant_id": participant_id,
        "goal_id": "G001",
        "week_number": 3,
        "insight_scope": "current_week",
        "insight_title": "Нехватка планирования",
        "insight_date": insight_date,
        "insight_text": "Сегодня я понял, что мне не хватает планирования.",
        "created_by_id": participant_id,
        "created_by_role": "participant",
        "created_at": f"{insight_date}T10:00:00+05:00",
    }

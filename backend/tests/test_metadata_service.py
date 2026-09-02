from services.metadata_service import summarize_categories


def test_summarize_categories_groups_and_sorts():
    rows = [
        ("Disease", "A"),
        ("Health system", "B"),
        ("Disease", "C"),
        ("", "D"),
        (None, "E"),
    ]

    assert summarize_categories(rows) == [
        {"category": "Disease", "count": 2},
        {"category": "Health system", "count": 1},
    ]

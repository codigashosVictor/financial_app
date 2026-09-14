from datetime import date

from app.core.card_schedule import select_upcoming_payment_per_card


def test_selects_next_cycle_with_pending_balance_when_closest_is_already_paid():
    events = [
        {"card_id": "c1", "due_date": date(2026, 9, 24), "amount": 0.0},
        {"card_id": "c1", "due_date": date(2026, 10, 24), "amount": 716.58},
        {"card_id": "c1", "due_date": date(2026, 11, 24), "amount": 716.58},
    ]

    selected = select_upcoming_payment_per_card(events)

    assert len(selected) == 1
    assert selected[0]["due_date"] == date(2026, 10, 24)
    assert selected[0]["amount"] == 716.58


def test_falls_back_to_closest_due_date_when_all_cycles_are_settled():
    events = [
        {"card_id": "c1", "due_date": date(2026, 9, 24), "amount": 0.0},
        {"card_id": "c1", "due_date": date(2026, 10, 24), "amount": 0.0},
    ]

    selected = select_upcoming_payment_per_card(events)

    assert selected[0]["due_date"] == date(2026, 9, 24)
    assert selected[0]["amount"] == 0.0


def test_handles_multiple_cards_independently():
    events = [
        {"card_id": "c1", "due_date": date(2026, 9, 24), "amount": 0.0},
        {"card_id": "c1", "due_date": date(2026, 10, 24), "amount": 500.0},
        {"card_id": "c2", "due_date": date(2026, 9, 10), "amount": 200.0},
    ]

    selected = select_upcoming_payment_per_card(events)
    by_card = {e["card_id"]: e for e in selected}

    assert by_card["c1"]["due_date"] == date(2026, 10, 24)
    assert by_card["c2"]["due_date"] == date(2026, 9, 10)


def test_empty_input_returns_empty_list():
    assert select_upcoming_payment_per_card([]) == []

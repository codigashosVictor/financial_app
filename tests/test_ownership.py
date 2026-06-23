import pytest
from fastapi import HTTPException

from app.core.ownership import (
    get_owned_card,
    get_owned_card_payment,
    get_owned_income,
    get_owned_installment_plan,
    get_owned_subscription,
)


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, fields):
        self.fields = fields
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        data = self.rows
        for field, value in self.filters:
            data = [row for row in data if row.get(field) == value]
        return Result(data)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables
        self.last_query = None

    def table(self, name):
        self.last_query = Query(self.tables[name])
        return self.last_query


def test_owned_card_requires_matching_user_id():
    supabase = FakeSupabase({
        "credit_cards": [{"id": "card-1", "user_id": "user-1", "cut_day": 15}],
    })

    card = get_owned_card(supabase, "user-1", "card-1", "cut_day")

    assert card["cut_day"] == 15
    assert ("user_id", "user-1") in supabase.last_query.filters


def test_owned_card_rejects_other_user_card():
    supabase = FakeSupabase({
        "credit_cards": [{"id": "card-1", "user_id": "user-2"}],
    })

    with pytest.raises(HTTPException) as exc:
        get_owned_card(supabase, "user-1", "card-1")

    assert exc.value.status_code == 404


def test_owned_subscription_requires_matching_user_id():
    supabase = FakeSupabase({
        "subscriptions": [{"id": "sub-1", "user_id": "user-1", "is_active": True}],
    })

    sub = get_owned_subscription(supabase, "user-1", "sub-1", "is_active")

    assert sub["is_active"] is True
    assert ("user_id", "user-1") in supabase.last_query.filters


def test_owned_installment_plan_rejects_other_user_plan():
    supabase = FakeSupabase({
        "installment_plans": [{"id": "plan-1", "user_id": "user-2"}],
    })

    with pytest.raises(HTTPException) as exc:
        get_owned_installment_plan(supabase, "user-1", "plan-1", "id")

    assert exc.value.status_code == 404


def test_owned_card_payment_requires_matching_user_id():
    supabase = FakeSupabase({
        "card_payments": [
            {"id": "pay-1", "user_id": "user-1", "card_id": "card-1", "amount": 500}
        ],
    })

    payment = get_owned_card_payment(supabase, "user-1", "pay-1", "id, card_id, amount")

    assert payment["amount"] == 500
    assert ("user_id", "user-1") in supabase.last_query.filters


def test_owned_card_payment_rejects_other_user():
    supabase = FakeSupabase({
        "card_payments": [{"id": "pay-1", "user_id": "user-2", "amount": 500}],
    })

    with pytest.raises(HTTPException) as exc:
        get_owned_card_payment(supabase, "user-1", "pay-1")

    assert exc.value.status_code == 404


def test_owned_card_payment_returns_404_when_missing():
    supabase = FakeSupabase({"card_payments": []})

    with pytest.raises(HTTPException) as exc:
        get_owned_card_payment(supabase, "user-1", "nonexistent-id")

    assert exc.value.status_code == 404


def test_owned_income_requires_matching_user_id():
    supabase = FakeSupabase({
        "incomes": [{"id": "inc-1", "user_id": "user-1", "amount": 1200}],
    })

    income = get_owned_income(supabase, "user-1", "inc-1", "id, amount")

    assert income["amount"] == 1200
    assert ("user_id", "user-1") in supabase.last_query.filters


def test_owned_income_rejects_other_user():
    supabase = FakeSupabase({
        "incomes": [{"id": "inc-1", "user_id": "user-2", "amount": 1200}],
    })

    with pytest.raises(HTTPException) as exc:
        get_owned_income(supabase, "user-1", "inc-1")

    assert exc.value.status_code == 404

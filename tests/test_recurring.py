from datetime import date

from app.core.billing_cycle import get_billing_period
from app.core.recurring import generate_installment_expenses, generate_subscription_expenses


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.pending_insert = None

    def select(self, fields):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def insert(self, payload):
        self.pending_insert = payload
        return self

    def execute(self):
        if self.pending_insert is not None:
            self.client.tables[self.table_name].append(self.pending_insert)
            return Result([self.pending_insert])

        rows = self.client.tables.get(self.table_name, [])
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        return Result(rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, table_name):
        return Query(self, table_name)


def test_subscription_does_not_duplicate_existing_expense():
    billing_period = get_billing_period(date.today().replace(day=10), 15)
    supabase = FakeSupabase({
        "subscriptions": [{
            "id": "sub-1",
            "user_id": "user-1",
            "card_id": "card-1",
            "name": "Netflix",
            "amount": 199,
            "charge_day": 10,
            "category": "Entretenimiento",
            "credit_cards": {"cut_day": 15},
            "is_active": True,
        }],
        "expenses": [{
            "id": "exp-1",
            "user_id": "user-1",
            "subscription_id": "sub-1",
            "billing_period": billing_period,
        }],
    })

    generated = generate_subscription_expenses(supabase, "user-1", "token")

    assert generated == 0
    assert len(supabase.tables["expenses"]) == 1


def test_subscription_creates_expense_with_user_id():
    supabase = FakeSupabase({
        "subscriptions": [{
            "id": "sub-1",
            "user_id": "user-1",
            "card_id": "card-1",
            "name": "Spotify",
            "amount": 129,
            "charge_day": 10,
            "category": "Entretenimiento",
            "credit_cards": {"cut_day": 15},
            "is_active": True,
        }],
        "expenses": [],
    })

    generated = generate_subscription_expenses(supabase, "user-1", "token")

    assert generated == 1
    assert supabase.tables["expenses"][0]["user_id"] == "user-1"


def test_installment_does_not_duplicate_existing_period():
    supabase = FakeSupabase({
        "installment_plans": [{
            "id": "plan-1",
            "user_id": "user-1",
            "card_id": "card-1",
            "name": "Laptop",
            "monthly_amount": 500,
            "installments": 1,
            "start_period": "2026-05",
            "category": "Tecnología",
            "credit_cards": {"cut_day": 15},
            "is_active": True,
        }],
        "expenses": [{
            "id": "exp-1",
            "user_id": "user-1",
            "installment_plan_id": "plan-1",
            "billing_period": "2026-05",
        }],
    })

    generated = generate_installment_expenses(supabase, "user-1")

    assert generated == 0
    assert len(supabase.tables["expenses"]) == 1


def test_installment_respects_number_of_installments():
    supabase = FakeSupabase({
        "installment_plans": [{
            "id": "plan-1",
            "user_id": "user-1",
            "card_id": "card-1",
            "name": "Laptop",
            "monthly_amount": 500,
            "installments": 3,
            "start_period": "2026-05",
            "category": "Tecnología",
            "credit_cards": {"cut_day": 15},
            "is_active": True,
        }],
        "expenses": [],
    })

    generated = generate_installment_expenses(supabase, "user-1")

    assert generated == 3
    assert len(supabase.tables["expenses"]) == 3

from datetime import date, timedelta

from app.core.income_projection import ensure_weekly_income_projections


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.pending_insert = None
        self.pending_update = None

    def select(self, fields):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def gte(self, field, value):
        self.filters.append((field, ("gte", value)))
        return self

    def lte(self, field, value):
        self.filters.append((field, ("lte", value)))
        return self

    def insert(self, payload):
        self.pending_insert = payload
        return self

    def update(self, payload):
        self.pending_update = payload
        return self

    def execute(self):
        rows = self.client.tables.get(self.table_name, [])

        if self.pending_insert is not None:
            next_row = {"id": f"new-{len(rows)+1}", **self.pending_insert}
            rows.append(next_row)
            self.client.tables[self.table_name] = rows
            return Result([next_row])

        def match(row):
            for field, value in self.filters:
                if isinstance(value, tuple):
                    op, comp = value
                    row_val = row.get(field)
                    if op == "gte" and str(row_val) < str(comp):
                        return False
                    if op == "lte" and str(row_val) > str(comp):
                        return False
                elif row.get(field) != value:
                    return False
            return True

        matched = [row for row in rows if match(row)]

        if self.pending_update is not None:
            for row in matched:
                row.update(self.pending_update)
            return Result(matched)

        return Result(matched)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return Query(self, name)


def _friday_of_current_week():
    today = date.today()
    delta = (4 - today.weekday()) % 7
    return today + timedelta(days=delta)


def test_creates_projected_payroll_when_missing():
    payday = _friday_of_current_week()
    supabase = FakeSupabase({"incomes": []})

    rule = {"weekly_amount": 5100, "payday_weekday": 4, "source_label": "Nomina semanal"}
    ensure_weekly_income_projections(supabase, "user-1", payday, payday, rule)

    assert len(supabase.tables["incomes"]) == 1
    assert supabase.tables["incomes"][0]["is_projected"] is True
    assert supabase.tables["incomes"][0]["amount"] == 5100


def test_reconfigures_future_projected_amount():
    payday = _friday_of_current_week()
    supabase = FakeSupabase(
        {
            "incomes": [
                {
                    "id": "inc-1",
                    "user_id": "user-1",
                    "source": "Nomina semanal",
                    "amount": 5100,
                    "income_date": payday.isoformat(),
                    "is_projected": True,
                }
            ]
        }
    )

    rule = {"weekly_amount": 6200, "payday_weekday": 4, "source_label": "Nomina semanal"}
    ensure_weekly_income_projections(supabase, "user-1", payday, payday, rule)

    assert supabase.tables["incomes"][0]["amount"] == 6200


def test_keeps_manual_override_amount():
    payday = _friday_of_current_week()
    supabase = FakeSupabase(
        {
            "incomes": [
                {
                    "id": "inc-1",
                    "user_id": "user-1",
                    "source": "Nomina semanal",
                    "amount": 7000,
                    "income_date": payday.isoformat(),
                    "is_projected": False,
                }
            ]
        }
    )

    rule = {"weekly_amount": 5100, "payday_weekday": 4, "source_label": "Nomina semanal"}
    ensure_weekly_income_projections(supabase, "user-1", payday, payday, rule)

    assert supabase.tables["incomes"][0]["amount"] == 7000

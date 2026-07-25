from datetime import date
from dateutil.relativedelta import relativedelta

MAX_MONTHS = 36


def build_periods(today: date, months: int) -> list:
    """Lista de periodos 'YYYY-MM' ascendente, terminando en el mes de `today`."""
    months = max(1, min(months, MAX_MONTHS))
    return [(today - relativedelta(months=i)).strftime("%Y-%m") for i in range(months - 1, -1, -1)]


def build_monthly_series(periods: list, expenses: list, incomes: list) -> dict:
    """
    Agrega gastos e ingresos por periodo y calcula flujo neto y tasa de ahorro.

    expenses: filas con `billing_period` y `amount` (y opcionalmente `category`)
    incomes:  filas con `income_date` (YYYY-MM-DD) y `amount`
    """
    expense_by_period = {p: 0 for p in periods}
    for e in expenses:
        p = e.get("billing_period")
        if p in expense_by_period:
            expense_by_period[p] += e["amount"]

    income_by_period = {p: 0 for p in periods}
    for inc in incomes:
        p = inc["income_date"][:7]
        if p in income_by_period:
            income_by_period[p] += inc["amount"]

    income_amounts = [round(income_by_period[p], 2) for p in periods]
    expense_amounts = [round(expense_by_period[p], 2) for p in periods]
    net_amounts = [round(income_by_period[p] - expense_by_period[p], 2) for p in periods]
    savings_rate = [
        round((income_by_period[p] - expense_by_period[p]) / income_by_period[p] * 100, 1)
        if income_by_period[p] > 0 else 0
        for p in periods
    ]

    category_totals = {}
    for e in expenses:
        if e.get("billing_period") not in expense_by_period:
            continue
        cat = e.get("category") or "Otro"
        category_totals[cat] = round(category_totals.get(cat, 0) + e["amount"], 2)

    total_income = round(sum(income_amounts), 2)
    total_expenses = round(sum(expense_amounts), 2)
    total_net = round(total_income - total_expenses, 2)
    avg_savings_rate = round(total_net / total_income * 100, 1) if total_income > 0 else 0

    return {
        "income_amounts": income_amounts,
        "expense_amounts": expense_amounts,
        "net_amounts": net_amounts,
        "savings_rate": savings_rate,
        "category_totals": category_totals,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "total_net": total_net,
        "avg_savings_rate": avg_savings_rate,
    }

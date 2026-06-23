from datetime import date, timedelta


def month_bounds(period: str) -> tuple[date, date]:
    year, month = map(int, period.split("-"))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def calculate_net_cashflow(total_income: float, total_expenses: float) -> float:
    return round(total_income - total_expenses, 2)


def calculate_30d_projection(projected_income: float, projected_expenses: float) -> dict:
    net = round(projected_income - projected_expenses, 2)
    return {
        "income_30d": round(projected_income, 2),
        "expenses_30d": round(projected_expenses, 2),
        "net_30d": net,
        "is_negative": net < 0,
    }

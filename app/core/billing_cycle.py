from datetime import date
from dateutil.relativedelta import relativedelta
from app.core.clock import today as get_today
import calendar

def get_billing_period(expense_date: date, cut_day: int) -> str:
    """
    Asigna el gasto al periodo correcto según la fecha de corte.
    
    Regla:
      día_gasto <= día_corte  → periodo mes actual   (ej: "2025-06")
      día_gasto >  día_corte  → periodo mes siguiente (ej: "2025-07")
    """
    if expense_date.day <= cut_day:
        period = expense_date
    else:
        period = expense_date + relativedelta(months=1)
    return period.strftime("%Y-%m")


def get_payment_due_date(billing_period: str, cut_day: int, payment_due_day: int) -> date:
    """
    Calcula la fecha límite de pago para un periodo.
    
    Ejemplo: periodo "2025-06", corte día 15, pago día 10
      → Fecha de corte: 15 Jun → Fecha límite pago: 10 Jul
    """
    year, month = map(int, billing_period.split("-"))
    cut_date = date(year, month, min(cut_day, calendar.monthrange(year, month)[1]))
    payment_month = cut_date + relativedelta(months=1)
    max_day = calendar.monthrange(payment_month.year, payment_month.month)[1]
    return payment_month.replace(day=min(payment_due_day, max_day))


def get_next_due_dates(cut_day: int, payment_due_day: int, today: date, cycles_ahead: int = 3) -> list[dict]:
    """
    Devuelve los próximos `cycles_ahead` ciclos de pago de una tarjeta, ordenados
    por fecha de pago, incluyendo el ciclo ya cerrado que aún no vence
    (is_open=False) y los ciclos que todavía están acumulando gastos
    (is_open=True, cut_date > today).
    """
    candidates = []
    for delta in range(-3, cycles_ahead + 2):
        candidate_month = today + relativedelta(months=delta)
        max_day = calendar.monthrange(candidate_month.year, candidate_month.month)[1]
        cut_date = date(candidate_month.year, candidate_month.month, min(cut_day, max_day))
        billing_period = cut_date.strftime("%Y-%m")
        due_date = get_payment_due_date(billing_period, cut_day, payment_due_day)
        if due_date < today:
            continue
        candidates.append({
            "billing_period": billing_period,
            "cut_date": cut_date,
            "due_date": due_date,
            "days_until_due": (due_date - today).days,
            "is_open": cut_date > today,
        })

    seen = set()
    unique = []
    for c in sorted(candidates, key=lambda x: x["due_date"]):
        if c["billing_period"] in seen:
            continue
        seen.add(c["billing_period"])
        unique.append(c)
    return unique[:cycles_ahead]


def get_current_period_summary(cut_day: int, payment_due_day: int) -> dict:
    """
    Devuelve info del periodo actual para mostrar en el dashboard.
    """
    today = get_today()
    current_period = get_billing_period(today, cut_day)
    due_date = get_payment_due_date(current_period, cut_day, payment_due_day)
    days_until_due = (due_date - today).days

    return {
        "current_period": current_period,
        "payment_due_date": due_date.strftime("%d %b %Y"),
        "days_until_due": days_until_due,
        "is_urgent": days_until_due <= 5,
    }
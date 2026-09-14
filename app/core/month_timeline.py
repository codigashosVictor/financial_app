from datetime import date, datetime, timedelta

from app.core.net_worth import latest_balance_by_owner


def _to_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def get_liquid_balance(account_balances: list) -> float:
    """
    Suma el último saldo conocido por cuenta. El llamador debe pasar solo
    los snapshots de cuentas ya marcadas como `is_liquid=True`.
    """
    return round(sum(latest_balance_by_owner(account_balances, "account_id").values()), 2)


def build_cash_events(income_rows: list, card_due_events: list, today: date, horizon_end: date) -> list[dict]:
    """
    Combina ingresos (+) y pagos de tarjeta pendientes (-) en una lista
    cronológica de eventos de efectivo dentro del horizonte [today, horizon_end].
    """
    events = []

    for inc in income_rows:
        inc_date = _to_date(inc["income_date"])
        if today <= inc_date <= horizon_end:
            events.append({
                "date": inc_date,
                "type": "income",
                "label": inc.get("source") or "Ingreso",
                "amount": round(inc["amount"], 2),
                "estimated": False,
            })

    for ev in card_due_events:
        due_date = ev["due_date"]
        if today <= due_date <= horizon_end:
            events.append({
                "date": due_date,
                "type": "card_due",
                "label": ev["card_name"],
                "amount": -round(ev["amount"], 2),
                "estimated": ev.get("estimated", False),
            })

    events.sort(key=lambda e: e["date"])
    return events


def build_daily_balance(starting_balance: float, events: list, today: date, horizon_end: date) -> dict:
    """
    Construye el saldo proyectado día a día desde `today` hasta `horizon_end`,
    aplicando los eventos de efectivo en su fecha correspondiente.
    """
    events_by_date: dict = {}
    for e in events:
        events_by_date.setdefault(e["date"], []).append(e)

    dates = []
    balances = []
    running = starting_balance
    current = today
    while current <= horizon_end:
        for e in events_by_date.get(current, []):
            running += e["amount"]
        dates.append(current.isoformat())
        balances.append(round(running, 2))
        current += timedelta(days=1)

    if balances:
        lowest_idx = min(range(len(balances)), key=lambda i: balances[i])
        lowest_point = {"date": dates[lowest_idx], "balance": balances[lowest_idx]}
    else:
        lowest_point = None

    return {
        "dates": dates,
        "balances": balances,
        "lowest_point": lowest_point,
        "end_balance": balances[-1] if balances else round(starting_balance, 2),
    }

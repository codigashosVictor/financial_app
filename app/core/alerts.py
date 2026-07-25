from datetime import date
from dateutil.relativedelta import relativedelta
from app.core.billing_cycle import get_payment_due_date
from app.core.clock import today as get_today

PAYMENT_ALERT_DAYS = {0, 1, 3, 7}
BUDGET_WARNING_PCT = 80


def _payment_copy(name: str, days_left: int, due: date, total: float):
    if days_left == 0:
        return f"⚠️ Pago HOY — {name}", f"Vence hoy. Total a pagar: ${total:,.2f}", True
    if days_left == 1:
        return f"🔴 Pago MAÑANA — {name}", f"Tienes 1 día. Total: ${total:,.2f}", True
    if days_left == 3:
        return f"🟡 Pago en 3 días — {name}", f"Vence el {due.strftime('%d %b')}. Total: ${total:,.2f}", False
    return f"📅 Pago en 1 semana — {name}", f"Vence el {due.strftime('%d %b')}. Total: ${total:,.2f}", False


def build_payment_alerts(cards: list, expense_totals: dict, today: date = None) -> list:
    """
    cards: filas de credit_cards (id, name, cut_day, payment_due_day)
    expense_totals: {(card_id, period): total_gastado}
    """
    today = today or get_today()
    alerts = []

    for card in cards:
        for delta in (-1, 0):
            candidate = today + relativedelta(months=delta)
            period = candidate.strftime("%Y-%m")
            due = get_payment_due_date(period, card["cut_day"], card["payment_due_day"])
            days_left = (due - today).days

            if days_left not in PAYMENT_ALERT_DAYS:
                continue

            total = expense_totals.get((card["id"], period), 0)
            title, body, urgent = _payment_copy(card["name"], days_left, due, total)
            alerts.append({
                "title": title,
                "body": body,
                "tag": f"payment-{card['id']}-{period}",
                "url": "/",
                "urgent": urgent,
            })
            break  # solo una alerta por tarjeta

    return alerts


def build_subscription_alerts(subscriptions: list, today: date = None) -> list:
    """subscriptions: filas activas con name, amount, charge_day."""
    today = today or get_today()
    day_subs = [s for s in subscriptions if s["charge_day"] == today.day]
    if not day_subs:
        return []

    names = ", ".join(s["name"] for s in day_subs[:3])
    total = sum(s["amount"] for s in day_subs)
    return [{
        "title": "🔄 Cargos de hoy",
        "body": f"{names} — ${total:,.2f} en total",
        "tag": f"subs-{today.isoformat()}",
        "url": "/subscriptions/",
        "urgent": False,
    }]


def build_budget_alerts(budgets: list, spent_by_category: dict) -> list:
    """
    budgets: filas de budgets del periodo actual (category, amount)
    spent_by_category: {category: total_gastado} del mismo periodo
    """
    alerts = []

    for b in budgets:
        budgeted = b["amount"]
        if budgeted <= 0:
            continue

        cat = b["category"]
        spent = spent_by_category.get(cat, 0)
        pct = spent / budgeted * 100

        if spent > budgeted:
            alerts.append({
                "title": f"🚨 Presupuesto excedido — {cat}",
                "body": f"Gastaste ${spent:,.2f} de ${budgeted:,.2f} ({pct:.0f}%)",
                "tag": f"budget-over-{cat}",
                "url": "/budgets/",
                "urgent": True,
            })
        elif pct >= BUDGET_WARNING_PCT:
            alerts.append({
                "title": f"🟡 Presupuesto casi agotado — {cat}",
                "body": f"Gastaste ${spent:,.2f} de ${budgeted:,.2f} ({pct:.0f}%)",
                "tag": f"budget-warning-{cat}",
                "url": "/budgets/",
                "urgent": False,
            })

    return alerts


def fetch_expense_totals_for_cards(supabase, user_id: str, cards: list, today: date = None) -> dict:
    """Totales de gasto para el periodo actual y el anterior de cada tarjeta."""
    today = today or get_today()
    totals = {}
    for card in cards:
        for delta in (-1, 0):
            period = (today + relativedelta(months=delta)).strftime("%Y-%m")
            exp_res = supabase.table("expenses").select("amount")\
                .eq("user_id", user_id).eq("card_id", card["id"]).eq("billing_period", period).execute()
            totals[(card["id"], period)] = sum(e["amount"] for e in (exp_res.data or []))
    return totals


def fetch_spent_by_category(supabase, user_id: str, period: str) -> dict:
    expenses_res = supabase.table("expenses").select("category, amount")\
        .eq("user_id", user_id).eq("billing_period", period).execute()
    spent_map = {}
    for exp in (expenses_res.data or []):
        cat = exp.get("category") or "Otro"
        spent_map[cat] = spent_map.get(cat, 0) + exp["amount"]
    return spent_map


def build_alerts_for_user(supabase, user_id: str, today: date = None) -> list:
    """Junta todas las alertas (pagos, suscripciones, presupuesto) de un usuario."""
    today = today or get_today()
    period = today.strftime("%Y-%m")

    cards = supabase.table("credit_cards").select("*")\
        .eq("user_id", user_id).eq("is_active", True).execute().data or []
    subs = supabase.table("subscriptions").select("*")\
        .eq("user_id", user_id).eq("is_active", True).execute().data or []
    budgets = supabase.table("budgets").select("*")\
        .eq("user_id", user_id).eq("period", period).execute().data or []

    return (
        build_payment_alerts(cards, fetch_expense_totals_for_cards(supabase, user_id, cards, today), today) +
        build_subscription_alerts(subs, today) +
        build_budget_alerts(budgets, fetch_spent_by_category(supabase, user_id, period))
    )

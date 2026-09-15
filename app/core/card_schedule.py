from datetime import date

from dateutil.relativedelta import relativedelta

from app.core.billing_cycle import get_next_due_dates
from app.core.card_payments import calculate_pending_balance


def build_card_due_events(
    supabase, user_id: str, cards: list, today: date, horizon_end: date, cycles_ahead: int = 3
) -> list[dict]:
    """
    Para cada tarjeta activa, calcula sus próximos ciclos de pago dentro del
    horizonte y su monto pendiente real (gastos - pagos ya hechos). Si el
    ciclo aún está acumulando gastos (is_open), el monto es una estimación
    parcial y se marca como `estimated`.
    """
    events = []
    for card in cards:
        due_dates = get_next_due_dates(card["cut_day"], card["payment_due_day"], today, cycles_ahead=cycles_ahead)
        for entry in due_dates:
            if entry["due_date"] > horizon_end:
                continue

            period = entry["billing_period"]
            exp_res = supabase.table("expenses")\
                .select("amount")\
                .eq("user_id", user_id)\
                .eq("card_id", card["id"])\
                .eq("billing_period", period)\
                .execute()
            pay_res = supabase.table("card_payments")\
                .select("amount")\
                .eq("user_id", user_id)\
                .eq("card_id", card["id"])\
                .eq("billing_period", period)\
                .execute()

            total_expenses = sum(e["amount"] for e in (exp_res.data or []))
            total_paid = sum(p["amount"] for p in (pay_res.data or []))
            pending = calculate_pending_balance(total_expenses, total_paid)["pending"]

            events.append({
                "card_id": card["id"],
                "card_name": card["name"],
                "billing_period": period,
                "due_date": entry["due_date"],
                "amount": round(max(pending, 0), 2),
                "is_open": entry["is_open"],
                "estimated": entry["is_open"],
            })
    return events


def select_upcoming_payment_per_card(card_due_events: list) -> list:
    """
    De los varios ciclos calculados por tarjeta (build_card_due_events con
    cycles_ahead>1), elige el más relevante para mostrar como "próximo pago":
    el más próximo que todavía tenga saldo pendiente (amount > 0). Si el
    usuario ya pagó/sobrepagó todos los ciclos dentro del horizonte, cae de
    vuelta al ciclo con fecha de vencimiento más cercana (para mostrar que no
    debe nada por ahora), en vez de un $0 que en realidad esconde un cargo
    real en el siguiente ciclo.
    """
    by_card = {}
    for event in card_due_events:
        by_card.setdefault(event["card_id"], []).append(event)

    selected = []
    for events in by_card.values():
        events_sorted = sorted(events, key=lambda e: e["due_date"])
        pick = next((e for e in events_sorted if e["amount"] > 0), events_sorted[0])
        selected.append(pick)
    return selected


def get_current_cards_pending_total(supabase, user_id: str, cards: list, today: date) -> float:
    """
    Suma lo que realmente se debe hoy en todas las tarjetas activas, usando
    el mismo criterio que "Próximos pagos": el ciclo más próximo por tarjeta
    que aún tenga saldo pendiente (o $0 si ya está saldado), respetando el
    día de corte real de cada tarjeta — en vez de un mes calendario único o
    el corte de una sola tarjeta, que pueden dar números distintos entre sí.
    """
    horizon_end = today + relativedelta(months=4)
    events = build_card_due_events(supabase, user_id, cards, today, horizon_end, cycles_ahead=3)
    relevant = select_upcoming_payment_per_card(events)
    return round(sum(e["amount"] for e in relevant), 2)

from datetime import date


def _explain(events: list, candidate_date: date, today: date) -> dict | None:
    """
    Encuentra el último evento (ingreso o pago de tarjeta) entre hoy y la
    fecha segura que explica por qué esa fecha ya es segura para comprar.
    Devuelve datos estructurados (no un texto ya armado) para que quien
    consuma el resultado pueda formatear la fecha a su propio estilo.
    """
    relevant = [e for e in events if today < e["date"] <= candidate_date]
    if not relevant:
        return None
    last = max(relevant, key=lambda e: e["date"])
    return {"type": last["type"], "label": last["label"], "date": last["date"].isoformat()}


def find_safe_purchase_date(
    daily_balance: dict, cost: float, target_date: date, today: date, horizon_end: date, events: list | None = None
) -> dict:
    """
    Determina la fecha más próxima (desde `target_date`, nunca antes de hoy)
    en la que restar `cost` al saldo proyectado no deja ningún día futuro
    en negativo dentro del horizonte.
    """
    dates = daily_balance["dates"]
    balances = daily_balance["balances"]
    if not dates:
        return {"status": "no_data"}

    date_objs = [date.fromisoformat(d) for d in dates]

    baseline_min = min(balances)
    if baseline_min < 0:
        return {"status": "already_negative", "floor_balance": baseline_min}

    start_from = max(target_date, today)
    start_idx = next((i for i, d in enumerate(date_objs) if d >= start_from), None)
    if start_idx is None:
        return {"status": "no_safe_date_in_horizon", "horizon_end": horizon_end.isoformat()}

    best_floor = None
    for candidate_idx in range(start_idx, len(date_objs)):
        candidate_date = date_objs[candidate_idx]
        simulated_floor = min(
            b - cost if d >= candidate_date else b
            for d, b in zip(date_objs, balances)
        )
        if best_floor is None or simulated_floor > best_floor:
            best_floor = simulated_floor
        if simulated_floor >= 0:
            result = {
                "status": "ok",
                "can_buy_now": candidate_date == today,
                "safe_date": candidate_date.isoformat(),
                "floor_after_purchase": round(simulated_floor, 2),
                "reason": None,
            }
            if events is not None and candidate_date > today:
                result["reason"] = _explain(events, candidate_date, today)
            return result

    return {
        "status": "no_safe_date_in_horizon",
        "horizon_end": horizon_end.isoformat(),
        "shortfall": round(-best_floor, 2) if best_floor is not None else None,
    }


def build_purchase_breakdown(
    starting_balance: float, cash_events: list, cost: float, horizon_end: date
) -> dict:
    """
    Arma el desglose cronológico (efectivo de partida, cada pago de tarjeta,
    cada ingreso) hasta el fin del horizonte, con el saldo corrido después de
    cada evento — para poder mostrar "una por una" el porqué del veredicto
    de find_safe_purchase_date, sin recalcular esa lógica.
    """
    lines = []
    running = starting_balance
    for event in sorted(cash_events, key=lambda e: e["date"]):
        running += event["amount"]
        lines.append({
            "date": event["date"].isoformat(),
            "type": event["type"],
            "label": event["label"],
            "amount": event["amount"],
            "balance_after": round(running, 2),
        })

    end_balance = round(running, 2)
    return {
        "starting_balance": round(starting_balance, 2),
        "horizon_end": horizon_end.isoformat(),
        "lines": lines,
        "end_balance": end_balance,
        "end_balance_after_purchase": round(end_balance - cost, 2),
    }

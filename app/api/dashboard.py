from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from app.core.billing_cycle import get_billing_period, get_payment_due_date
from datetime import date
import calendar
from dateutil.relativedelta import relativedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@router.get("/data")
async def dashboard_data(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    supabase = get_supabase(user["access_token"])
    today    = date.today()
    import calendar as cal

    # ── Periodo seleccionado (default: periodo activo de hoy) ────
    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
    cards = cards_res.data or []

    # Periodo por default = donde caen los gastos de hoy
    default_period = get_billing_period(today, cards[0]["cut_day"]) \
                     if cards else today.strftime("%Y-%m")

    selected_period = request.query_params.get("period", default_period)

    # ── Próximos pagos (siempre basados en fecha real, no en periodo) ──
    upcoming_payments = []
    for card in cards:
        for delta in [-2, -1, 0, 1]:
            candidate = today + relativedelta(months=delta)
            max_day   = cal.monthrange(candidate.year, candidate.month)[1]
            cut_date  = date(candidate.year, candidate.month,
                             min(card["cut_day"], max_day))
            next_m    = cut_date + relativedelta(months=1)
            max_day_n = cal.monthrange(next_m.year, next_m.month)[1]
            pay_date  = date(next_m.year, next_m.month,
                             min(card["payment_due_day"], max_day_n))
            days = (pay_date - today).days
            if days < 0:
                continue
            pay_period = cut_date.strftime("%Y-%m")
            exp_res = supabase.table("expenses")\
                .select("amount")\
                .eq("user_id", user["id"])\
                .eq("card_id", card["id"])\
                .eq("billing_period", pay_period)\
                .execute()
            total = sum(e["amount"] for e in (exp_res.data or []))
            upcoming_payments.append({
                "card":     card["name"],
                "due_date": pay_date.strftime("%d %b %Y"),
                "days":     days,
                "amount":   round(total, 2),
                "period":   pay_period,
                "urgent":   days <= 5,
            })
            break
    upcoming_payments.sort(key=lambda x: x["days"])
    next_payment = upcoming_payments[0] if upcoming_payments else None

    # ── Gastos últimos 7 meses ───────────────────────────────────
    seven_months_ago = (today - relativedelta(months=6)).strftime("%Y-%m")
    expenses_res = supabase.table("expenses")\
        .select("*")\
        .eq("user_id", user["id"])\
        .gte("billing_period", seven_months_ago)\
        .order("expense_date", desc=True)\
        .execute()
    all_expenses = expenses_res.data or []

    # Gastos del periodo SELECCIONADO
    current_expenses = [e for e in all_expenses
                        if e.get("billing_period") == selected_period]
    total_month      = sum(e["amount"] for e in current_expenses)

    # ── Proyección (solo tiene sentido en el periodo activo) ─────
    projection = _calculate_projection(today, selected_period, current_expenses) \
                 if selected_period == default_period else {}

    # ── Comparativa ──────────────────────────────────────────────
    # Mes anterior al seleccionado
    sel_year, sel_month = map(int, selected_period.split("-"))
    prev_date    = date(sel_year, sel_month, 1) - relativedelta(months=1)
    prev_period  = prev_date.strftime("%Y-%m")
    prev_expenses = [e for e in all_expenses
                     if e.get("billing_period") == prev_period]

    # Si prev no está en los 7 meses, consultar aparte
    if not prev_expenses and prev_period < seven_months_ago:
        prev_res = supabase.table("expenses")\
            .select("*")\
            .eq("user_id", user["id"])\
            .eq("billing_period", prev_period)\
            .execute()
        prev_expenses = prev_res.data or []

    comparison = _calculate_comparison(current_expenses, prev_expenses)

    # ── Flujo mensual 6 meses ────────────────────────────────────
    monthly_flow = {}
    for i in range(5, -1, -1):
        m = (today - relativedelta(months=i)).strftime("%Y-%m")
        monthly_flow[m] = 0
    for exp in all_expenses:
        p = exp.get("billing_period", "")
        if p in monthly_flow:
            monthly_flow[p] += exp["amount"]

    # ── Categorías ───────────────────────────────────────────────
    cat_totals = {}
    for exp in current_expenses:
        cat = exp.get("category", "Otro")
        cat_totals[cat] = cat_totals.get(cat, 0) + exp["amount"]

    # ── Total por tarjeta ────────────────────────────────────────
    card_totals = {}
    for exp in current_expenses:
        cid = exp.get("card_id")
        card_totals[cid] = card_totals.get(cid, 0) + exp["amount"]

    cards_with_totals = []
    for card in cards:
        card["total"] = card_totals.get(card["id"], 0)
        cards_with_totals.append(card)

    return JSONResponse({
        "cards":             cards_with_totals,
        "recent_expenses":   all_expenses[:8],
        "total_month":       total_month,
        "selected_period":   selected_period,
        "default_period":    default_period,
        "is_current":        selected_period == default_period,
        "days_until_due":    next_payment["days"] if next_payment else 0,
        "next_due_date":     next_payment["due_date"] if next_payment else "",
        "urgent_card":       next_payment["card"] if next_payment else "",
        "upcoming_payments": upcoming_payments,
        "monthly_flow": {
            "periods": list(monthly_flow.keys()),
            "amounts": list(monthly_flow.values()),
        },
        "category_totals":   cat_totals,
        "projection":        projection,
        "comparison":        comparison,
    })
    
def _calculate_projection(today: date, period: str, expenses: list) -> dict:
    """
    Proyecta el gasto total al cierre del periodo basado
    en el promedio diario de los gastos registrados.
    """
    if not expenses:
        return {"projected": 0, "daily_avg": 0, "days_elapsed": 0,
                "days_total": 0, "pct_period": 0}

    year, month = map(int, period.split("-"))
    days_in_month = calendar.monthrange(year, month)[1]

    # Días transcurridos en el periodo (desde día 1 hasta hoy o fin de mes)
    period_start  = date(year, month, 1)
    period_end    = date(year, month, days_in_month)
    days_elapsed  = min((today - period_start).days + 1, days_in_month)

    total_spent   = sum(e["amount"] for e in expenses)
    daily_avg     = total_spent / days_elapsed if days_elapsed > 0 else 0
    projected     = daily_avg * days_in_month
    pct_period    = round((days_elapsed / days_in_month) * 100)

    return {
        "projected":    round(projected, 2),
        "daily_avg":    round(daily_avg, 2),
        "days_elapsed": days_elapsed,
        "days_total":   days_in_month,
        "pct_period":   pct_period,
    }


def _calculate_comparison(current: list, previous: list) -> dict:
    """
    Compara gastos por categoría entre el periodo actual y el anterior.
    Devuelve top categorías que subieron y bajaron.
    """
    def by_category(expenses):
        totals = {}
        for e in expenses:
            cat = e.get("category", "Otro")
            totals[cat] = totals.get(cat, 0) + e["amount"]
        return totals

    cur_cats  = by_category(current)
    prev_cats = by_category(previous)

    all_cats  = set(cur_cats) | set(prev_cats)
    changes   = []

    for cat in all_cats:
        cur_amt  = cur_cats.get(cat, 0)
        prev_amt = prev_cats.get(cat, 0)

        if prev_amt == 0 and cur_amt == 0:
            continue

        if prev_amt == 0:
            pct = 100.0
        else:
            pct = ((cur_amt - prev_amt) / prev_amt) * 100

        changes.append({
            "category":  cat,
            "current":   round(cur_amt, 2),
            "previous":  round(prev_amt, 2),
            "pct_change": round(pct, 1),
            "direction": "up" if pct > 0 else "down" if pct < 0 else "equal",
        })

    changes.sort(key=lambda x: abs(x["pct_change"]), reverse=True)

    total_cur  = sum(e["amount"] for e in current)
    total_prev = sum(e["amount"] for e in previous)
    total_pct  = round(((total_cur - total_prev) / total_prev * 100)
                        if total_prev > 0 else 0, 1)

    return {
        "changes":    changes[:6],   # top 6 categorías con más movimiento
        "total_current":  round(total_cur, 2),
        "total_previous": round(total_prev, 2),
        "total_pct_change": total_pct,
        "total_direction": "up" if total_pct > 0 else "down" if total_pct < 0 else "equal",
    }
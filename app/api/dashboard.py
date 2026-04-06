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

    supabase  = get_supabase(user["access_token"])
    today     = date.today()

    # ── Tarjetas activas ─────────────────────────────────────────
    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
    cards = cards_res.data or []

    # ── Periodo más urgente ──────────────────────────────────────
    best_period   = today.strftime("%Y-%m")
    best_days     = 9999
    urgent_card   = ""
    next_due_date = ""

    for card in cards:
        for delta in [-1, 0, 1]:
            candidate = today + relativedelta(months=delta)
            period    = candidate.strftime("%Y-%m")
            due       = get_payment_due_date(period, card["cut_day"], card["payment_due_day"])
            days      = (due - today).days
            if 0 <= days < best_days:
                best_days     = days
                best_period   = period
                urgent_card   = card["name"]
                next_due_date = due.strftime("%d %b %Y")

    if best_days == 9999:
        best_period   = today.strftime("%Y-%m")
        best_days     = 0
        next_due_date = ""
        urgent_card   = ""

    # ── Gastos últimos 7 meses (6 + actual) ─────────────────────
    seven_months_ago = (today - relativedelta(months=6)).strftime("%Y-%m")
    expenses_res = supabase.table("expenses")\
        .select("*")\
        .eq("user_id", user["id"])\
        .gte("billing_period", seven_months_ago)\
        .order("expense_date", desc=True)\
        .execute()
    all_expenses = expenses_res.data or []

    # ── Gastos del periodo urgente ───────────────────────────────
    current_expenses = [e for e in all_expenses if e.get("billing_period") == best_period]
    total_month      = sum(e["amount"] for e in current_expenses)

    # ── Proyección del mes ───────────────────────────────────────
    projection = _calculate_projection(today, best_period, current_expenses)

    # ── Comparativa mes a mes ────────────────────────────────────
    prev_period    = (today - relativedelta(months=1)).strftime("%Y-%m")
    prev_expenses  = [e for e in all_expenses if e.get("billing_period") == prev_period]
    comparison     = _calculate_comparison(current_expenses, prev_expenses)

    # ── Flujo mensual 6 meses ────────────────────────────────────
    monthly_flow = {}
    for i in range(5, -1, -1):
        m = (today - relativedelta(months=i)).strftime("%Y-%m")
        monthly_flow[m] = 0
    for exp in all_expenses:
        p = exp.get("billing_period", "")
        if p in monthly_flow:
            monthly_flow[p] += exp["amount"]

    # ── Gastos por categoría ─────────────────────────────────────
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
        "cards":           cards_with_totals,
        "recent_expenses": all_expenses[:8],
        "total_month":     total_month,
        "days_until_due":  best_days,
        "next_due_date":   next_due_date,
        "urgent_card":     urgent_card,
        "current_period":  best_period,
        "monthly_flow": {
            "periods": list(monthly_flow.keys()),
            "amounts": list(monthly_flow.values()),
        },
        "category_totals": cat_totals,
        "projection":      projection,
        "comparison":      comparison,
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
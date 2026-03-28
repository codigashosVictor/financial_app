from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from app.core.billing_cycle import get_billing_period, get_payment_due_date
from datetime import date
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
    today = date.today()

    # Tarjetas activas
    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
    cards = cards_res.data or []

    # ── Encontrar el periodo más urgente ────────────────────────
    # Para cada tarjeta calculamos TODOS los periodos posibles:
    # el periodo del mes pasado (si aún no venció su pago),
    # el periodo actual y el próximo — y nos quedamos con el
    # que tenga la fecha de pago más próxima >= hoy.
    best_period    = today.strftime("%Y-%m")
    best_due       = None
    best_days      = 9999
    urgent_card    = ""
    next_due_date  = ""

    for card in cards:
        # Revisar los últimos 2 periodos + el siguiente
        # para no perder pagos que aún no vencen
        for delta in [-1, 0, 1]:
            candidate_date  = today + relativedelta(months=delta)
            period          = candidate_date.strftime("%Y-%m")
            due             = get_payment_due_date(
                                period,
                                card["cut_day"],
                                card["payment_due_day"]
                              )
            days = (due - today).days

            # Solo considerar fechas futuras o de hoy
            # y que sean más urgentes que la mejor encontrada
            if days >= 0 and days < best_days:
                best_days     = days
                best_period   = period
                best_due      = due
                urgent_card   = card["name"]
                next_due_date = due.strftime("%d %b %Y")

    # Si todas vencieron, mostrar el periodo actual
    if best_days == 9999:
        best_period   = today.strftime("%Y-%m")
        best_days     = 0
        next_due_date = ""
        urgent_card   = ""

    # ── Gastos últimos 6 meses ───────────────────────────────────
    six_months_ago = (today - relativedelta(months=6)).strftime("%Y-%m")
    expenses_res = supabase.table("expenses")\
        .select("*")\
        .eq("user_id", user["id"])\
        .gte("billing_period", six_months_ago)\
        .order("expense_date", desc=True)\
        .execute()
    all_expenses = expenses_res.data or []

    # Gastos del periodo más urgente
    current_expenses = [e for e in all_expenses if e.get("billing_period") == best_period]
    total_month      = sum(e["amount"] for e in current_expenses)

    # ── Flujo mensual 6 meses ────────────────────────────────────
    monthly_flow = {}
    for i in range(5, -1, -1):
        m = (today - relativedelta(months=i)).strftime("%Y-%m")
        monthly_flow[m] = 0
    for exp in all_expenses:
        p = exp.get("billing_period", "")
        if p in monthly_flow:
            monthly_flow[p] += exp["amount"]

    # ── Gastos por categoría (periodo urgente) ───────────────────
    cat_totals = {}
    for exp in current_expenses:
        cat = exp.get("category", "Otro")
        cat_totals[cat] = cat_totals.get(cat, 0) + exp["amount"]

    # ── Total por tarjeta (periodo urgente) ──────────────────────
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
    })
    user = request.session.get("user")
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    supabase = get_supabase(user["access_token"])
    today = date.today()

    # Tarjetas activas
    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
    cards = cards_res.data or []

    # Periodo actual y próximo pago (tarjeta con pago más urgente)
    current_period = today.strftime("%Y-%m")
    days_until_due = 999
    next_due_date = ""
    urgent_card = ""

    for card in cards:
        period = get_billing_period(today, card["cut_day"])
        due = get_payment_due_date(period, card["cut_day"], card["payment_due_day"])
        days = (due - today).days
        if days < days_until_due:
            days_until_due = days
            next_due_date = due.strftime("%d %b %Y")
            urgent_card = card["name"]
            current_period = period

    # Gastos últimos 6 meses
    six_months_ago = (today - relativedelta(months=6)).strftime("%Y-%m")
    expenses_res = supabase.table("expenses")\
        .select("*")\
        .eq("user_id", user["id"])\
        .gte("billing_period", six_months_ago)\
        .order("expense_date", desc=True)\
        .execute()
    all_expenses = expenses_res.data or []

    # Gastos del periodo actual
    current_expenses = [e for e in all_expenses if e.get("billing_period") == current_period]
    total_month = sum(e["amount"] for e in current_expenses)

    # Flujo por mes (últimos 6)
    monthly_flow = {}
    for i in range(5, -1, -1):
        m = (today - relativedelta(months=i)).strftime("%Y-%m")
        monthly_flow[m] = 0
    for exp in all_expenses:
        p = exp.get("billing_period", "")
        if p in monthly_flow:
            monthly_flow[p] += exp["amount"]

    # Gastos por categoría (periodo actual)
    cat_totals = {}
    for exp in current_expenses:
        cat = exp.get("category", "Otro")
        cat_totals[cat] = cat_totals.get(cat, 0) + exp["amount"]

    # Total por tarjeta (periodo actual)
    card_totals = {}
    for exp in current_expenses:
        cid = exp.get("card_id")
        card_totals[cid] = card_totals.get(cid, 0) + exp["amount"]

    cards_with_totals = []
    for card in cards:
        card["total"] = card_totals.get(card["id"], 0)
        cards_with_totals.append(card)

    return JSONResponse({
        "cards": cards_with_totals,
        "recent_expenses": all_expenses[:8],
        "total_month": total_month,
        "days_until_due": days_until_due if days_until_due < 999 else 0,
        "next_due_date": next_due_date,
        "urgent_card": urgent_card,
        "current_period": current_period,
        "monthly_flow": {
            "periods": list(monthly_flow.keys()),
            "amounts": list(monthly_flow.values()),
        },
        "category_totals": cat_totals,
    })
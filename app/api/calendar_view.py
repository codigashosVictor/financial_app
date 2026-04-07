from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from app.core.billing_cycle import get_billing_period
from datetime import date
import calendar as cal

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def calendar_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("calendar.html", {
        "request": request, "user": user
    })

@router.get("/data")
async def calendar_data(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    today  = date.today()
    year   = int(request.query_params.get("year",  today.year))
    month  = int(request.query_params.get("month", today.month))

    supabase      = get_supabase(user["access_token"])
    days_in_month = cal.monthrange(year, month)[1]
    first_day     = date(year, month, 1)
    last_day      = date(year, month, days_in_month)

    # ── Gastos del mes (por fecha real del gasto) ────────────────
    expenses_res = supabase.table("expenses")\
        .select("id, merchant, amount, category, expense_date, source")\
        .eq("user_id", user["id"])\
        .gte("expense_date", first_day.isoformat())\
        .lte("expense_date", last_day.isoformat())\
        .order("expense_date")\
        .execute()

    expenses_by_day = {}
    for exp in (expenses_res.data or []):
        d = exp["expense_date"]
        if d not in expenses_by_day:
            expenses_by_day[d] = {"total": 0, "items": [], "count": 0}
        expenses_by_day[d]["total"] += exp["amount"]
        expenses_by_day[d]["count"] += 1
        expenses_by_day[d]["items"].append({
            "merchant": exp.get("merchant") or "Sin nombre",
            "amount":   exp["amount"],
            "category": exp.get("category", "Otro"),
            "source":   exp.get("source", "manual"),
        })
    for d in expenses_by_day:
        expenses_by_day[d]["total"] = round(expenses_by_day[d]["total"], 2)

    # ── Tarjetas: cortes, pagos y montos a pagar ─────────────────
    cards_res = supabase.table("credit_cards")\
        .select("id, name, cut_day, payment_due_day")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .execute()
    cards = cards_res.data or []

    # Necesitamos los gastos de varios periodos para calcular
    # el monto a pagar en cada fecha de pago del mes
    # Traemos gastos de los últimos 3 meses de billing_period
    from dateutil.relativedelta import relativedelta
    two_months_ago = (first_day - relativedelta(months=2)).strftime("%Y-%m")

    all_expenses_res = supabase.table("expenses")\
        .select("amount, billing_period, card_id")\
        .eq("user_id", user["id"])\
        .gte("billing_period", two_months_ago)\
        .execute()
    all_expenses = all_expenses_res.data or []

    card_events = {}

    def add_event(day_key, event):
        if day_key not in card_events:
            card_events[day_key] = []
        card_events[day_key].append(event)

    for card in cards:
        # ── Día de corte ────────────────────────────────────────
        cut_day_num = min(card["cut_day"], days_in_month)
        cut_key     = date(year, month, cut_day_num).isoformat()

        # El periodo que CIERRA en este corte
        # = el billing_period del mes actual si el día <= cut_day
        cut_date   = date(year, month, cut_day_num)
        cut_period = get_billing_period(cut_date, card["cut_day"])

        # Total de gastos que cierran en este corte
        cut_total = sum(
            e["amount"] for e in all_expenses
            if e.get("card_id") == card["id"]
            and e.get("billing_period") == cut_period
        )

        add_event(cut_key, {
            "type":   "cut",
            "label":  f"Corte {card['name']}",
            "card":   card["name"],
            "amount": round(cut_total, 2),
            "period": cut_period,
        })

        # ── Día de pago ─────────────────────────────────────────────
        pay_day_num = min(card["payment_due_day"], days_in_month)
        pay_key     = date(year, month, pay_day_num).isoformat()

        # El pago de este mes corresponde al corte del mes ANTERIOR
        # Corte del mes anterior → periodo que cierra ese corte
        prev_month_date  = date(year, month, 1) - relativedelta(months=1)
        prev_days_in_m   = cal.monthrange(prev_month_date.year, prev_month_date.month)[1]
        prev_cut_day_num = min(card["cut_day"], prev_days_in_m)
        prev_cut_date    = date(prev_month_date.year, prev_month_date.month, prev_cut_day_num)

        # El periodo que cerró ese corte
        # gastos del 4 de marzo al 3 de abril → periodo "2026-03"
        # = el mes donde está la mayoría de los gastos = mes del corte anterior
        pay_period = prev_cut_date.strftime("%Y-%m")

        pay_total = sum(
            e["amount"] for e in all_expenses
            if e.get("card_id") == card["id"]
            and e.get("billing_period") == pay_period
        )

        add_event(pay_key, {
            "type":   "payment",
            "label":  f"Pago {card['name']}",
            "card":   card["name"],
            "amount": round(pay_total, 2),
            "period": pay_period,
        })

    # ── Suscripciones ────────────────────────────────────────────
    subs_res = supabase.table("subscriptions")\
        .select("name, charge_day, amount")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .execute()

    sub_events = {}
    for sub in (subs_res.data or []):
        day     = min(sub["charge_day"], days_in_month)
        sub_key = date(year, month, day).isoformat()
        if sub_key not in sub_events:
            sub_events[sub_key] = []
        sub_events[sub_key].append({
            "name":   sub["name"],
            "amount": sub["amount"],
        })

    # ── Grid del calendario ──────────────────────────────────────
    cal_matrix = cal.monthcalendar(year, month)
    weeks = []
    for week in cal_matrix:
        days = []
        for day_num in week:
            if day_num == 0:
                days.append(None)
                continue
            day_key  = date(year, month, day_num).isoformat()
            day_data = expenses_by_day.get(day_key, {})
            c_events = card_events.get(day_key, [])
            days.append({
                "day":        day_num,
                "date":       day_key,
                "is_today":   day_key == today.isoformat(),
                "is_weekend": date(year, month, day_num).weekday() >= 5,
                "total":      day_data.get("total", 0),
                "count":      day_data.get("count", 0),
                "items":      day_data.get("items", []),
                "cut_events": [e for e in c_events if e["type"] == "cut"],
                "pay_events": [e for e in c_events if e["type"] == "payment"],
                "sub_events": sub_events.get(day_key, []),
            })
        weeks.append(days)

    return JSONResponse({
        "year":        year,
        "month":       month,
        "month_name":  date(year, month, 1).strftime("%B %Y"),
        "weeks":       weeks,
        "today":       today.isoformat(),
        "total_month": round(sum(v["total"] for v in expenses_by_day.values()), 2),
        "expense_days": len(expenses_by_day),
    })
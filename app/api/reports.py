from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.csrf import configure_templates
from app.db.supabase_client import get_supabase
from app.core.reports import build_periods, build_monthly_series
from app.core.clock import today as get_today
from datetime import date

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory="app/templates"))


def require_user(request: Request):
    return request.session.get("user")


@router.get("/", response_class=HTMLResponse)
async def reports_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("reports.html", {"request": request, "user": user})


@router.get("/data")
async def reports_data(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    months = int(request.query_params.get("months", 12))
    today = get_today()
    periods = build_periods(today, months)

    supabase = get_supabase(user["access_token"])

    expenses_res = supabase.table("expenses")\
        .select("amount, category, billing_period")\
        .eq("user_id", user["id"])\
        .gte("billing_period", periods[0])\
        .lte("billing_period", periods[-1])\
        .execute()

    incomes_res = supabase.table("incomes")\
        .select("amount, income_date")\
        .eq("user_id", user["id"])\
        .gte("income_date", f"{periods[0]}-01")\
        .lte("income_date", today.isoformat())\
        .execute()

    series = build_monthly_series(periods, expenses_res.data or [], incomes_res.data or [])

    return JSONResponse({
        "periods": periods,
        **series,
    })

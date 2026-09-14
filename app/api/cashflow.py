from datetime import date

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.affordability import build_purchase_breakdown, find_safe_purchase_date
from app.core.card_schedule import build_card_due_events
from app.core.clock import today as get_today
from app.core.csrf import configure_templates, verify_csrf
from app.core.income_projection import ensure_weekly_income_projections, get_or_create_income_rule
from app.core.month_timeline import build_cash_events, build_daily_balance, get_liquid_balance
from app.db.supabase_client import get_supabase

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory="app/templates"))

DEFAULT_HORIZON_DAYS = 60
SIMULATION_HORIZON_DAYS = 90


def require_user(request: Request):
    return request.session.get("user")


def _build_timeline(supabase, user_id: str, horizon_days: int) -> dict:
    today = get_today()
    horizon_end = today + relativedelta(days=horizon_days)

    payroll_rule = get_or_create_income_rule(supabase, user_id)
    ensure_weekly_income_projections(supabase, user_id, today, horizon_end, payroll_rule)

    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user_id).eq("is_active", True).execute()
    cards = cards_res.data or []

    accounts_res = supabase.table("accounts")\
        .select("id").eq("user_id", user_id).eq("is_active", True).eq("is_liquid", True).execute()
    account_ids = [a["id"] for a in (accounts_res.data or [])]
    account_balances = (
        supabase.table("account_balances").select("*").eq("user_id", user_id).in_("account_id", account_ids).execute().data or []
    ) if account_ids else []
    starting_balance = get_liquid_balance(account_balances)
    has_liquid_accounts = len(account_ids) > 0

    incomes_res = supabase.table("incomes")\
        .select("amount, income_date, source")\
        .eq("user_id", user_id)\
        .gte("income_date", today.isoformat())\
        .lte("income_date", horizon_end.isoformat())\
        .execute()
    income_rows = incomes_res.data or []

    card_due_events = build_card_due_events(supabase, user_id, cards, today, horizon_end)
    cash_events = build_cash_events(income_rows, card_due_events, today, horizon_end)
    daily_balance = build_daily_balance(starting_balance, cash_events, today, horizon_end)

    return {
        "today": today,
        "horizon_end": horizon_end,
        "starting_balance": starting_balance,
        "has_liquid_accounts": has_liquid_accounts,
        "card_due_events": card_due_events,
        "cash_events": cash_events,
        "daily_balance": daily_balance,
    }


@router.get("/", response_class=HTMLResponse)
async def cashflow_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("cashflow/index.html", {"request": request, "user": user})


@router.get("/data")
async def cashflow_data(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    horizon = int(request.query_params.get("horizon", DEFAULT_HORIZON_DAYS))
    supabase = get_supabase(user["access_token"])
    tl = _build_timeline(supabase, user["id"], horizon)

    return JSONResponse({
        "starting_balance": tl["starting_balance"],
        "has_liquid_accounts": tl["has_liquid_accounts"],
        "horizon_days": horizon,
        "daily_balance": tl["daily_balance"],
        "card_events": [
            {
                "card_name": e["card_name"],
                "due_date": e["due_date"].isoformat(),
                "amount": e["amount"],
                "estimated": e["estimated"],
            }
            for e in sorted(tl["card_due_events"], key=lambda x: x["due_date"])
        ],
    })


class SimulateBody(BaseModel):
    description: str
    cost: float
    target_date: date | None = None


@router.post("/simulate")
async def cashflow_simulate(request: Request, body: SimulateBody, _csrf: None = Depends(verify_csrf)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    if body.cost <= 0:
        return JSONResponse({"error": "El monto debe ser mayor a 0"}, status_code=400)

    supabase = get_supabase(user["access_token"])
    tl = _build_timeline(supabase, user["id"], SIMULATION_HORIZON_DAYS)
    today = tl["today"]
    target_date = max(body.target_date, today) if body.target_date else today

    result = find_safe_purchase_date(
        tl["daily_balance"], body.cost, target_date, today, tl["horizon_end"], events=tl["cash_events"],
    )
    result["breakdown"] = build_purchase_breakdown(
        tl["starting_balance"], tl["cash_events"], body.cost, tl["horizon_end"],
    )
    result["description"] = body.description
    result["cost"] = round(body.cost, 2)
    return JSONResponse(result)

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.cashflow import month_bounds
from app.core.csrf import configure_templates, verify_csrf
from app.core.income_projection import ensure_weekly_income_projections, get_or_create_income_rule
from app.core.ownership import get_owned_income
from app.core.clock import today as get_today
from app.db.supabase_client import get_supabase

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory="app/templates"))


def require_user(request: Request):
    return request.session.get("user")


@router.get("/", response_class=HTMLResponse)
async def income_list(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    period = request.query_params.get("period", get_today().strftime("%Y-%m"))
    start_date, end_date = month_bounds(period)

    supabase = get_supabase(user["access_token"])
    payroll_rule = get_or_create_income_rule(supabase, user["id"])
    ensure_weekly_income_projections(supabase, user["id"], start_date, end_date, payroll_rule)

    incomes_res = (
        supabase.table("incomes")
        .select("*")
        .eq("user_id", user["id"])
        .gte("income_date", start_date.isoformat())
        .lte("income_date", end_date.isoformat())
        .order("income_date", desc=True)
        .execute()
    )

    incomes = incomes_res.data or []
    total_income = round(sum(i["amount"] for i in incomes), 2)

    return templates.TemplateResponse(
        "income/list.html",
        {
            "request": request,
            "user": user,
            "incomes": incomes,
            "period": period,
            "today": get_today().isoformat(),
            "total_income": total_income,
            "payroll_rule": payroll_rule,
        },
    )


@router.post("/nuevo")
async def income_create(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    source: str = Form(...),
    amount: float = Form(...),
    income_date: str = Form(...),
    notes: Optional[str] = Form(None),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    source_value = source.strip()
    rule = get_or_create_income_rule(supabase, user["id"])

    # If this week already has a projected payroll row, convert it to manual.
    existing_projected = (
        supabase.table("incomes")
        .select("id")
        .eq("user_id", user["id"])
        .eq("source", rule["source_label"])
        .eq("income_date", income_date)
        .eq("is_projected", True)
        .execute()
    ).data or []

    payload = {
        "source": source_value,
        "amount": round(amount, 2),
        "income_date": income_date,
        "notes": (notes or "").strip() or None,
        "is_projected": False,
    }

    if existing_projected and source_value == rule["source_label"]:
        (
            supabase.table("incomes")
            .update(payload)
            .eq("id", existing_projected[0]["id"])
            .eq("user_id", user["id"])
            .execute()
        )
    else:
        supabase.table("incomes").insert({"user_id": user["id"], **payload}).execute()

    period = income_date[:7]
    return RedirectResponse(f"/income/?period={period}", status_code=302)


@router.post("/{income_id}/eliminar")
async def income_delete(
    request: Request,
    income_id: str,
    _csrf: None = Depends(verify_csrf),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    income = get_owned_income(supabase, user["id"], income_id, "id, income_date")

    supabase.table("incomes").delete().eq("id", income_id).eq("user_id", user["id"]).execute()

    return RedirectResponse(f"/income/?period={income['income_date'][:7]}", status_code=302)


@router.post("/configurar-nomina")
async def configure_payroll(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    weekly_amount: float = Form(...),
    payday_weekday: int = Form(...),
    period: str = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    get_or_create_income_rule(supabase, user["id"])

    supabase.table("income_rules").update(
        {
            "weekly_amount": round(weekly_amount, 2),
            "payday_weekday": payday_weekday,
        }
    ).eq("user_id", user["id"]).execute()

    return RedirectResponse(f"/income/?period={period}", status_code=302)


@router.post("/{income_id}/ajustar")
async def adjust_income(
    request: Request,
    income_id: str,
    _csrf: None = Depends(verify_csrf),
    amount: float = Form(...),
    notes: Optional[str] = Form(None),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    income = get_owned_income(
        supabase, user["id"], income_id, "id, income_date, is_projected, notes"
    )

    next_notes = (notes or "").strip()
    if not next_notes:
        next_notes = income.get("notes")

    supabase.table("incomes").update(
        {
            "amount": round(amount, 2),
            "notes": next_notes,
            "is_projected": False,
        }
    ).eq("id", income_id).eq("user_id", user["id"]).execute()

    return RedirectResponse(f"/income/?period={income['income_date'][:7]}", status_code=302)

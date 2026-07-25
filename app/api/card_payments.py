from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.csrf import configure_templates, verify_csrf
from app.core.ownership import get_owned_card, get_owned_card_payment
from app.core.card_payments import calculate_pending_balance
from app.db.supabase_client import get_supabase
from app.core.clock import today as get_today
from datetime import date
from typing import Optional

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory="app/templates"))


def require_user(request: Request):
    return request.session.get("user")


@router.get("/{card_id}", response_class=HTMLResponse)
async def payments_list(request: Request, card_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    card = get_owned_card(supabase, user["id"], card_id)

    default_period = get_today().strftime("%Y-%m")
    selected_period = request.query_params.get("period", default_period)

    payments_res = supabase.table("card_payments") \
        .select("*") \
        .eq("user_id", user["id"]) \
        .eq("card_id", card_id) \
        .eq("billing_period", selected_period) \
        .order("payment_date", desc=True) \
        .execute()
    payments = payments_res.data or []

    expenses_res = supabase.table("expenses") \
        .select("amount") \
        .eq("user_id", user["id"]) \
        .eq("card_id", card_id) \
        .eq("billing_period", selected_period) \
        .execute()
    total_expenses = sum(e["amount"] for e in (expenses_res.data or []))
    total_paid = sum(p["amount"] for p in payments)

    balance = calculate_pending_balance(total_expenses, total_paid)

    return templates.TemplateResponse("card_payments/list.html", {
        "request":         request,
        "user":            user,
        "card":            card,
        "payments":        payments,
        "selected_period": selected_period,
        "total_expenses":  round(total_expenses, 2),
        "total_paid":      round(total_paid, 2),
        "pending":         balance["pending"],
        "is_paid":         balance["is_paid"],
        "today":           get_today().isoformat(),
    })


@router.post("/{card_id}/nuevo")
async def payment_create(
    request: Request,
    card_id: str,
    _csrf: None = Depends(verify_csrf),
    billing_period: str = Form(...),
    amount: float = Form(...),
    payment_date: str = Form(...),
    notes: Optional[str] = Form(None),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    get_owned_card(supabase, user["id"], card_id, "id")

    supabase.table("card_payments").insert({
        "user_id":        user["id"],
        "card_id":        card_id,
        "billing_period": billing_period,
        "amount":         round(amount, 2),
        "payment_date":   payment_date,
        "notes":          notes or None,
    }).execute()

    return RedirectResponse(
        f"/card-payments/{card_id}?period={billing_period}",
        status_code=302,
    )


@router.post("/{payment_id}/eliminar")
async def payment_delete(
    request: Request,
    payment_id: str,
    _csrf: None = Depends(verify_csrf),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    payment = get_owned_card_payment(
        supabase, user["id"], payment_id, "id, card_id, billing_period"
    )

    supabase.table("card_payments") \
        .delete() \
        .eq("id", payment_id) \
        .eq("user_id", user["id"]) \
        .execute()

    return RedirectResponse(
        f"/card-payments/{payment['card_id']}?period={payment['billing_period']}",
        status_code=302,
    )

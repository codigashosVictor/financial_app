from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.core.csrf import configure_templates, verify_csrf
from app.core.ownership import get_owned_account, get_owned_debt
from app.core.card_payments import calculate_pending_balance
from app.core.clock import today as get_today
from app.core.reports import build_periods
from app.core.net_worth import calculate_net_worth, build_net_worth_series
from app.db.supabase_client import get_supabase

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory="app/templates"))

ACCOUNT_TYPES = ["Efectivo", "Ahorro", "Inversión", "Otro"]
DEBT_TYPES = ["Préstamo", "Hipoteca", "Otro"]


def require_user(request: Request):
    return request.session.get("user")


def _cards_pending_total(supabase, user_id: str, period: str) -> float:
    """Suma el saldo pendiente (no cubierto por pagos) de todas las tarjetas en un periodo."""
    expenses_res = supabase.table("expenses")\
        .select("amount").eq("user_id", user_id).eq("billing_period", period).execute()
    payments_res = supabase.table("card_payments")\
        .select("amount").eq("user_id", user_id).eq("billing_period", period).execute()

    total_expenses = sum(e["amount"] for e in (expenses_res.data or []))
    total_payments = sum(p["amount"] for p in (payments_res.data or []))
    pending = calculate_pending_balance(total_expenses, total_payments)["pending"]
    return max(pending, 0)


def _cards_pending_by_period(supabase, user_id: str, periods: list) -> dict:
    expenses_res = supabase.table("expenses")\
        .select("amount, billing_period")\
        .eq("user_id", user_id)\
        .gte("billing_period", periods[0])\
        .lte("billing_period", periods[-1])\
        .execute()
    payments_res = supabase.table("card_payments")\
        .select("amount, billing_period")\
        .eq("user_id", user_id)\
        .gte("billing_period", periods[0])\
        .lte("billing_period", periods[-1])\
        .execute()

    expense_totals, payment_totals = {}, {}
    for e in (expenses_res.data or []):
        expense_totals[e["billing_period"]] = expense_totals.get(e["billing_period"], 0) + e["amount"]
    for p in (payments_res.data or []):
        payment_totals[p["billing_period"]] = payment_totals.get(p["billing_period"], 0) + p["amount"]

    return {
        period: max(
            calculate_pending_balance(expense_totals.get(period, 0), payment_totals.get(period, 0))["pending"], 0
        )
        for period in periods
    }


@router.get("/", response_class=HTMLResponse)
async def net_worth_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    accounts_res = supabase.table("accounts")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).order("created_at").execute()
    debts_res = supabase.table("debts")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).order("created_at").execute()
    accounts = accounts_res.data or []
    debts = debts_res.data or []

    account_ids = [a["id"] for a in accounts]
    debt_ids = [d["id"] for d in debts]

    account_balances = (
        supabase.table("account_balances").select("*").eq("user_id", user["id"]).in_("account_id", account_ids).execute().data or []
    ) if account_ids else []
    debt_balances = (
        supabase.table("debt_balances").select("*").eq("user_id", user["id"]).in_("debt_id", debt_ids).execute().data or []
    ) if debt_ids else []

    latest_by_account = {}
    for row in account_balances:
        cur = latest_by_account.get(row["account_id"])
        if not cur or row["snapshot_date"] >= cur["snapshot_date"]:
            latest_by_account[row["account_id"]] = row
    for a in accounts:
        a["balance"] = latest_by_account.get(a["id"], {}).get("balance")

    latest_by_debt = {}
    for row in debt_balances:
        cur = latest_by_debt.get(row["debt_id"])
        if not cur or row["snapshot_date"] >= cur["snapshot_date"]:
            latest_by_debt[row["debt_id"]] = row
    for d in debts:
        d["balance"] = latest_by_debt.get(d["id"], {}).get("balance")

    today = get_today()
    cards_pending = _cards_pending_total(supabase, user["id"], today.strftime("%Y-%m"))
    summary = calculate_net_worth(account_balances, debt_balances, cards_pending)

    return templates.TemplateResponse("net_worth/index.html", {
        "request": request,
        "user": user,
        "accounts": accounts,
        "debts": debts,
        "summary": summary,
        "account_types": ACCOUNT_TYPES,
        "debt_types": DEBT_TYPES,
        "today": today.isoformat(),
    })


@router.get("/data")
async def net_worth_data(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    months = int(request.query_params.get("months", 12))
    today = get_today()
    periods = build_periods(today, months)

    supabase = get_supabase(user["access_token"])

    accounts_res = supabase.table("accounts").select("id").eq("user_id", user["id"]).execute()
    debts_res = supabase.table("debts").select("id").eq("user_id", user["id"]).execute()
    account_ids = [a["id"] for a in (accounts_res.data or [])]
    debt_ids = [d["id"] for d in (debts_res.data or [])]

    account_balances = (
        supabase.table("account_balances").select("*").eq("user_id", user["id"]).in_("account_id", account_ids).execute().data or []
    ) if account_ids else []
    debt_balances = (
        supabase.table("debt_balances").select("*").eq("user_id", user["id"]).in_("debt_id", debt_ids).execute().data or []
    ) if debt_ids else []

    card_pending_by_period = _cards_pending_by_period(supabase, user["id"], periods)

    series = build_net_worth_series(periods, account_balances, debt_balances, card_pending_by_period)
    return JSONResponse(series)


# ── Cuentas ────────────────────────────────────────────────────

@router.get("/cuentas/nueva", response_class=HTMLResponse)
async def account_new(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("net_worth/account_form.html", {
        "request": request, "user": user, "account": None, "account_types": ACCOUNT_TYPES, "error": None,
    })


@router.post("/cuentas/nueva")
async def account_create(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    name: str = Form(...),
    type: str = Form(...),
    balance: Optional[float] = Form(None),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    created = supabase.table("accounts").insert({
        "user_id": user["id"], "name": name, "type": type,
    }).execute().data or []

    if created and balance is not None:
        supabase.table("account_balances").insert({
            "user_id": user["id"],
            "account_id": created[0]["id"],
            "balance": round(balance, 2),
            "snapshot_date": get_today().isoformat(),
        }).execute()

    return RedirectResponse("/net-worth/", status_code=302)


@router.get("/cuentas/{account_id}/editar", response_class=HTMLResponse)
async def account_edit(request: Request, account_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    account = get_owned_account(supabase, user["id"], account_id)

    return templates.TemplateResponse("net_worth/account_form.html", {
        "request": request, "user": user, "account": account, "account_types": ACCOUNT_TYPES, "error": None,
    })


@router.post("/cuentas/{account_id}/editar")
async def account_update(
    request: Request, account_id: str,
    _csrf: None = Depends(verify_csrf),
    name: str = Form(...),
    type: str = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("accounts").update({"name": name, "type": type})\
        .eq("id", account_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/net-worth/", status_code=302)


@router.post("/cuentas/{account_id}/eliminar")
async def account_delete(request: Request, account_id: str, _csrf: None = Depends(verify_csrf)):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("accounts").update({"is_active": False})\
        .eq("id", account_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/net-worth/", status_code=302)


@router.post("/cuentas/{account_id}/saldo")
async def account_update_balance(
    request: Request, account_id: str,
    _csrf: None = Depends(verify_csrf),
    balance: float = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    get_owned_account(supabase, user["id"], account_id, "id")
    supabase.table("account_balances").insert({
        "user_id": user["id"],
        "account_id": account_id,
        "balance": round(balance, 2),
        "snapshot_date": get_today().isoformat(),
    }).execute()

    return RedirectResponse("/net-worth/", status_code=302)


# ── Deudas ─────────────────────────────────────────────────────

@router.get("/deudas/nueva", response_class=HTMLResponse)
async def debt_new(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("net_worth/debt_form.html", {
        "request": request, "user": user, "debt": None, "debt_types": DEBT_TYPES, "error": None,
    })


@router.post("/deudas/nueva")
async def debt_create(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    name: str = Form(...),
    type: str = Form(...),
    balance: Optional[float] = Form(None),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    created = supabase.table("debts").insert({
        "user_id": user["id"], "name": name, "type": type,
    }).execute().data or []

    if created and balance is not None:
        supabase.table("debt_balances").insert({
            "user_id": user["id"],
            "debt_id": created[0]["id"],
            "balance": round(balance, 2),
            "snapshot_date": get_today().isoformat(),
        }).execute()

    return RedirectResponse("/net-worth/", status_code=302)


@router.get("/deudas/{debt_id}/editar", response_class=HTMLResponse)
async def debt_edit(request: Request, debt_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    debt = get_owned_debt(supabase, user["id"], debt_id)

    return templates.TemplateResponse("net_worth/debt_form.html", {
        "request": request, "user": user, "debt": debt, "debt_types": DEBT_TYPES, "error": None,
    })


@router.post("/deudas/{debt_id}/editar")
async def debt_update(
    request: Request, debt_id: str,
    _csrf: None = Depends(verify_csrf),
    name: str = Form(...),
    type: str = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("debts").update({"name": name, "type": type})\
        .eq("id", debt_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/net-worth/", status_code=302)


@router.post("/deudas/{debt_id}/eliminar")
async def debt_delete(request: Request, debt_id: str, _csrf: None = Depends(verify_csrf)):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("debts").update({"is_active": False})\
        .eq("id", debt_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/net-worth/", status_code=302)


@router.post("/deudas/{debt_id}/saldo")
async def debt_update_balance(
    request: Request, debt_id: str,
    _csrf: None = Depends(verify_csrf),
    balance: float = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    get_owned_debt(supabase, user["id"], debt_id, "id")
    supabase.table("debt_balances").insert({
        "user_id": user["id"],
        "debt_id": debt_id,
        "balance": round(balance, 2),
        "snapshot_date": get_today().isoformat(),
    }).execute()

    return RedirectResponse("/net-worth/", status_code=302)

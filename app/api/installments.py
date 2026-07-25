from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.csrf import configure_templates, verify_csrf
from app.core.ownership import get_owned_card, get_owned_installment_plan
from app.db.supabase_client import get_supabase
from app.core.recurring import generate_installment_expenses, get_installment_status
from app.core.billing_cycle import get_billing_period
from app.core.clock import today as get_today
from datetime import date

router = APIRouter()
templates = configure_templates(Jinja2Templates(directory="app/templates"))

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def plans_list(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    today = get_today()
    current_period = today.strftime("%Y-%m")

    # Generar cuotas automáticas
    generate_installment_expenses(supabase, user["id"])

    res = supabase.table("installment_plans")\
        .select("*, credit_cards(name)")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .order("created_at", desc=True)\
        .execute()

    plans = []
    total_monthly = 0
    total_pending = 0

    for plan in (res.data or []):
        status = get_installment_status(plan, current_period)
        plan["status"] = status
        total_monthly += plan["monthly_amount"]
        total_pending += status["remaining_amount"]

        # Marcar como inactivo si ya terminó
        if status["is_done"]:
            supabase.table("installment_plans")\
                .update({"is_active": False})\
                .eq("id", plan["id"])\
                .eq("user_id", user["id"])\
                .execute()
        else:
            plans.append(plan)

    return templates.TemplateResponse("installments/list.html", {
        "request": request,
        "user": user,
        "plans": plans,
        "total_monthly": total_monthly,
        "total_pending": total_pending,
        "current_period": current_period,
    })

@router.get("/nuevo", response_class=HTMLResponse)
async def plan_new(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    cards = supabase.table("credit_cards")\
        .select("id, name, cut_day")\
        .eq("user_id", user["id"]).eq("is_active", True).execute()

    return templates.TemplateResponse("installments/form.html", {
        "request": request, "user": user,
        "cards": cards.data or [],
        "today": get_today().isoformat(),
        "error": None,
    })

@router.post("/nuevo")
async def plan_create(
    request: Request,
    _csrf: None = Depends(verify_csrf),
    name: str = Form(...),
    card_id: str = Form(...),
    total_amount: float = Form(...),
    installments: int = Form(...),
    start_date: str = Form(...),
    category: str = Form("Tecnología"),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    # Calcular mensualidad y periodo inicial
    monthly_amount = round(total_amount / installments, 2)
    card = get_owned_card(supabase, user["id"], card_id, "cut_day", active_only=True)
    cut_day = card["cut_day"]

    start = date.fromisoformat(start_date)
    start_period = get_billing_period(start, cut_day)

    supabase.table("installment_plans").insert({
        "user_id": user["id"],
        "card_id": card_id,
        "name": name,
        "total_amount": total_amount,
        "installments": installments,
        "monthly_amount": monthly_amount,
        "start_date": start_date,
        "start_period": start_period,
        "category": category,
        "is_active": True,
    }).execute()

    # Generar cuotas inmediatamente
    generate_installment_expenses(supabase, user["id"])

    return RedirectResponse("/installments/", status_code=302)

@router.post("/{plan_id}/eliminar")
async def plan_delete(request: Request, plan_id: str, _csrf: None = Depends(verify_csrf)):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    get_owned_installment_plan(supabase, user["id"], plan_id, "id")

    # Eliminar gastos generados por este plan
    supabase.table("expenses")\
        .delete()\
        .eq("installment_plan_id", plan_id)\
        .eq("user_id", user["id"])\
        .execute()

    supabase.table("installment_plans")\
        .delete().eq("id", plan_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/installments/", status_code=302)

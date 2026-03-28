from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from app.core.recurring import generate_subscription_expenses
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def subs_list(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    # Generar gastos automáticos al entrar
    generate_subscription_expenses(supabase, user["id"], user["access_token"])

    res = supabase.table("subscriptions")\
        .select("*, credit_cards(name)")\
        .eq("user_id", user["id"])\
        .order("is_active", desc=True)\
        .order("name")\
        .execute()

    total_active = sum(
        s["amount"] for s in (res.data or []) if s["is_active"]
    )

    return templates.TemplateResponse("subscriptions/list.html", {
        "request": request,
        "user": user,
        "subscriptions": res.data or [],
        "total_active": total_active,
    })

@router.get("/nuevo", response_class=HTMLResponse)
async def sub_new(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    cards = supabase.table("credit_cards")\
        .select("id, name").eq("user_id", user["id"]).eq("is_active", True).execute()

    return templates.TemplateResponse("subscriptions/form.html", {
        "request": request, "user": user,
        "cards": cards.data or [], "sub": None, "error": None
    })

@router.post("/nuevo")
async def sub_create(
    request: Request,
    name: str = Form(...),
    card_id: str = Form(...),
    amount: float = Form(...),
    charge_day: int = Form(...),
    category: str = Form("Entretenimiento"),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("subscriptions").insert({
        "user_id": user["id"],
        "card_id": card_id,
        "name": name,
        "amount": amount,
        "charge_day": charge_day,
        "category": category,
        "is_active": True,
    }).execute()

    # Generar el gasto del periodo actual inmediatamente
    generate_subscription_expenses(supabase, user["id"], user["access_token"])

    return RedirectResponse("/subscriptions/", status_code=302)

@router.post("/{sub_id}/toggle")
async def sub_toggle(request: Request, sub_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    current = supabase.table("subscriptions")\
        .select("is_active").eq("id", sub_id).single().execute()

    new_state = not current.data["is_active"]
    supabase.table("subscriptions")\
        .update({"is_active": new_state})\
        .eq("id", sub_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/subscriptions/", status_code=302)

@router.post("/{sub_id}/eliminar")
async def sub_delete(request: Request, sub_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("subscriptions")\
        .delete().eq("id", sub_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/subscriptions/", status_code=302)
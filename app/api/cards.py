from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def cards_list(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    res = supabase.table("credit_cards")\
        .select("*")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .order("created_at", desc=False)\
        .execute()

    return templates.TemplateResponse("cards/list.html", {
        "request": request,
        "user": user,
        "cards": res.data or []
    })

@router.get("/nuevo", response_class=HTMLResponse)
async def card_new(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("cards/form.html", {
        "request": request, "user": user, "card": None, "error": None
    })

@router.post("/nuevo")
async def card_create(
    request: Request,
    name: str = Form(...),
    cut_day: int = Form(...),
    payment_due_day: int = Form(...),
    credit_limit: Optional[float] = Form(None)
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    try:
        supabase = get_supabase(user["access_token"])
        supabase.table("credit_cards").insert({
            "user_id": user["id"],
            "name": name,
            "cut_day": cut_day,
            "payment_due_day": payment_due_day,
            "credit_limit": credit_limit,
        }).execute()
        return RedirectResponse("/cards/", status_code=302)
    except Exception as e:
        return templates.TemplateResponse("cards/form.html", {
            "request": request, "user": user, "card": None, "error": str(e)
        })

@router.get("/{card_id}/editar", response_class=HTMLResponse)
async def card_edit(request: Request, card_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    res = supabase.table("credit_cards")\
        .select("*").eq("id", card_id).eq("user_id", user["id"])\
        .single().execute()

    return templates.TemplateResponse("cards/form.html", {
        "request": request, "user": user, "card": res.data, "error": None
    })

@router.post("/{card_id}/editar")
async def card_update(
    request: Request, card_id: str,
    name: str = Form(...),
    cut_day: int = Form(...),
    payment_due_day: int = Form(...),
    credit_limit: Optional[float] = Form(None)
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("credit_cards").update({
        "name": name, "cut_day": cut_day,
        "payment_due_day": payment_due_day, "credit_limit": credit_limit,
    }).eq("id", card_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/cards/", status_code=302)

@router.post("/{card_id}/eliminar")
async def card_delete(request: Request, card_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("credit_cards")\
        .update({"is_active": False})\
        .eq("id", card_id).eq("user_id", user["id"]).execute()

    return RedirectResponse("/cards/", status_code=302)
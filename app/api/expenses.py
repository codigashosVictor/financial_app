from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from app.core.billing_cycle import get_billing_period
from app.core.ocr_processor import process_receipt_image
from datetime import date
from typing import Optional
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def expenses_list(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    # Filtros desde query params
    period = request.query_params.get("period", date.today().strftime("%Y-%m"))
    card_id = request.query_params.get("card_id", "")

    query = supabase.table("expenses")\
        .select("*, credit_cards(name)")\
        .eq("user_id", user["id"])\
        .eq("billing_period", period)\
        .order("expense_date", desc=True)

    if card_id:
        query = query.eq("card_id", card_id)

    expenses_res = query.execute()

    cards_res = supabase.table("credit_cards")\
        .select("id, name")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .execute()

    total = sum(e["amount"] for e in (expenses_res.data or []))

    return templates.TemplateResponse("expenses/list.html", {
        "request": request,
        "user": user,
        "expenses": expenses_res.data or [],
        "cards": cards_res.data or [],
        "current_period": period,
        "selected_card": card_id,
        "total": total,
    })

@router.get("/nuevo", response_class=HTMLResponse)
async def expense_new(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    cards_res = supabase.table("credit_cards")\
        .select("id, name, cut_day")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .execute()

    return templates.TemplateResponse("expenses/form.html", {
        "request": request,
        "user": user,
        "cards": cards_res.data or [],
        "expense": None,
        "error": None,
        "today": date.today().isoformat(),
    })

@router.post("/nuevo")
async def expense_create(
    request: Request,
    card_id: str = Form(...),
    merchant: str = Form(""),
    amount: float = Form(...),
    tax_amount: float = Form(0.0),
    category: str = Form("Otro"),
    notes: str = Form(""),
    expense_date: str = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    # Obtener cut_day de la tarjeta
    card_res = supabase.table("credit_cards")\
        .select("cut_day")\
        .eq("id", card_id)\
        .single()\
        .execute()

    cut_day = card_res.data["cut_day"]
    exp_date = date.fromisoformat(expense_date)
    billing_period = get_billing_period(exp_date, cut_day)

    supabase.table("expenses").insert({
        "user_id": user["id"],
        "card_id": card_id if card_id else None,
        "merchant": merchant or None,
        "amount": amount,
        "tax_amount": tax_amount,
        "category": category,
        "notes": notes or None,
        "expense_date": expense_date,
        "billing_period": billing_period,
        "source": "manual",
    }).execute()

    return RedirectResponse("/expenses/", status_code=302)

@router.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    cards_res = supabase.table("credit_cards")\
        .select("id, name, cut_day")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .execute()

    return templates.TemplateResponse("expenses/scan.html", {
        "request": request,
        "user": user,
        "cards": cards_res.data or [],
        "today": date.today().isoformat(),
    })

@router.post("/ocr")
async def process_ocr(
    request: Request,
    image: UploadFile = File(...),
):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    image_bytes = await image.read()
    result = await process_receipt_image(image_bytes, image.content_type)
    return JSONResponse(result)

@router.post("/scan/guardar")
async def scan_save(
    request: Request,
    card_id: str = Form(...),
    merchant: str = Form(""),
    amount: float = Form(...),
    tax_amount: float = Form(0.0),
    category: str = Form("Otro"),
    expense_date: str = Form(...),
    notes: str = Form(""),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    card_res = supabase.table("credit_cards")\
        .select("cut_day")\
        .eq("id", card_id)\
        .single()\
        .execute()

    cut_day = card_res.data["cut_day"]
    exp_date = date.fromisoformat(expense_date)
    billing_period = get_billing_period(exp_date, cut_day)

    supabase.table("expenses").insert({
        "user_id": user["id"],
        "card_id": card_id,
        "merchant": merchant or None,
        "amount": amount,
        "tax_amount": tax_amount,
        "category": category,
        "notes": notes or None,
        "expense_date": expense_date,
        "billing_period": billing_period,
        "source": "ocr",
    }).execute()

    return RedirectResponse("/expenses/", status_code=302)

@router.post("/{expense_id}/eliminar")
async def expense_delete(request: Request, expense_id: str):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])
    supabase.table("expenses")\
        .delete()\
        .eq("id", expense_id)\
        .eq("user_id", user["id"])\
        .execute()

    return RedirectResponse("/expenses/", status_code=302)
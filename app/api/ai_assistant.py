from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from app.core.payment_strategy import analyze_payment_strategy
from datetime import date

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def ai_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    # Historial de consultas
    logs_res = supabase.table("payment_strategy_logs")\
        .select("*")\
        .eq("user_id", user["id"])\
        .order("created_at", desc=True)\
        .limit(10)\
        .execute()

    return templates.TemplateResponse("ai/index.html", {
        "request": request,
        "user": user,
        "logs": logs_res.data or []
    })

@router.post("/analyze")
async def ai_analyze(request: Request, strategy_type: str = Form("snowball")):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    supabase = get_supabase(user["access_token"])
    today = date.today()
    current_period = today.strftime("%Y-%m")

    # Recopilar datos del usuario
    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()
    cards = cards_res.data or []

    expenses_res = supabase.table("expenses")\
        .select("*").eq("user_id", user["id"])\
        .eq("billing_period", current_period).execute()
    expenses = expenses_res.data or []

    if not cards:
        return JSONResponse({"error": "No tienes tarjetas registradas"}, status_code=400)

    # Llamar a Gemini
    result = await analyze_payment_strategy(cards, expenses, strategy_type, current_period)

    # Guardar log
    supabase.table("payment_strategy_logs").insert({
        "user_id": user["id"],
        "strategy_type": strategy_type,
        "prompt_summary": f"Análisis {strategy_type} — periodo {current_period}",
        "ai_response": result,
    }).execute()

    return JSONResponse({"response": result})

@router.get("/data")
async def ai_data(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    supabase = get_supabase(user["access_token"])
    today = date.today()
    current_period = today.strftime("%Y-%m")

    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()

    expenses_res = supabase.table("expenses")\
        .select("*").eq("user_id", user["id"])\
        .eq("billing_period", current_period).execute()

    # Total por tarjeta
    card_totals = {}
    for exp in (expenses_res.data or []):
        cid = exp.get("card_id")
        card_totals[cid] = card_totals.get(cid, 0) + exp["amount"]

    cards_with_totals = []
    for card in (cards_res.data or []):
        card["total_current_period"] = card_totals.get(card["id"], 0)
        cards_with_totals.append(card)

    return JSONResponse({
        "cards": cards_with_totals,
        "period": current_period,
    })
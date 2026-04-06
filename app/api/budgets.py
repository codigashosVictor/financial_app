from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase
from datetime import date

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

CATEGORIES = [
    "Alimentación", 
    "Transporte", 
    "Entretenimiento",
    "Salud", 
    "Ropa", 
    "Tecnología", 
    "Hogar", 
    "Educación",
    "Cita Bby",
    "Vacaciones",
    "Servicios",
    "Regalos",
    "Seguros/Mtto",
    "Inversión",
    "Gasolina",
    "Mandado",
    "Otro"
]

CAT_EMOJI = {
    "Alimentación": "🍔", 
    "Transporte": "🚗", 
    "Entretenimiento": "🎬", 
    "Inversión": "📈",
    "Salud": "💊", 
    "Ropa": "👕", 
    "Tecnología": "💻", 
    "Hogar": "🏠", 
    "Educación": "🎓", 
    "Cita Bby": "💑", 
    "Vacaciones": "🌴", 
    "Servicios": "⚡", 
    "Regalos": "🎁", 
    "Seguros/Mtto": "🛡️", 
    "Gasolina": "⛽",
    "Mandado": "🛒",
    "Otro": "📦"
}

def require_user(request: Request):
    return request.session.get("user")

@router.get("/", response_class=HTMLResponse)
async def budgets_page(request: Request):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    today          = date.today()
    current_period = request.query_params.get("period", today.strftime("%Y-%m"))
    supabase       = get_supabase(user["access_token"])

    # Presupuestos del periodo
    budgets_res = supabase.table("budgets")\
        .select("*")\
        .eq("user_id", user["id"])\
        .eq("period", current_period)\
        .execute()

    budgets_map = {b["category"]: b for b in (budgets_res.data or [])}

    # Gastos reales del periodo
    expenses_res = supabase.table("expenses")\
        .select("category, amount")\
        .eq("user_id", user["id"])\
        .eq("billing_period", current_period)\
        .execute()

    spent_map = {}
    for exp in (expenses_res.data or []):
        cat = exp.get("category", "Otro")
        spent_map[cat] = spent_map.get(cat, 0) + exp["amount"]

    # Construir lista combinada
    categories = []
    total_budgeted = 0
    total_spent    = 0

    for cat in CATEGORIES:
        budget  = budgets_map.get(cat)
        spent   = spent_map.get(cat, 0)
        budgeted = budget["amount"] if budget else 0
        pct     = round((spent / budgeted * 100) if budgeted > 0 else 0)

        total_budgeted += budgeted
        total_spent    += spent

        categories.append({
            "name":      cat,
            "emoji":     CAT_EMOJI[cat],
            "budgeted":  budgeted,
            "spent":     round(spent, 2),
            "remaining": round(budgeted - spent, 2),
            "pct":       min(pct, 100),
            "overflow":  max(round(spent - budgeted, 2), 0),
            "status":    "over" if spent > budgeted and budgeted > 0
                         else "warning" if pct >= 80
                         else "ok",
            "has_budget": budget is not None,
            "budget_id":  budget["id"] if budget else None,
        })

    return templates.TemplateResponse("budgets/index.html", {
        "request":        request,
        "user":           user,
        "categories":     categories,
        "current_period": current_period,
        "total_budgeted": round(total_budgeted, 2),
        "total_spent":    round(total_spent, 2),
    })

@router.post("/save")
async def save_budget(
    request: Request,
    period: str = Form(...),
):
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase  = get_supabase(user["access_token"])
    form_data = await request.form()

    for cat in CATEGORIES:
        key = f"budget_{cat}"
        val = form_data.get(key, "").strip()

        if not val:
            # Borrar presupuesto si se dejó vacío
            supabase.table("budgets")\
                .delete()\
                .eq("user_id", user["id"])\
                .eq("category", cat)\
                .eq("period", period)\
                .execute()
            continue

        try:
            amount = float(val)
            if amount <= 0:
                continue
        except ValueError:
            continue

        # Upsert — actualiza si existe, crea si no
        supabase.table("budgets").upsert({
            "user_id":  user["id"],
            "category": cat,
            "amount":   amount,
            "period":   period,
        }, on_conflict="user_id,category,period").execute()

    return RedirectResponse(f"/budgets/?period={period}", status_code=302)

@router.post("/copy")
async def copy_budget(
    request: Request,
    from_period: str = Form(...),
    to_period: str = Form(...),
):
    """Copia presupuestos de un mes a otro."""
    user = require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    supabase = get_supabase(user["access_token"])

    source = supabase.table("budgets")\
        .select("*")\
        .eq("user_id", user["id"])\
        .eq("period", from_period)\
        .execute()

    for b in (source.data or []):
        supabase.table("budgets").upsert({
            "user_id":  user["id"],
            "category": b["category"],
            "amount":   b["amount"],
            "period":   to_period,
        }, on_conflict="user_id,category,period").execute()

    return RedirectResponse(f"/budgets/?period={to_period}", status_code=302)

@router.get("/data")
async def budgets_data(request: Request):
    """Endpoint para el dashboard — presupuestos del periodo activo."""
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    period   = request.query_params.get("period", date.today().strftime("%Y-%m"))
    supabase = get_supabase(user["access_token"])

    budgets_res = supabase.table("budgets")\
        .select("*")\
        .eq("user_id", user["id"])\
        .eq("period", period)\
        .execute()

    expenses_res = supabase.table("expenses")\
        .select("category, amount")\
        .eq("user_id", user["id"])\
        .eq("billing_period", period)\
        .execute()

    spent_map = {}
    for exp in (expenses_res.data or []):
        cat = exp.get("category", "Otro")
        spent_map[cat] = spent_map.get(cat, 0) + exp["amount"]

    result = []
    for b in (budgets_res.data or []):
        cat     = b["category"]
        spent   = spent_map.get(cat, 0)
        budgeted = b["amount"]
        pct     = round((spent / budgeted * 100) if budgeted > 0 else 0)

        result.append({
            "category": cat,
            "emoji":    CAT_EMOJI.get(cat, "📦"),
            "budgeted": budgeted,
            "spent":    round(spent, 2),
            "pct":      min(pct, 100),
            "status":   "over" if spent > budgeted else "warning" if pct >= 80 else "ok",
        })

    return JSONResponse({"budgets": result, "period": period})
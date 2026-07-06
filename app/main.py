from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware as StarletteSessionMiddleware
from app.config import settings
from app.core.session import SessionMiddleware as AppSessionMiddleware
from app.core.csrf import configure_templates
from app.api import auth, cards, expenses, dashboard, ai_assistant, subscriptions, installments, card_payments, income
from app.api import budgets
from app.api import calendar_view
from app.api import push
from app.api import cron

app = FastAPI(title="Finance App", version="1.0.0")

# Orden importante: Starlette session primero, luego el nuestro
app.add_middleware(AppSessionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.add_middleware(StarletteSessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = configure_templates(Jinja2Templates(directory="app/templates"))

app.include_router(auth.router, tags=["auth"])
app.include_router(cards.router, prefix="/cards", tags=["cards"])
app.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(ai_assistant.router, prefix="/ai", tags=["ai"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(installments.router, prefix="/installments", tags=["installments"])
app.include_router(card_payments.router, prefix="/card-payments", tags=["card-payments"])
app.include_router(income.router, prefix="/income", tags=["income"])
app.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
app.include_router(calendar_view.router, prefix="/calendar", tags=["calendar"])
app.include_router(push.router, prefix="/push", tags=["push"])
app.include_router(cron.router, prefix="/cron", tags=["cron"])

@app.get("/")
async def root(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/healthz")
async def healthz():
    return {"ok": True}

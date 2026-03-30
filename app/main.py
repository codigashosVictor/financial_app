from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware as StarletteSessionMiddleware
from app.config import settings
from app.core.session import SessionMiddleware as AppSessionMiddleware
from app.api import auth, cards, expenses, dashboard, ai_assistant, subscriptions, installments

app = FastAPI(title="Finance App", version="1.0.0")

# Orden importante: Starlette session primero, luego el nuestro
app.add_middleware(AppSessionMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(StarletteSessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router, tags=["auth"])
app.include_router(cards.router, prefix="/cards", tags=["cards"])
app.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(ai_assistant.router, prefix="/ai", tags=["ai"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(installments.router, prefix="/installments", tags=["installments"])

@app.get("/")
async def root(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
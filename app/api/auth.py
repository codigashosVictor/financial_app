from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.supabase_client import get_supabase

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        supabase = get_supabase()
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        # Guardar tokens completos incluyendo refresh_token y expires_at
        request.session["user"] = {
            "id":            response.user.id,
            "email":         response.user.email,
            "access_token":  response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_at":    response.session.expires_at,
        }
        return RedirectResponse("/", status_code=302)

    except Exception:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Credenciales incorrectas"
        })

@router.get("/logout")
async def logout(request: Request):
    try:
        user = request.session.get("user")
        if user:
            supabase = get_supabase()
            supabase.auth.sign_out()
    except Exception:
        pass
    finally:
        request.session.clear()
    return RedirectResponse("/login", status_code=302)
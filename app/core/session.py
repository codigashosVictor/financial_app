from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from supabase import create_client
from app.config import settings
import time

# Rutas que NO requieren autenticación
PUBLIC_ROUTES = {"/login", "/logout", "/static", "/favicon.ico"}

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Dejar pasar rutas públicas y archivos estáticos
        if any(path.startswith(r) for r in PUBLIC_ROUTES):
            return await call_next(request)

        user = request.session.get("user")

        # Sin sesión → login
        if not user:
            if path.startswith("/api") or "application/json" in request.headers.get("accept", ""):
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": "No autorizado", "redirect": "/login"}, status_code=401)
            return RedirectResponse("/login", status_code=302)

        # Verificar si el token está por vencer o ya venció
        # Supabase tokens duran 1 hora (3600 seg), renovamos con 5 min de margen
        expires_at = user.get("expires_at", 0)
        now = int(time.time())

        if now >= expires_at - 300:  # 5 minutos antes de que expire
            try:
                client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                refresh_token = user.get("refresh_token")

                if not refresh_token:
                    request.session.clear()
                    return RedirectResponse("/login", status_code=302)

                refreshed = client.auth.refresh_session(refresh_token)

                # Actualizar sesión con nuevos tokens
                request.session["user"] = {
                    "id":            refreshed.user.id,
                    "email":         refreshed.user.email,
                    "access_token":  refreshed.session.access_token,
                    "refresh_token": refreshed.session.refresh_token,
                    "expires_at":    refreshed.session.expires_at,
                }
            except Exception:
                # Si no se puede renovar → limpiar y redirigir
                request.session.clear()
                if "application/json" in request.headers.get("accept", ""):
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"error": "Sesión expirada", "redirect": "/login"}, status_code=401)
                return RedirectResponse("/login", status_code=302)

        # Continuar con la request normal
        try:
            response = await call_next(request)
            return response
        except Exception:
            # Cualquier error no capturado → redirigir limpiamente
            request.session.clear()
            return RedirectResponse("/login", status_code=302)
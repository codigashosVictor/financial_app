from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from app.core.csrf import verify_csrf
from app.db.supabase_client import get_supabase
from app.config import settings
from datetime import date
from app.core.alerts import build_alerts_for_user
from app.core.push_dispatch import send_alerts_to_user

router = APIRouter()

def require_user(request: Request):
    return request.session.get("user")

# ── Guardar suscripción push ─────────────────────────────────
@router.post("/subscribe")
async def subscribe(request: Request, _csrf: None = Depends(verify_csrf)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    body      = await request.json()
    endpoint  = body.get("endpoint")
    p256dh    = body.get("keys", {}).get("p256dh")
    auth      = body.get("keys", {}).get("auth")

    if not all([endpoint, p256dh, auth]):
        return JSONResponse({"error": "datos incompletos"}, status_code=400)

    supabase = get_supabase(user["access_token"])
    supabase.table("push_subscriptions").upsert({
        "user_id":  user["id"],
        "endpoint": endpoint,
        "p256dh":   p256dh,
        "auth":     auth,
    }, on_conflict="endpoint").execute()

    return JSONResponse({"ok": True})

# ── Eliminar suscripción push ────────────────────────────────
@router.post("/unsubscribe")
async def unsubscribe(request: Request, _csrf: None = Depends(verify_csrf)):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    body     = await request.json()
    endpoint = body.get("endpoint")

    supabase = get_supabase(user["access_token"])
    supabase.table("push_subscriptions")\
        .delete()\
        .eq("endpoint", endpoint)\
        .eq("user_id", user["id"])\
        .execute()

    return JSONResponse({"ok": True})

# ── Enviar alertas del día ───────────────────────────────────
@router.post("/send-alerts")
async def send_alerts(request: Request, _csrf: None = Depends(verify_csrf)):
    """
    Revisa pagos próximos, suscripciones del día y presupuesto
    y envía notificaciones push al usuario.
    """
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    if not settings.VAPID_PRIVATE_KEY:
        return JSONResponse({"error": "VAPID no configurado"}, status_code=500)

    supabase = get_supabase(user["access_token"])
    alerts   = build_alerts_for_user(supabase, user["id"], date.today())

    if not alerts:
        return JSONResponse({"sent": 0, "message": "Sin alertas para hoy"})

    sent = send_alerts_to_user(supabase, user["id"], alerts)
    if sent == 0:
        return JSONResponse({"sent": 0, "message": "Sin dispositivos registrados"})

    return JSONResponse({"sent": sent, "alerts": len(alerts)})

# ── Clave pública VAPID para el frontend ─────────────────────
@router.get("/vapid-key")
async def vapid_key():
    return JSONResponse({"public_key": settings.VAPID_PUBLIC_KEY})

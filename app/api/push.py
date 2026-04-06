from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.db.supabase_client import get_supabase
from app.config import settings
from datetime import date
from dateutil.relativedelta import relativedelta
from app.core.billing_cycle import get_payment_due_date, get_billing_period
import json

router = APIRouter()

def require_user(request: Request):
    return request.session.get("user")

# ── Guardar suscripción push ─────────────────────────────────
@router.post("/subscribe")
async def subscribe(request: Request):
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
async def unsubscribe(request: Request):
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
async def send_alerts(request: Request):
    """
    Revisa pagos próximos y suscripciones del día
    y envía notificaciones push al usuario.
    """
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "no auth"}, status_code=401)

    if not settings.VAPID_PRIVATE_KEY:
        return JSONResponse({"error": "VAPID no configurado"}, status_code=500)

    supabase = get_supabase(user["access_token"])
    today    = date.today()
    alerts   = []

    # ── Alertas de pago de tarjetas ──────────────────────────
    cards_res = supabase.table("credit_cards")\
        .select("*").eq("user_id", user["id"]).eq("is_active", True).execute()

    for card in (cards_res.data or []):
        for delta in [-1, 0]:
            candidate = today + relativedelta(months=delta)
            period    = candidate.strftime("%Y-%m")
            due       = get_payment_due_date(period, card["cut_day"], card["payment_due_day"])
            days_left = (due - today).days

            if days_left not in [0, 1, 3, 7]:
                continue

            # Calcular monto del periodo
            exp_res = supabase.table("expenses")\
                .select("amount")\
                .eq("user_id", user["id"])\
                .eq("card_id", card["id"])\
                .eq("billing_period", period)\
                .execute()
            total = sum(e["amount"] for e in (exp_res.data or []))

            if days_left == 0:
                title = f"⚠️ Pago HOY — {card['name']}"
                body  = f"Vence hoy. Total a pagar: ${total:,.2f}"
                urgent = True
            elif days_left == 1:
                title = f"🔴 Pago MAÑANA — {card['name']}"
                body  = f"Tienes 1 día. Total: ${total:,.2f}"
                urgent = True
            elif days_left == 3:
                title = f"🟡 Pago en 3 días — {card['name']}"
                body  = f"Vence el {due.strftime('%d %b')}. Total: ${total:,.2f}"
                urgent = False
            else:
                title = f"📅 Pago en 1 semana — {card['name']}"
                body  = f"Vence el {due.strftime('%d %b')}. Total: ${total:,.2f}"
                urgent = False

            alerts.append({
                "title":  title,
                "body":   body,
                "tag":    f"payment-{card['id']}-{period}",
                "url":    "/",
                "urgent": urgent,
            })
            break  # solo una alerta por tarjeta

    # ── Alertas de suscripciones del día ────────────────────
    subs_res = supabase.table("subscriptions")\
        .select("*")\
        .eq("user_id", user["id"])\
        .eq("is_active", True)\
        .execute()

    day_subs = [s for s in (subs_res.data or []) if s["charge_day"] == today.day]
    if day_subs:
        names  = ", ".join(s["name"] for s in day_subs[:3])
        total  = sum(s["amount"] for s in day_subs)
        alerts.append({
            "title":  f"🔄 Cargos de hoy",
            "body":   f"{names} — ${total:,.2f} en total",
            "tag":    f"subs-{today.isoformat()}",
            "url":    "/subscriptions/",
            "urgent": False,
        })

    if not alerts:
        return JSONResponse({"sent": 0, "message": "Sin alertas para hoy"})

    # ── Obtener suscripciones push del usuario ───────────────
    subs_push = supabase.table("push_subscriptions")\
        .select("*").eq("user_id", user["id"]).execute()

    if not subs_push.data:
        return JSONResponse({"sent": 0, "message": "Sin dispositivos registrados"})

    # ── Enviar notificaciones ────────────────────────────────
    from pywebpush import webpush, WebPushException
    sent = 0

    for sub in subs_push.data:
        for alert in alerts:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {
                            "p256dh": sub["p256dh"],
                            "auth":   sub["auth"],
                        }
                    },
                    data=json.dumps(alert),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_EMAIL},
                )
                sent += 1
            except WebPushException as e:
                # Si el endpoint ya no es válido, eliminarlo
                if "410" in str(e) or "404" in str(e):
                    supabase.table("push_subscriptions")\
                        .delete().eq("endpoint", sub["endpoint"]).execute()

    return JSONResponse({"sent": sent, "alerts": len(alerts)})

# ── Clave pública VAPID para el frontend ─────────────────────
@router.get("/vapid-key")
async def vapid_key():
    return JSONResponse({"public_key": settings.VAPID_PUBLIC_KEY})
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from datetime import date
from hmac import compare_digest
from app.config import settings
from app.db.supabase_client import get_supabase_admin
from app.core.alerts import build_alerts_for_user
from app.core.push_dispatch import send_alerts_to_user

router = APIRouter()


@router.post("/send-alerts")
async def cron_send_alerts(x_cron_secret: str = Header(default="")):
    """
    Alertas proactivas para todos los usuarios con dispositivos push
    registrados. Pensado para ser llamado por un scheduler externo
    (no requiere sesión de usuario), autenticado con CRON_SECRET.
    """
    if not settings.CRON_SECRET or not compare_digest(x_cron_secret, settings.CRON_SECRET):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not settings.VAPID_PRIVATE_KEY:
        return JSONResponse({"error": "VAPID no configurado"}, status_code=500)

    supabase = get_supabase_admin()
    today    = date.today()

    push_subs = supabase.table("push_subscriptions").select("user_id").execute().data or []
    user_ids  = {p["user_id"] for p in push_subs}

    total_sent     = 0
    users_notified = 0

    for uid in user_ids:
        alerts = build_alerts_for_user(supabase, uid, today)
        if not alerts:
            continue

        sent = send_alerts_to_user(supabase, uid, alerts)
        if sent:
            total_sent += sent
            users_notified += 1

    return JSONResponse({
        "sent":          total_sent,
        "users_notified": users_notified,
        "users_checked":  len(user_ids),
    })

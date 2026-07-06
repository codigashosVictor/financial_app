import json
from pywebpush import webpush, WebPushException
from app.config import settings


def send_alerts_to_user(supabase, user_id: str, alerts: list) -> int:
    """Envía cada alerta a todos los dispositivos push del usuario. Devuelve cuántas se enviaron."""
    if not alerts:
        return 0

    subs_push = supabase.table("push_subscriptions").select("*").eq("user_id", user_id).execute()
    if not subs_push.data:
        return 0

    sent = 0
    for sub in subs_push.data:
        for alert in alerts:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {
                            "p256dh": sub["p256dh"],
                            "auth": sub["auth"],
                        },
                    },
                    data=json.dumps(alert),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_EMAIL},
                )
                sent += 1
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    supabase.table("push_subscriptions").delete().eq("endpoint", sub["endpoint"]).execute()

    return sent

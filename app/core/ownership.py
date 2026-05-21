from fastapi import HTTPException


def first_or_404(response, message: str):
    data = response.data or []
    if not data:
        raise HTTPException(status_code=404, detail=message)
    return data[0]


def get_owned_card(supabase, user_id: str, card_id: str, fields: str = "*", active_only: bool = False):
    query = supabase.table("credit_cards")\
        .select(fields)\
        .eq("id", card_id)\
        .eq("user_id", user_id)
    if active_only:
        query = query.eq("is_active", True)
    return first_or_404(query.execute(), "Tarjeta no encontrada")


def get_owned_subscription(supabase, user_id: str, sub_id: str, fields: str = "*"):
    return first_or_404(
        supabase.table("subscriptions")
        .select(fields)
        .eq("id", sub_id)
        .eq("user_id", user_id)
        .execute(),
        "Suscripción no encontrada",
    )


def get_owned_installment_plan(supabase, user_id: str, plan_id: str, fields: str = "*"):
    return first_or_404(
        supabase.table("installment_plans")
        .select(fields)
        .eq("id", plan_id)
        .eq("user_id", user_id)
        .execute(),
        "Plan no encontrado",
    )

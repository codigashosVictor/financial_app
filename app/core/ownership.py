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


def get_owned_card_payment(supabase, user_id: str, payment_id: str, fields: str = "*"):
    return first_or_404(
        supabase.table("card_payments")
        .select(fields)
        .eq("id", payment_id)
        .eq("user_id", user_id)
        .execute(),
        "Pago no encontrado",
    )


def get_owned_income(supabase, user_id: str, income_id: str, fields: str = "*"):
    return first_or_404(
        supabase.table("incomes")
        .select(fields)
        .eq("id", income_id)
        .eq("user_id", user_id)
        .execute(),
        "Ingreso no encontrado",
    )


def get_owned_account(supabase, user_id: str, account_id: str, fields: str = "*", active_only: bool = False):
    query = supabase.table("accounts")\
        .select(fields)\
        .eq("id", account_id)\
        .eq("user_id", user_id)
    if active_only:
        query = query.eq("is_active", True)
    return first_or_404(query.execute(), "Cuenta no encontrada")


def get_owned_debt(supabase, user_id: str, debt_id: str, fields: str = "*", active_only: bool = False):
    query = supabase.table("debts")\
        .select(fields)\
        .eq("id", debt_id)\
        .eq("user_id", user_id)
    if active_only:
        query = query.eq("is_active", True)
    return first_or_404(query.execute(), "Deuda no encontrada")

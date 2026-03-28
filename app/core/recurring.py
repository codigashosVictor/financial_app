from datetime import date
from dateutil.relativedelta import relativedelta
from app.core.billing_cycle import get_billing_period

def generate_subscription_expenses(supabase, user_id: str, user_token: str):
    """
    Revisa todas las suscripciones activas y genera el gasto
    en expenses si aún no existe para el periodo actual.
    """
    today = date.today()
    client = supabase

    subs_res = client.table("subscriptions")\
        .select("*, credit_cards(cut_day)")\
        .eq("user_id", user_id)\
        .eq("is_active", True)\
        .execute()

    generated = 0
    for sub in (subs_res.data or []):
        cut_day = sub["credit_cards"]["cut_day"] if sub.get("credit_cards") else today.day
        charge_date = today.replace(day=min(sub["charge_day"], 28))
        billing_period = get_billing_period(charge_date, cut_day)

        # Verificar si ya existe el gasto para este periodo
        existing = client.table("expenses")\
            .select("id")\
            .eq("subscription_id", sub["id"])\
            .eq("billing_period", billing_period)\
            .execute()

        if not existing.data:
            client.table("expenses").insert({
                "user_id": user_id,
                "card_id": sub["card_id"],
                "merchant": sub["name"],
                "amount": sub["amount"],
                "tax_amount": 0,
                "category": sub["category"],
                "expense_date": charge_date.isoformat(),
                "billing_period": billing_period,
                "source": "subscription",
                "subscription_id": sub["id"],
                "notes": f"Suscripción automática — {sub['name']}",
            }).execute()
            generated += 1

    return generated


def generate_installment_expenses(supabase, user_id: str):
    """
    Revisa todos los planes MSI activos y genera la cuota mensual
    en expenses si aún no existe para cada periodo pendiente.
    """
    today = date.today()
    client = supabase

    plans_res = client.table("installment_plans")\
        .select("*, credit_cards(cut_day)")\
        .eq("user_id", user_id)\
        .eq("is_active", True)\
        .execute()

    generated = 0
    for plan in (plans_res.data or []):
        cut_day = plan["credit_cards"]["cut_day"] if plan.get("credit_cards") else today.day
        start_year, start_month = map(int, plan["start_period"].split("-"))
        start = date(start_year, start_month, 1)

        for i in range(plan["installments"]):
            period_date = start + relativedelta(months=i)
            billing_period = period_date.strftime("%Y-%m")

            # Solo generar periodos pasados y el actual (no futuros)
            period_cutoff = date(today.year, today.month, 1)
            if period_date > period_cutoff:
                continue

            existing = client.table("expenses")\
                .select("id")\
                .eq("installment_plan_id", plan["id"])\
                .eq("billing_period", billing_period)\
                .execute()

            if not existing.data:
                charge_date = period_date.replace(day=min(plan["start_date_day"] if "start_date_day" in plan else 1, 28))
                client.table("expenses").insert({
                    "user_id": user_id,
                    "card_id": plan["card_id"],
                    "merchant": plan["name"],
                    "amount": plan["monthly_amount"],
                    "tax_amount": 0,
                    "category": plan["category"],
                    "expense_date": period_date.replace(day=1).isoformat(),
                    "billing_period": billing_period,
                    "source": "installment",
                    "installment_plan_id": plan["id"],
                    "notes": f"MSI {i+1}/{plan['installments']} — {plan['name']}",
                }).execute()
                generated += 1

    return generated


def get_installment_status(plan: dict, current_period: str) -> dict:
    """
    Calcula el estado actual de un plan MSI.
    """
    start_year, start_month = map(int, plan["start_period"].split("-"))
    cur_year, cur_month = map(int, current_period.split("-"))

    months_elapsed = (cur_year - start_year) * 12 + (cur_month - start_month) + 1
    paid = min(months_elapsed, plan["installments"])
    remaining = max(plan["installments"] - paid, 0)
    paid_amount = paid * plan["monthly_amount"]
    remaining_amount = remaining * plan["monthly_amount"]

    return {
        "paid": paid,
        "remaining": remaining,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount,
        "progress_pct": round((paid / plan["installments"]) * 100),
        "is_done": remaining == 0,
    }
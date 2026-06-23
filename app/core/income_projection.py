from datetime import date, datetime, timedelta

DEFAULT_WEEKLY_AMOUNT = 5100.00
DEFAULT_PAYDAY_WEEKDAY = 4  # Friday (Monday=0)
DEFAULT_SOURCE = "Nomina semanal"


def _to_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _iter_weekdays(start_date: date, end_date: date, weekday: int):
    days_until = (weekday - start_date.weekday()) % 7
    current = start_date + timedelta(days=days_until)
    while current <= end_date:
        yield current
        current += timedelta(days=7)


def get_or_create_income_rule(supabase, user_id: str) -> dict:
    existing = (
        supabase.table("income_rules")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    ).data or []
    if existing:
        return existing[0]

    created = (
        supabase.table("income_rules")
        .insert(
            {
                "user_id": user_id,
                "weekly_amount": DEFAULT_WEEKLY_AMOUNT,
                "payday_weekday": DEFAULT_PAYDAY_WEEKDAY,
                "source_label": DEFAULT_SOURCE,
            }
        )
        .execute()
    ).data or []
    return created[0] if created else {
        "user_id": user_id,
        "weekly_amount": DEFAULT_WEEKLY_AMOUNT,
        "payday_weekday": DEFAULT_PAYDAY_WEEKDAY,
        "source_label": DEFAULT_SOURCE,
    }


def ensure_weekly_income_projections(
    supabase,
    user_id: str,
    start_date: date,
    end_date: date,
    rule: dict,
) -> None:
    today = date.today()
    existing = (
        supabase.table("incomes")
        .select("id, income_date, amount, is_projected")
        .eq("user_id", user_id)
        .eq("source", rule["source_label"])
        .gte("income_date", start_date.isoformat())
        .lte("income_date", end_date.isoformat())
        .execute()
    ).data or []

    by_date = {row["income_date"]: row for row in existing}

    for payday in _iter_weekdays(start_date, end_date, int(rule["payday_weekday"])):
        day_key = payday.isoformat()
        current = by_date.get(day_key)

        if not current:
            supabase.table("incomes").insert(
                {
                    "user_id": user_id,
                    "source": rule["source_label"],
                    "amount": round(float(rule["weekly_amount"]), 2),
                    "income_date": day_key,
                    "notes": "Proyeccion automatica",
                    "is_projected": True,
                }
            ).execute()
            continue

        # Reconfigure only upcoming projected weeks.
        if (
            current.get("is_projected")
            and _to_date(current["income_date"]) >= today
            and round(float(current["amount"]), 2) != round(float(rule["weekly_amount"]), 2)
        ):
            (
                supabase.table("incomes")
                .update({"amount": round(float(rule["weekly_amount"]), 2)})
                .eq("id", current["id"])
                .eq("user_id", user_id)
                .execute()
            )

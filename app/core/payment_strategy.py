import google.generativeai as genai
from app.config import settings
from datetime import date
from app.core.billing_cycle import get_billing_period, get_payment_due_date

genai.configure(api_key=settings.GEMINI_API_KEY)

async def analyze_payment_strategy(
    cards: list,
    expenses: list,
    strategy_type: str,
    current_period: str
) -> str:
    today = date.today()

    # Construir resumen de cada tarjeta
    card_summaries = []
    for card in cards:
        total = sum(e["amount"] for e in expenses if e.get("card_id") == card["id"])
        due = get_payment_due_date(current_period, card["cut_day"], card["payment_due_day"])
        days_left = (due - today).days

        card_summaries.append(
            f"- {card['name']}: saldo periodo actual ${total:,.2f} MXN, "
            f"fecha límite de pago {due.strftime('%d %b %Y')} ({days_left} días)"
            + (f", límite de crédito ${card['credit_limit']:,.2f}" if card.get("credit_limit") else "")
        )

    # Resumen de gastos por categoría
    cat_totals = {}
    for exp in expenses:
        cat = exp.get("category", "Otro")
        cat_totals[cat] = cat_totals.get(cat, 0) + exp["amount"]

    cat_summary = "\n".join([f"  - {k}: ${v:,.2f}" for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])])

    strategy_instructions = {
        "snowball": "Aplica el método bola de nieve: sugiere pagar primero la tarjeta con menor saldo total para eliminarla rápido y liberar flujo de efectivo.",
        "avalanche": "Aplica el método avalancha: sugiere pagar primero la tarjeta con mayor costo (considera fechas de corte próximas como prioridad urgente).",
        "recommendation": "Analiza qué tarjeta conviene usar para los próximos gastos según las fechas de corte (para maximizar días de gracia antes del pago).",
    }

    prompt = f"""
Eres un asesor financiero personal experto en tarjetas de crédito mexicanas.
Analiza la siguiente situación financiera y da recomendaciones claras, específicas y accionables.
Responde en español, de forma conversacional pero profesional. Usa emojis con moderación.
Formato: párrafos cortos, máximo 250 palabras. Sin listas interminables.

FECHA HOY: {today.strftime('%d de %B de %Y')}
PERIODO ANALIZADO: {current_period}

TARJETAS:
{chr(10).join(card_summaries)}

GASTOS POR CATEGORÍA ESTE PERIODO:
{cat_summary if cat_summary else "  Sin gastos registrados"}

INSTRUCCIÓN: {strategy_instructions.get(strategy_type, strategy_instructions['recommendation'])}

Da tu análisis y recomendación concreta ahora:
"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()
import google.generativeai as genai
import json, base64
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

EXTRACTION_PROMPT = """
Analiza esta imagen de un ticket/recibo y extrae la información en formato JSON.
Responde ÚNICAMENTE con el JSON puro, sin texto adicional, sin bloques markdown, sin explicaciones.

Formato exacto requerido:
{
  "merchant": "nombre del comercio",
  "date": "YYYY-MM-DD",
  "amount": 0.00,
  "tax_amount": 0.00,
  "category": "una de estas exactas: Alimentación|Transporte|Entretenimiento|Salud|Ropa|Tecnología|Hogar|Otro",
  "confidence": 0.95
}

Reglas:
- amount debe ser el TOTAL del ticket incluyendo impuestos
- tax_amount solo los impuestos (IVA, etc.)
- Si no puedes leer un campo con certeza, usa null
- La fecha debe estar en formato YYYY-MM-DD
"""

async def process_receipt_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Envía imagen a Gemini y retorna datos estructurados del ticket.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")

    image_part = {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(image_bytes).decode("utf-8")
        }
    }

    try:
        response = model.generate_content([EXTRACTION_PROMPT, image_part])
        raw = response.text.strip()
        # Limpiar si Gemini manda markdown a pesar de las instrucciones
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return {"error": "No se pudo parsear la respuesta", "raw": response.text}
    except Exception as e:
        return {"error": str(e)}
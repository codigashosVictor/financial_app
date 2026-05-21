# Finance App

App privada para controlar tarjetas de crédito, gastos, presupuestos, suscripciones, pagos a meses, calendario financiero, OCR de tickets y recomendaciones con IA.

## Requisitos

- Python 3.11+
- Cuenta/proyecto de Supabase
- API key de Gemini si usarás OCR o asistente IA

## Setup local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Completa `.env` con tus credenciales de Supabase, Gemini y una `SECRET_KEY` larga.

## Variables de entorno

Consulta [.env.example](.env.example). Las variables VAPID son opcionales salvo que habilites notificaciones push.

## Correr en desarrollo

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abre `http://localhost:8000`.

## Tests

```bash
python3 -m compileall app
pytest
```

## Deploy en Railway

El proyecto incluye `railway.toml`. Railway debe ejecutar:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

El healthcheck público es `/healthz`.

## Supabase

La app espera tablas para usuarios/autenticación, tarjetas, gastos, presupuestos, suscripciones, planes MSI, logs de IA y push subscriptions. Configura RLS para que cada usuario solo pueda leer y escribir sus propios registros. El backend también valida `user_id` en operaciones sensibles.

## Módulos principales

- `app/main.py`: inicialización de FastAPI, routers, CORS y healthcheck.
- `app/core/session.py`: protección de sesión y refresh de token Supabase.
- `app/core/csrf.py`: generación y validación CSRF.
- `app/core/ownership.py`: helpers defensivos de ownership.
- `app/core/billing_cycle.py`: cálculo de periodos de corte y fechas de pago.
- `app/core/recurring.py`: generación de gastos de suscripciones y MSI.
- `app/api/`: rutas de la aplicación.
- `app/templates/`: vistas Jinja.
- `static/`: assets PWA/frontend.
- `docs/card-payments-spec.md`: diseño propuesto para pagos de tarjeta.

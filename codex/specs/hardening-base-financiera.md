# Spec: Finance App Hardening + Base Financiera

## Contexto

Este proyecto es una app FastAPI llamada `finance-app` para control de finanzas personales. Usa:

- FastAPI
- Jinja templates
- Supabase
- Sesiones con Starlette
- Tarjetas de crédito
- Gastos
- Presupuestos
- Suscripciones
- MSI/installments
- OCR con Gemini
- Push notifications

El objetivo de esta tarea es fortalecer la base del proyecto antes de agregar más funcionalidades grandes.

## Objetivo principal

Implementar un primer hardening de seguridad y confiabilidad:

1. Proteger formularios `POST` contra CSRF.
2. Corregir validaciones de ownership por `user_id`.
3. Restringir CORS por configuración.
4. Evitar que errores internos borren la sesión silenciosamente.
5. Agregar `/healthz`.
6. Completar `.env.example`.
7. Crear tests mínimos para lógica crítica.
8. Preparar la base para una futura feature de pagos de tarjeta, sin implementar todavía toda la UI si resulta demasiado grande.

## Reglas de trabajo

- No romper la UI existente.
- Mantener el estilo actual del proyecto.
- No reescribir la app completa.
- No tocar secretos reales.
- No asumir que Supabase RLS siempre protege todo; el backend también debe validar `user_id`.
- Si hay cambios existentes en Git que no son tuyos, no los reviertas.
- Priorizar cambios pequeños, claros y testeables.

## Task 1: CSRF en formularios

Agregar protección CSRF para todos los formularios y endpoints mutables.

### Requisitos

- Crear utilidad/middleware/helper para generar y validar token CSRF por sesión.
- Inyectar `csrf_token` en templates.
- Agregar `<input type="hidden" name="csrf_token" ...>` a todos los formularios `POST`.
- Validar token en endpoints `POST` que reciben formularios.
- Para endpoints JSON/fetch mutables, aceptar token por header, por ejemplo `X-CSRF-Token`, o documentar y aplicar una solución consistente.
- Si el token falla, devolver `403`.

### Formularios/endpoints a revisar

- `/login`
- `/cards/nuevo`
- `/cards/{card_id}/editar`
- `/cards/{card_id}/eliminar`
- `/expenses/nuevo`
- `/expenses/scan/guardar`
- `/expenses/{expense_id}/eliminar`
- `/subscriptions/nuevo`
- `/subscriptions/{sub_id}/toggle`
- `/subscriptions/{sub_id}/eliminar`
- `/installments/nuevo`
- `/installments/{plan_id}/eliminar`
- `/budgets/save`
- `/budgets/copy`
- `/ai/analyze`
- `/push/subscribe`
- `/push/unsubscribe`
- `/push/send-alerts`

Si algún endpoint no debe tener CSRF por diseño, dejar comentario breve explicando por qué.

## Task 2: Ownership y autorización defensiva

Revisar todos los accesos por `id` y asegurar que filtran por `user_id` cuando aplique.

### Casos conocidos a corregir

En `app/api/expenses.py`:

- Al crear gasto, cuando se lee la tarjeta por `card_id`, también filtrar por `user_id`.
- En `/scan/guardar`, lo mismo.
- Si la tarjeta no pertenece al usuario, devolver error o redirigir con mensaje.

En `app/api/subscriptions.py`:

- En toggle, leer la suscripción con `.eq("id", sub_id).eq("user_id", user["id"])`.
- Si no existe, devolver 404 o redirigir sin modificar.

En `app/api/installments.py`:

- Al crear plan, leer tarjeta con `.eq("id", card_id).eq("user_id", user["id"])`.
- Al eliminar plan, primero verificar que el plan pertenece al usuario.
- Al eliminar gastos generados por ese plan, filtrar también por `user_id`.

Revisar también:

- `cards.py`
- `budgets.py`
- `push.py`
- `ai_assistant.py`
- `recurring.py`

### Resultado esperado

Ninguna operación mutable debe depender solo de un `id` enviado por el cliente.

## Task 3: CORS configurable

Actualmente CORS permite todos los origins.

### Requisitos

- Agregar setting `ALLOWED_ORIGINS`.
- Leer desde env como string separado por comas.
- En desarrollo permitir localhost si no se configura.
- En producción no usar `["*"]` por defecto.
- Actualizar `.env.example`.

Ejemplo:

```env
ALLOWED_ORIGINS=http://localhost:8000,https://mi-dominio.com
```

## Task 4: Manejo de errores en SessionMiddleware

Actualmente `app/core/session.py` captura cualquier excepción, limpia sesión y redirige a login.

### Requisitos

- No borrar sesión para errores internos genéricos.
- Mantener limpieza de sesión solo cuando el refresh token falla o la sesión es inválida.
- Para errores no esperados, dejar que FastAPI los maneje o registrar el error y devolver 500.
- Evitar esconder bugs reales.

## Task 5: Healthcheck

Agregar endpoint:

```txt
GET /healthz
```

Respuesta esperada:

```json
{"ok": true}
```

Debe ser público y no requerir sesión.

Actualizar `railway.toml` para usar:

```toml
healthcheckPath = "/healthz"
```

## Task 6: `.env.example` completo

Actualizar `.env.example` con todas las variables usadas por el código:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
GEMINI_API_KEY=
SECRET_KEY=
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_EMAIL=mailto:admin@example.com
ALLOWED_ORIGINS=http://localhost:8000
```

Si alguna variable no es obligatoria, indicarlo en comentario.

## Task 7: Tests mínimos

Agregar estructura de tests.

### Requisitos

- Agregar `pytest` y dependencias necesarias de test.
- Crear carpeta `tests/`.
- Agregar configuración mínima si hace falta.

### Tests requeridos

Crear tests unitarios para:

#### `app/core/billing_cycle.py`

Casos:

- Gasto antes del día de corte queda en mes actual.
- Gasto en día de corte queda en mes actual.
- Gasto después del corte queda en mes siguiente.
- Fecha límite de pago respeta meses con menos días.
- Día de pago 31 en febrero no rompe.

#### `app/core/recurring.py`

Si testear directo con Supabase es difícil, crear fake/mock client.

Casos:

- Suscripción no duplica gasto si ya existe.
- Suscripción crea gasto con `user_id`.
- MSI no duplica cuota si ya existe.
- MSI respeta número de cuotas.

#### Ownership

Agregar tests donde sea razonable usando `TestClient` y mocks, o al menos tests de helpers si se extraen helpers.

Validar que:

- No se puede usar una tarjeta que no pertenece al usuario.
- No se elimina un plan MSI ajeno.
- No se hace toggle de suscripción ajena.

## Task 8: Preparación para pagos de tarjeta

No implementar toda la funcionalidad si es demasiado grande, pero dejar una base clara.

### Crear modelo conceptual/documentación

Agregar archivo:

```txt
docs/card-payments-spec.md
```

Debe describir:

- Tabla sugerida `card_payments`.
- Campos:
  - `id`
  - `user_id`
  - `card_id`
  - `billing_period`
  - `amount`
  - `payment_date`
  - `notes`
  - `created_at`
- Constraints:
  - FK a usuario/tarjeta
  - indice por `user_id`, `card_id`, `billing_period`
- Comportamiento esperado:
  - permitir pagos parciales
  - calcular saldo pendiente como gastos del periodo menos pagos
  - mostrar pagado/pendiente en dashboard
  - no bloquear nuevos gastos despues de pagar, pero distinguirlos por periodo

Si es sencillo, tambien crear funciones puras testeables para calcular:

```python
pending = total_expenses - total_payments
is_paid = pending <= 0
```

Pero no sobre-implementar UI en esta tarea.

## Task 9: README mínimo útil

Actualizar `README.md` con:

- Qué es el proyecto.
- Requisitos.
- Setup local.
- Variables de entorno.
- Cómo correr dev server.
- Cómo correr tests.
- Deploy Railway.
- Notas de Supabase/RLS.
- Módulos principales.

Mantenerlo breve pero suficiente.

## Criterios de aceptación

La tarea se considera terminada si:

- Todos los formularios mutables tienen CSRF.
- Endpoints mutables validan ownership.
- CORS ya no está abierto por default.
- `/healthz` funciona sin sesión.
- `railway.toml` usa `/healthz`.
- `.env.example` está completo.
- Hay tests mínimos para fechas/recurrencias/ownership crítico.
- `python3 -m compileall app` pasa.
- `pytest` pasa.
- README tiene instrucciones reales de uso.
- No se revierten cambios ajenos.

## Comandos de verificación

Ejecutar:

```bash
python3 -m compileall app
pytest
```

Si falta instalar dependencias, actualizar `requirements.txt` o crear `requirements-dev.txt`, según el estilo que encaje mejor con el repo.

## Notas importantes

- El proyecto actualmente tiene cambios locales en `app/core/recurring.py`; revisar antes de editar y no revertir cambios ajenos.
- Hay una carpeta `.claude/` sin trackear; ignorarla salvo que sea relevante.
- La app usa Supabase; no hacer llamadas reales en tests si se pueden mockear.

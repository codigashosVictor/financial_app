# Card Payments Spec

## Objetivo

Permitir registrar pagos parciales o totales de tarjetas por periodo de facturación y calcular cuánto queda pendiente.

## Tabla sugerida: `card_payments`

Campos:

- `id`: UUID primary key.
- `user_id`: UUID del usuario dueño del pago.
- `card_id`: UUID de la tarjeta pagada.
- `billing_period`: periodo al que aplica el pago, formato `YYYY-MM`.
- `amount`: monto pagado.
- `payment_date`: fecha real del pago.
- `notes`: notas opcionales.
- `created_at`: timestamp de creación.

## Constraints e índices

- Foreign key `card_id` hacia `credit_cards.id`.
- `user_id` debe coincidir con el dueño de la tarjeta.
- Índice por `(user_id, card_id, billing_period)`.
- Check `amount > 0`.
- RLS: cada usuario solo puede leer/escribir sus pagos.

## Comportamiento

- Permitir múltiples pagos para la misma tarjeta y periodo.
- Calcular:

```python
pending = total_expenses - total_payments
is_paid = pending <= 0
```

- Dashboard debe mostrar por tarjeta:
  - total del periodo
  - total pagado
  - saldo pendiente
  - estado pagado/pendiente
- No bloquear nuevos gastos después de registrar un pago; los gastos siguen agrupados por `billing_period`.
- Si hay sobrepago, `pending` puede quedar negativo y la UI puede mostrarlo como saldo a favor.

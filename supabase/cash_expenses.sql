
-- Run this in the Supabase SQL editor.
-- Permite registrar gastos en efectivo (sin tarjeta), ligados a una cuenta
-- de Patrimonio Neto en vez de a una credit_cards.

ALTER TABLE expenses ALTER COLUMN card_id DROP NOT NULL;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES accounts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_expenses_account_id ON expenses (account_id);

-- La columna "source" tiene un CHECK que solo permitía los valores ya
-- usados por el resto de la app (manual, ocr, subscription, installment).
-- Lo volvemos a crear agregando "cash" para los gastos en efectivo.
ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_source_check;
ALTER TABLE expenses ADD CONSTRAINT expenses_source_check
    CHECK (source IN ('manual', 'ocr', 'subscription', 'installment', 'cash'));

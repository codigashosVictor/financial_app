
-- Run this in the Supabase SQL editor
-- Seguro de volver a correr completo si una corrida anterior se cortó a medias.

CREATE TABLE IF NOT EXISTS accounts
(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('Efectivo', 'Ahorro', 'Inversión', 'Otro')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_balances
(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    balance NUMERIC(12, 2) NOT NULL CHECK (balance >= 0),
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_account_balances_user_account_date
        ON account_balances (user_id, account_id, snapshot_date);

CREATE TABLE IF NOT EXISTS debts
(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('Préstamo', 'Hipoteca', 'Otro')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS debt_balances
(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    debt_id UUID NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    balance NUMERIC(12, 2) NOT NULL CHECK (balance >= 0),
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_debt_balances_user_debt_date
        ON debt_balances (user_id, debt_id, snapshot_date);

ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE debts ENABLE ROW LEVEL SECURITY;
ALTER TABLE debt_balances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own accounts" ON accounts;
CREATE POLICY "Users manage own accounts"
        ON accounts
        FOR ALL
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users manage own account balances" ON account_balances;
CREATE POLICY "Users manage own account balances"
        ON account_balances
        FOR ALL
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users manage own debts" ON debts;
CREATE POLICY "Users manage own debts"
        ON debts
        FOR ALL
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users manage own debt balances" ON debt_balances;
CREATE POLICY "Users manage own debt balances"
        ON debt_balances
        FOR ALL
        USING (user_id = auth.uid())
        WITH CHECK (user_id = auth.uid());

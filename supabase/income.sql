-- Run this in the Supabase SQL editor

CREATE TABLE incomes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    source      TEXT NOT NULL,
    amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    income_date DATE NOT NULL,
    notes       TEXT,
    is_projected BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incomes_user_date
    ON incomes (user_id, income_date);

ALTER TABLE incomes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own incomes"
    ON incomes
    FOR ALL
    USING  (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE TABLE income_rules (
    user_id         UUID PRIMARY KEY,
    weekly_amount   NUMERIC(12, 2) NOT NULL CHECK (weekly_amount > 0),
    payday_weekday  INTEGER NOT NULL CHECK (payday_weekday >= 0 AND payday_weekday <= 6),
    source_label    TEXT NOT NULL DEFAULT 'Nomina semanal',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_income_rules_user
    ON income_rules (user_id);

ALTER TABLE income_rules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own income rules"
    ON income_rules
    FOR ALL
    USING  (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

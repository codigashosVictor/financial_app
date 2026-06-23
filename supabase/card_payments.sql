
-- Run this in the Supabase SQL editor

CREATE TABLE card_payments
(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    card_id UUID NOT NULL REFERENCES credit_cards(id) ON DELETE CASCADE,
    billing_period TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    payment_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_card_payments_user_card_period
        ON card_payments (user_id, card_id, billing_period);

ALTER TABLE card_payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own card payments"
        ON card_payments
        FOR ALL
        USING
(user_id = auth.uid
())
        WITH CHECK
(user_id = auth.uid
());

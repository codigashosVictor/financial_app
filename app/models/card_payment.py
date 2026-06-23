from pydantic import BaseModel, UUID4, field_validator
from typing import Optional
from datetime import date, datetime


class CardPaymentCreate(BaseModel):
    card_id: UUID4
    billing_period: str
    amount: float
    payment_date: date
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        return round(v, 2)


class CardPaymentResponse(CardPaymentCreate):
    id: UUID4
    user_id: UUID4
    created_at: datetime

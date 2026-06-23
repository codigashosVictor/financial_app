from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, UUID4, field_validator


class IncomeCreate(BaseModel):
    source: str
    amount: float
    income_date: date
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        return round(value, 2)


class IncomeResponse(IncomeCreate):
    id: UUID4
    user_id: UUID4
    is_projected: bool = False
    created_at: datetime

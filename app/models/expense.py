from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import date, datetime

class ExpenseCreate(BaseModel):
    card_id: Optional[UUID4] = None
    merchant: Optional[str] = None
    amount: float
    tax_amount: float = 0.0
    category: Optional[str] = None
    notes: Optional[str] = None
    expense_date: date
    source: str = "manual"

class ExpenseResponse(ExpenseCreate):
    id: UUID4
    user_id: UUID4
    billing_period: str
    receipt_url: Optional[str] = None
    created_at: datetime
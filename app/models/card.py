from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

class CardCreate(BaseModel):
    name: str
    cut_day: int
    payment_due_day: int
    credit_limit: Optional[float] = None

class CardResponse(CardCreate):
    id: UUID4
    user_id: UUID4
    is_active: bool
    created_at: datetime
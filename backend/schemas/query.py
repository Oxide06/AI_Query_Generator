from datetime import datetime
from pydantic import BaseModel, field_validator


class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        if len(v) > 1000:
            raise ValueError("Question is too long (max 1000 characters)")
        return v


class QueryResponse(BaseModel):
    question: str
    generated_sql: str
    results: list[dict]
    row_count: int
    log_id: int


class QueryLogOut(BaseModel):
    id: int
    user_id: int
    user_role: str
    natural_language: str
    generated_sql: str | None
    passed_security: bool
    rejection_reason: str | None
    executed: bool
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

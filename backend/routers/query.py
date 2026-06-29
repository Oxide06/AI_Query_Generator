from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.models.user import User
from backend.models.query_log import QueryLog
from backend.schemas.query import QueryRequest, QueryResponse, QueryLogOut
from backend.core.auth import get_current_user
from backend.core.security import validate_sql, extract_sql_from_llm_output
from backend.llm.prompt_builder import build_prompt
from backend.llm.hf_client import generate_sql
from backend.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def run_query(
    request: QueryRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Convert a natural language question to SQL and execute it.
    Full pipeline: NL → LLM → SQL parser → RBAC check → DB execution.
    Every attempt is logged regardless of outcome.
    """
    log = QueryLog(
        user_id=current_user.id,
        user_role=current_user.role.value,
        natural_language=request.question,
    )

    # 1. Optional RAG context
    rag_context: str | None = None
    if settings.USE_RAG:
        try:
            from backend.llm.rag import retrieve_context
            rag_context = retrieve_context(request.question, current_user.role.value)
        except Exception:
            pass  # RAG failure is non-fatal; continue without it

    # 2. Build prompt and call LLM
    messages = build_prompt(request.question, current_user.role, extra_context=rag_context)
    raw_output = await generate_sql(messages)

    # 3. Strip markdown fences the LLM may have added
    raw_sql = extract_sql_from_llm_output(raw_output)
    log.generated_sql = raw_sql

    # 4. Handle CANNOT_ANSWER signal from the model
    if raw_sql.upper() == "CANNOT_ANSWER":
        db.add(log)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question could not be answered with the available schema.",
        )

    # 5. Security validation + RBAC
    try:
        clean_sql = validate_sql(raw_sql, current_user.role)
        log.passed_security = True
    except HTTPException as e:
        log.passed_security = False
        log.rejection_reason = e.detail
        db.add(log)
        db.commit()
        raise

    # 6. Execute against the DB
    try:
        result = db.execute(text(clean_sql))
        rows = [dict(row._mapping) for row in result]
        log.executed = True
    except Exception as e:
        log.executed = False
        log.error_message = str(e)
        db.add(log)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {e}",
        )

    db.add(log)
    db.commit()
    db.refresh(log)

    return QueryResponse(
        question=request.question,
        generated_sql=clean_sql,
        results=rows,
        row_count=len(rows),
        log_id=log.id,
    )


@router.get("/logs", response_model=list[QueryLogOut])
def get_query_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
):
    """Return the current user's query history. Admins see all logs."""
    from backend.models.user import UserRole
    query = db.query(QueryLog)
    if current_user.role != UserRole.admin:
        query = query.filter(QueryLog.user_id == current_user.id)
    return query.order_by(QueryLog.created_at.desc()).limit(limit).all()

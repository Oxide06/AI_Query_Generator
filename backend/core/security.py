import re
import sqlglot
from sqlglot import exp
from fastapi import HTTPException, status
from backend.models.user import UserRole
from backend.core.rbac import check_permission


# ---------- Dangerous patterns (block before parsing) ----------

BLOCKED_PATTERNS = [
    r"--",                        # SQL line comment
    r"/\*.*?\*/",                 # block comment
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bATTACH\b",                # SQLite-specific: attach another DB file
    r"\bDETACH\b",
    r"\bPRAGMA\b",                # SQLite internals
    r"\bLOAD_EXTENSION\b",
    r";\s*\w",                    # stacked statements (semicolon followed by more SQL)
    r"\bINTO\s+OUTFILE\b",
    r"\bINTO\s+DUMPFILE\b",
    r"\bINFORMATION_SCHEMA\b",
    r"\bSQLITE_MASTER\b",
    r"\bSQLITE_SEQUENCE\b",
]

_BLOCKED_RE = re.compile(
    "|".join(BLOCKED_PATTERNS),
    flags=re.IGNORECASE | re.DOTALL,
)

# Only these top-level statement types are allowed through
ALLOWED_STATEMENT_TYPES = {exp.Select}


def validate_sql(sql: str, role: UserRole) -> str:
    """
    Full validation pipeline:
      1. Strip and basic sanity check
      2. Block dangerous patterns via regex
      3. Parse with sqlglot
      4. Enforce allowed statement types
      5. Check table-level RBAC permissions

    Returns the cleaned SQL string if valid, raises HTTPException otherwise.
    """
    sql = sql.strip().rstrip(";")

    if not sql:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty SQL generated")

    # 1. Regex pre-filter
    match = _BLOCKED_RE.search(sql)
    if match:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"SQL contains a blocked pattern: '{match.group()}'",
        )

    # 2. Parse
    try:
        statements = sqlglot.parse(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQL could not be parsed: {e}",
        )

    if not statements or len(statements) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one SQL statement is required",
        )

    statement = statements[0]

    # 3. Statement type whitelist
    if not isinstance(statement, tuple(ALLOWED_STATEMENT_TYPES)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Statement type '{type(statement).__name__}' is not allowed. Only SELECT is permitted.",
        )

    # 4. Extract all referenced tables and check RBAC
    tables = _extract_tables(statement)
    if not tables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tables found in SQL",
        )

    for table in tables:
        check_permission(role, table, "SELECT")

    return sql


def _extract_tables(statement: exp.Expression) -> set[str]:
    """Walk the AST and collect all table names (handles JOINs and subqueries)."""
    return {
        table.name.lower()
        for table in statement.find_all(exp.Table)
        if table.name
    }


def extract_sql_from_llm_output(raw: str) -> str:
    """
    LLMs often wrap SQL in markdown code blocks. Strip them out.
    Falls back to the raw string if no code block is found.
    """
    # Match ```sql ... ``` or ``` ... ```
    match = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Sometimes the model just outputs the SQL with no fences
    return raw.strip()

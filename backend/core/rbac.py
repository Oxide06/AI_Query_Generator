from fastapi import HTTPException, status
from backend.models.user import UserRole


# ---------- Permission map ----------
# Format: role -> { table_name -> set of allowed SQL operations }
# Add your actual application tables here.

ROLE_PERMISSIONS: dict[UserRole, dict[str, set[str]]] = {
    UserRole.admin: {
        # Admin can do anything on any table
        "*": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    },
    UserRole.analyst: {
        # Analysts can read most tables and insert into reports
        "users":        {"SELECT"},
        "query_logs":   {"SELECT"},
        "products":     {"SELECT"},
        "orders":       {"SELECT"},
        "customers":    {"SELECT"},
        "reports":      {"SELECT", "INSERT"},
    },
    UserRole.viewer: {
        # Viewers get read-only access to a limited set
        "products":     {"SELECT"},
        "orders":       {"SELECT"},
    },
}


def get_allowed_tables(role: UserRole) -> set[str]:
    """Return the set of table names accessible to this role."""
    perms = ROLE_PERMISSIONS.get(role, {})
    if "*" in perms:
        return {"*"}  # admin wildcard
    return set(perms.keys())


def check_permission(role: UserRole, table: str, operation: str) -> None:
    """
    Raise HTTP 403 if the role cannot perform `operation` on `table`.
    Called once per table referenced in the generated SQL.
    """
    perms = ROLE_PERMISSIONS.get(role, {})

    # Wildcard (admin)
    if "*" in perms and operation in perms["*"]:
        return

    table_perms = perms.get(table)
    if table_perms is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' has no access to table '{table}'",
        )

    if operation not in table_perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' cannot perform {operation} on table '{table}'",
        )


def get_schema_context_for_role(role: UserRole) -> str:
    """
    Return a description of accessible tables to inject into the LLM prompt.
    Keeps the LLM from generating SQL for tables the user can't access.
    """
    allowed = get_allowed_tables(role)

    # Full schema descriptions — update these to match your actual DB schema
    schema_descriptions: dict[str, str] = {
        "users":      "users(id INT, username TEXT, email TEXT, role TEXT, is_active BOOL, created_at DATETIME)",
        "query_logs": "query_logs(id INT, user_id INT, natural_language TEXT, generated_sql TEXT, passed_security BOOL, created_at DATETIME)",
        "products":   "products(id INT, name TEXT, price REAL, stock INT, category TEXT)",
        "orders":     "orders(id INT, customer_id INT, product_id INT, quantity INT, total REAL, created_at DATETIME)",
        "customers":  "customers(id INT, name TEXT, email TEXT, city TEXT)",
        "reports":    "reports(id INT, title TEXT, content TEXT, created_by INT, created_at DATETIME)",
    }

    if "*" in allowed:
        tables = schema_descriptions
    else:
        tables = {t: schema_descriptions[t] for t in allowed if t in schema_descriptions}

    lines = ["The following tables are available:"]
    for desc in tables.values():
        lines.append(f"  - {desc}")
    return "\n".join(lines)

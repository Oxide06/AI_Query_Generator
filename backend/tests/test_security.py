import pytest
from fastapi import HTTPException
from backend.models.user import UserRole
from backend.core.security import validate_sql, extract_sql_from_llm_output


# ---------- extract_sql_from_llm_output ----------

def test_strips_sql_code_block():
    raw = "```sql\nSELECT * FROM products\n```"
    assert extract_sql_from_llm_output(raw) == "SELECT * FROM products"

def test_strips_generic_code_block():
    raw = "```\nSELECT id FROM orders\n```"
    assert extract_sql_from_llm_output(raw) == "SELECT id FROM orders"

def test_passthrough_plain_sql():
    raw = "SELECT id FROM orders"
    assert extract_sql_from_llm_output(raw) == raw


# ---------- validate_sql — blocked patterns ----------

@pytest.mark.parametrize("sql", [
    "SELECT * FROM products -- bypass",
    "SELECT * FROM products /* comment */",
    "DROP TABLE products",
    "SELECT * FROM products; DROP TABLE products",
    "TRUNCATE products",
    "SELECT * FROM sqlite_master",
    "PRAGMA table_info(products)",
    "ALTER TABLE products ADD COLUMN x TEXT",
])
def test_blocked_patterns(sql):
    with pytest.raises(HTTPException) as exc:
        validate_sql(sql, UserRole.admin)
    assert exc.value.status_code in (400, 403)


# ---------- validate_sql — statement type ----------

@pytest.mark.parametrize("sql", [
    "INSERT INTO products (name) VALUES ('x')",
    "UPDATE products SET name='x' WHERE id=1",
    "DELETE FROM products WHERE id=1",
])
def test_mutating_statements_blocked(sql):
    with pytest.raises(HTTPException) as exc:
        validate_sql(sql, UserRole.admin)
    assert exc.value.status_code == 403


# ---------- validate_sql — RBAC ----------

def test_viewer_can_select_products():
    sql = "SELECT * FROM products"
    result = validate_sql(sql, UserRole.viewer)
    assert "products" in result.lower()

def test_viewer_cannot_select_users():
    with pytest.raises(HTTPException) as exc:
        validate_sql("SELECT * FROM users", UserRole.viewer)
    assert exc.value.status_code == 403

def test_analyst_can_select_users():
    result = validate_sql("SELECT id, username FROM users", UserRole.analyst)
    assert result is not None

def test_admin_can_select_anything():
    result = validate_sql("SELECT * FROM query_logs", UserRole.admin)
    assert result is not None

def test_join_checks_all_tables():
    # viewer can't access users, so this join should fail
    sql = "SELECT p.name, u.username FROM products p JOIN users u ON p.id = u.id"
    with pytest.raises(HTTPException) as exc:
        validate_sql(sql, UserRole.viewer)
    assert exc.value.status_code == 403

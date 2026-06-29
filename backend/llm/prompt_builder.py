from backend.models.user import UserRole
from backend.core.rbac import get_schema_context_for_role


SYSTEM_PROMPT = """You are a SQL query generator. Your ONLY job is to convert a natural language question into a valid SQLite SELECT statement.

Rules you MUST follow:
- Output ONLY the raw SQL query. No explanation, no markdown, no code blocks.
- Only generate SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, or any other statement.
- Only use the tables and columns listed in the schema below.
- Do not reference any tables not listed in the schema.
- Use proper SQLite syntax.
- If the question cannot be answered with the available schema, output exactly: CANNOT_ANSWER
"""


def build_prompt(
    question: str,
    role: UserRole,
    extra_context: str | None = None,
) -> list[dict]:
    """
    Build the messages list for the Hugging Face chat completion API.

    Args:
        question: The user's natural language question.
        role: Used to fetch the role-filtered schema context.
        extra_context: Optional RAG-retrieved schema snippets.

    Returns:
        A list of message dicts in OpenAI chat format.
    """
    schema_context = get_schema_context_for_role(role)

    user_content_parts = [schema_context]

    if extra_context:
        user_content_parts.append(f"\nAdditional context:\n{extra_context}")

    user_content_parts.append(f"\nQuestion: {question}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_content_parts)},
    ]

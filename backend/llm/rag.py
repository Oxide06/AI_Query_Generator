"""
Optional RAG module using ChromaDB.
Only active when USE_RAG=true in .env.
Embeds schema descriptions and retrieves relevant ones per query.
"""
from __future__ import annotations

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        raise RuntimeError(
            "chromadb is not installed. Run: pip install chromadb"
        )

    from backend.config import get_settings
    settings = get_settings()

    _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    ef = embedding_functions.DefaultEmbeddingFunction()
    _collection = _client.get_or_create_collection(
        name="schema_context",
        embedding_function=ef,
    )
    return _collection


def index_schema(schema_docs: list[dict]) -> None:
    """
    Index schema descriptions into ChromaDB.
    Call this once at startup or via a management command.

    schema_docs format:
        [{"id": "table_products", "text": "products(id INT, name TEXT, ...)", "role": "viewer"}, ...]
    """
    collection = _get_collection()
    collection.upsert(
        ids=[doc["id"] for doc in schema_docs],
        documents=[doc["text"] for doc in schema_docs],
        metadatas=[{"role": doc.get("role", "viewer")} for doc in schema_docs],
    )


def retrieve_context(question: str, role: str, n_results: int = 3) -> str:
    """
    Retrieve the most relevant schema snippets for the question.
    Filters by role so users only get context for tables they can access.

    Returns a string to inject into the LLM prompt.
    """
    collection = _get_collection()

    results = collection.query(
        query_texts=[question],
        n_results=n_results,
        where={"role": {"$in": [role, "admin"]}},
    )

    docs = results.get("documents", [[]])[0]
    if not docs:
        return ""

    return "Relevant schema context:\n" + "\n".join(f"  - {d}" for d in docs)

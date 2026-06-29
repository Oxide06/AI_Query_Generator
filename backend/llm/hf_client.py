import httpx
from fastapi import HTTPException, status
from backend.config import get_settings

settings = get_settings()

HF_API_URL = f"https://api-inference.huggingface.co/models/{settings.HF_MODEL}/v1/chat/completions"


async def generate_sql(messages: list[dict]) -> str:
    """
    Send a chat completion request to Hugging Face Inference API.

    Args:
        messages: List of {"role": ..., "content": ...} dicts.

    Returns:
        The model's raw text output (SQL or CANNOT_ANSWER).
    """
    if not settings.HF_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HF_TOKEN is not configured. Set it in your .env file.",
        )

    headers = {
        "Authorization": f"Bearer {settings.HF_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.HF_MODEL,
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.1,   # low temp = more deterministic SQL
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(HF_API_URL, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="LLM request timed out",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM API error {e.response.status_code}: {e.response.text}",
            )

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unexpected LLM response format: {data}",
        )

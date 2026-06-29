from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import create_tables
from backend.routers import auth, query, admin
from backend.core.auth import get_current_user
from backend.models.user import User
from backend.schemas.user import UserOut

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Secure LLM-based natural language interface for database queries with RBAC.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(query.router)
app.include_router(admin.router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/me", response_model=UserOut, tags=["auth"])
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Returns the currently authenticated user's profile."""
    return current_user

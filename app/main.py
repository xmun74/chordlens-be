from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db import init_supabase
from app.routers import extract


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_supabase(settings.supabase_url, settings.supabase_key)
    print("CodeLens API 시작")
    yield
    print("CodeLens API 종료")


app = FastAPI(title="CodeLens API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extract.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

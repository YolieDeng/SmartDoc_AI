from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.qa import router as qa_router
from app.api.upload import router as upload_router
from app.core.auth import ApiKeyMiddleware
from app.core.langsmith import setup_langsmith
from app.db.redis_client import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_langsmith()
    yield
    await close_redis()


app = FastAPI(title="SmartDoc AI", version="0.3.0", lifespan=lifespan)

app.add_middleware(ApiKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(qa_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import FastAPI

from app.api.upload import router as upload_router

app = FastAPI(title="SmartDoc AI", version="0.1.0")

app.include_router(upload_router)

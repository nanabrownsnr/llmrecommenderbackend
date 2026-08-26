import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import deployments, models

app = FastAPI(
    title="Ollama Model Deployment API",
    version="0.1.0",
    description="Recommend models and generate cross-platform Ollama deployment packages.",
)

cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

app.include_router(models.router, prefix="/api")
app.include_router(deployments.router, prefix="/api")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.investigate import router as investigate_router

# Initialize loguru logging
setup_logging()

app = FastAPI(
    title="AI Kubernetes Agent Backend",
    description="Backend for the AI Kubernetes Troubleshooting Agent",
    version="0.1.0"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(investigate_router)


@app.get("/health")
async def health_check():
    logger.info("Health check endpoint triggered.")
    return {
        "status": "healthy",
        "service": "ai-kubernetes-agent"
    }

from app.core.database import init_db

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up AI Kubernetes Troubleshooting Agent backend...")
    logger.info(f"OpenRouter Model configured: {settings.openrouter_model}")
    logger.info(f"Kubeconfig Path: {settings.kubeconfig_path}")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database initialization failed on startup: {str(e)}")


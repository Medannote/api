from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import images, signaux, text
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Médicale Unifiée",
    description="API regroupant images, signaux et textes médicaux",
    version="1.0.0"
)

# Configure CORS - adjust origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images, prefix="/images", tags=["Images"])
app.include_router(signaux, prefix="/signaux", tags=["Signaux"])
app.include_router(text, prefix="/text", tags=["Text"])

@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "status": "online",
        "message": "API Médicale Unifiée",
        "version": "1.0.0",
        "endpoints": {
            "images": "/images",
            "signaux": "/signaux",
            "text": "/text"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "medical-api"}

logger.info("API Médicale Unifiée initialized successfully")
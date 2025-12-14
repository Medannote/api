import os
import logging
from fastapi import FastAPI, Request, status, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers import images, signaux, text, batch
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware, InputSanitizationMiddleware
from app.job_tracker import job_tracker, JobStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Médicale Unifiée",
    description="API regroupant images, signaux, textes médicaux et traitement par lots",
    version="2.0.0"
)

# Custom exception handler to avoid exposing internal details
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Une erreur interne s'est produite. Veuillez réessayer plus tard.",
            "error_type": "internal_error"
        }
    )

# Add custom middleware (order matters - first added = last executed)
# 1. Input sanitization (first line of defense)
app.add_middleware(InputSanitizationMiddleware)

# 2. Rate limiting
rate_limit_calls = int(os.getenv("RATE_LIMIT_CALLS", "100"))
rate_limit_period = int(os.getenv("RATE_LIMIT_PERIOD", "60"))
app.add_middleware(RateLimitMiddleware, calls=rate_limit_calls, period=rate_limit_period)

# 3. Request logging
app.add_middleware(RequestLoggingMiddleware)

# 4. CORS configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "API Médicale Unifiée",
        "version": "2.0.0"
    }

@app.get("/", tags=["System"])
async def root():
    """API root endpoint"""
    return {
        "message": "API Médicale Unifiée",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "jobs": "/jobs",
        "api_versions": {
            "v1": "/api/v1"
        }
    }

@app.get("/jobs/{job_id}", tags=["Jobs"])
async def get_job_status(job_id: str):
    """
    Get the status of a processing job.
    Returns real-time progress information.
    """
    job = job_tracker.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job non trouvé. Il a peut-être expiré ou n'existe pas."
        )
    
    return job

@app.get("/jobs", tags=["Jobs"])
async def list_jobs(status: JobStatus = None, limit: int = 50):
    """
    List recent jobs, optionally filtered by status.
    Useful for monitoring and debugging.
    """
    if limit > 100:
        limit = 100
    
    jobs = job_tracker.list_jobs(status=status, limit=limit)
    
    return {
        "total": len(jobs),
        "jobs": jobs
    }

@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def cancel_job(job_id: str):
    """
    Cancel or delete a job.
    Note: This only marks the job as cancelled, it doesn't stop running processes.
    """
    job = job_tracker.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job non trouvé."
        )
    
    if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
        job_tracker.update_status(job_id, JobStatus.CANCELLED, message="Annulé par l'utilisateur")
    
    return {
        "message": "Job annulé",
        "job_id": job_id
    }

# Create API v1 router for versioning
api_v1 = APIRouter(prefix="/api/v1")

# Include all routers under v1
api_v1.include_router(images, prefix="/images", tags=["Images"])
api_v1.include_router(signaux, prefix="/signaux", tags=["Signaux"])
api_v1.include_router(text, prefix="/text", tags=["Text"])
api_v1.include_router(batch, prefix="/batch", tags=["Batch Processing"])

# Mount the versioned API
app.include_router(api_v1)

# For backward compatibility, also mount routers at root level (can be removed later)
app.include_router(images, prefix="/images", tags=["Images (Legacy)"])
app.include_router(signaux, prefix="/signaux", tags=["Signaux (Legacy)"])
app.include_router(text, prefix="/text", tags=["Text (Legacy)"])
app.include_router(batch, prefix="/batch", tags=["Batch Processing (Legacy)"])
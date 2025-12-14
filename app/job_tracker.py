"""
Job tracking system for long-running operations
Provides real-time status updates for async processing tasks
"""
import uuid
import time
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any
from pydantic import BaseModel
import threading


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobProgress(BaseModel):
    """Job progress information"""
    job_id: str
    status: JobStatus
    progress_percent: int = 0  # 0-100
    message: str = ""
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class JobTracker:
    """
    Thread-safe job tracking system.
    For production, consider using Redis or a database for persistence.
    """
    
    def __init__(self, max_jobs: int = 1000):
        self.jobs: Dict[str, JobProgress] = {}
        self.lock = threading.Lock()
        self.max_jobs = max_jobs
    
    def create_job(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new job and return its ID"""
        job_id = str(uuid.uuid4())
        
        with self.lock:
            # Clean up old jobs if we're at max capacity
            if len(self.jobs) >= self.max_jobs:
                self._cleanup_old_jobs()
            
            self.jobs[job_id] = JobProgress(
                job_id=job_id,
                status=JobStatus.PENDING,
                created_at=datetime.utcnow().isoformat(),
                metadata=metadata or {}
            )
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[JobProgress]:
        """Get job status"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def update_status(
        self, 
        job_id: str, 
        status: JobStatus,
        progress: Optional[int] = None,
        message: Optional[str] = None
    ):
        """Update job status"""
        with self.lock:
            if job_id not in self.jobs:
                return
            
            job = self.jobs[job_id]
            job.status = status
            
            if progress is not None:
                job.progress_percent = min(100, max(0, progress))
            
            if message is not None:
                job.message = message
            
            # Update timestamps
            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.utcnow().isoformat()
            
            if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.utcnow().isoformat()
                job.progress_percent = 100 if status == JobStatus.COMPLETED else job.progress_percent
    
    def set_result(self, job_id: str, result: Dict[str, Any]):
        """Set job result"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].result = result
    
    def set_error(self, job_id: str, error: str):
        """Set job error"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].error = error
                self.jobs[job_id].status = JobStatus.FAILED
                self.jobs[job_id].completed_at = datetime.utcnow().isoformat()
    
    def delete_job(self, job_id: str):
        """Delete a job"""
        with self.lock:
            if job_id in self.jobs:
                del self.jobs[job_id]
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> list[JobProgress]:
        """List jobs, optionally filtered by status"""
        with self.lock:
            jobs = list(self.jobs.values())
            
            if status:
                jobs = [j for j in jobs if j.status == status]
            
            # Sort by created_at descending
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            
            return jobs[:limit]
    
    def _cleanup_old_jobs(self):
        """Remove oldest completed/failed jobs to free space"""
        completed_jobs = [
            (job_id, job) for job_id, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
        ]
        
        # Sort by completion time
        completed_jobs.sort(key=lambda x: x[1].completed_at or "")
        
        # Remove oldest 10%
        remove_count = max(1, len(completed_jobs) // 10)
        for job_id, _ in completed_jobs[:remove_count]:
            del self.jobs[job_id]


# Global job tracker instance
job_tracker = JobTracker()

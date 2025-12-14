"""
Custom middleware for API rate limiting, request logging, and other cross-cutting concerns
"""
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import uuid

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.
    For production, consider using Redis for distributed rate limiting.
    """
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        """
        Args:
            app: FastAPI application
            calls: Number of calls allowed per period
            period: Time period in seconds
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients: Dict[str, list] = defaultdict(list)
        
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request"""
        # Try to get real IP from headers (for proxy/load balancer scenarios)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
            
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        return "unknown"
    
    def _is_rate_limited(self, client_id: str) -> Tuple[bool, int]:
        """
        Check if client is rate limited.
        
        Returns:
            (is_limited, remaining_calls)
        """
        now = time.time()
        cutoff = now - self.period
        
        # Clean old entries
        self.clients[client_id] = [
            timestamp for timestamp in self.clients[client_id]
            if timestamp > cutoff
        ]
        
        # Check rate limit
        if len(self.clients[client_id]) >= self.calls:
            return True, 0
        
        # Add current request
        self.clients[client_id].append(now)
        remaining = self.calls - len(self.clients[client_id])
        
        return False, remaining
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        # Skip rate limiting for health check and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json", "/"]:
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        is_limited, remaining = self._is_rate_limited(client_id)
        
        if is_limited:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Trop de requêtes. Veuillez réessayer plus tard.",
                    "error_type": "rate_limit_exceeded"
                },
                headers={
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + self.period))
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.period))
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all incoming requests and responses
    """
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response details"""
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        
        # Get client info
        client_id = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For", "")
        
        # Start timer
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request started | "
            f"ID: {request_id} | "
            f"Method: {request.method} | "
            f"Path: {request.url.path} | "
            f"Client: {client_id} | "
            f"Forwarded: {forwarded}"
        )
        
        # Add request ID to state for use in endpoints if needed
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed | "
                f"ID: {request_id} | "
                f"Status: {response.status_code} | "
                f"Duration: {duration:.3f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed | "
                f"ID: {request_id} | "
                f"Error: {str(e)} | "
                f"Duration: {duration:.3f}s",
                exc_info=True
            )
            raise


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to sanitize potentially dangerous input patterns
    """
    
    SUSPICIOUS_PATTERNS = [
        "../",  # Path traversal
        "..\\",  # Windows path traversal
        "<script",  # XSS attempts
        "javascript:",  # XSS attempts
        "onerror=",  # XSS attempts
        "onload=",  # XSS attempts
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Check request for suspicious patterns"""
        # Check query parameters
        query_string = str(request.url.query).lower()
        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern.lower() in query_string:
                logger.warning(
                    f"Suspicious pattern detected in query: {pattern} | "
                    f"Path: {request.url.path} | "
                    f"Client: {request.client.host if request.client else 'unknown'}"
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": "Requête invalide détectée.",
                        "error_type": "invalid_input"
                    }
                )
        
        return await call_next(request)

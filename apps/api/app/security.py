import hashlib
import hmac
import time
from uuid import uuid4

from fastapi import HTTPException, Request
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import get_settings


PUBLIC_PATHS = {"/api/v1/health"}


class SecurityMiddleware(BaseHTTPMiddleware):
    """Authentication, fixed-window limits, tracing, and browser hardening."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
        client_ip = request.client.host if request.client else "unknown"

        local_intake_path = (
            request.url.path.startswith("/api/v1/uploads")
            or request.url.path == "/api/v1/preflight"
            or (request.method == "POST" and request.url.path == "/api/v1/runs")
        )
        if settings.environment == "production" and not settings.allow_local_uploads and local_intake_path:
            return JSONResponse({"detail": "Local uploads are disabled for this deployment", "request_id": request_id}, status_code=404)

        if settings.require_api_key and request.url.path not in PUBLIC_PATHS:
            supplied = request.headers.get("X-API-Key", "")
            if not any(hmac.compare_digest(supplied, key) for key in settings.accepted_api_keys):
                return JSONResponse({"detail": "Authentication required", "request_id": request_id}, status_code=401)

        limit = settings.upload_rate_limit_per_minute if "/uploads" in request.url.path else settings.rate_limit_per_minute
        identity = hashlib.sha256(f"{client_ip}:{request.headers.get('X-API-Key', '')}".encode()).hexdigest()
        bucket = int(time.time() // 60)
        try:
            redis = Redis.from_url(settings.redis_url, decode_responses=True)
            key = f"express:rate:{bucket}:{identity}:{'upload' if '/uploads' in request.url.path else 'api'}"
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, 120)
            if count > limit:
                return JSONResponse({"detail": "Rate limit exceeded", "request_id": request_id}, status_code=429, headers={"Retry-After": "60"})
        except Exception:
            if settings.environment == "production":
                return JSONResponse({"detail": "Request guard unavailable", "request_id": request_id}, status_code=503)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response

import hashlib
import hmac
import time
from uuid import uuid4
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .auth import SESSION_COOKIE, authenticate_session
from .config import get_settings


PUBLIC_PATHS = {"/api/v1/health", "/api/v1/auth/login"}


def is_local_intake(method: str, path: str) -> bool:
    return (
        path.startswith("/api/v1/uploads")
        or path == "/api/v1/preflight"
        or (method.upper() == "POST" and path == "/api/v1/runs")
    )


class SecurityMiddleware(BaseHTTPMiddleware):
    """Authentication, fixed-window limits, tracing, and browser hardening."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
        client_ip = request.client.host if request.client else "unknown"

        if settings.environment == "production" and not settings.allow_local_uploads and is_local_intake(request.method, request.url.path):
            return JSONResponse({"detail": "Local uploads are disabled for this deployment", "request_id": request_id}, status_code=404)

        if settings.environment == "production" and request.url.path.startswith("/api/") and request.url.path not in PUBLIC_PATHS:
            user = authenticate_session(request.cookies.get(SESSION_COOKIE))
            if not user:
                return JSONResponse({"detail": "Authentication required", "request_id": request_id}, status_code=401)
            request.state.user = user
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                origin = request.headers.get("origin")
                host = request.headers.get("host", "")
                if origin and urlparse(origin).netloc != host:
                    return JSONResponse({"detail": "Request origin rejected", "request_id": request_id}, status_code=403)

        if settings.require_api_key and request.url.path not in PUBLIC_PATHS:
            supplied = request.headers.get("X-API-Key", "")
            if not any(hmac.compare_digest(supplied, key) for key in settings.accepted_api_keys):
                return JSONResponse({"detail": "Authentication required", "request_id": request_id}, status_code=401)

        if request.url.path == "/api/v1/auth/login":
            limit = 10
        else:
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

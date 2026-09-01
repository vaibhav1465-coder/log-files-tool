from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .config import get_settings
from .db import connection

router = APIRouter(prefix="/api/v1", tags=["authentication"])
SESSION_COOKIE = "express_session"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(default="analyst", pattern="^(analyst|admin)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(analyst|admin)$")
    active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=12, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


def _normalise_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return email


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + salt.hex() + "$" + derived.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _public_user(row: dict) -> dict:
    return {"id": str(row["id"]), "email": row["email"], "display_name": row["display_name"], "role": row["role"], "active": row["active"], "created_at": row.get("created_at"), "last_login_at": row.get("last_login_at"), "must_change_password": row.get("must_change_password", False)}


def authenticate_session(token: str | None) -> dict | None:
    if not token:
        return None
    with connection() as conn:
        row = conn.execute(
            """SELECT u.id,u.email,u.display_name,u.role,u.active,u.created_at,u.last_login_at,u.must_change_password,
                      s.id session_id,s.expires_at,s.last_seen_at
               FROM user_sessions s JOIN app_users u ON u.id=s.user_id
               WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>NOW() AND u.active""",
            (_token_hash(token),),
        ).fetchone()
        if row:
            conn.execute("UPDATE user_sessions SET last_seen_at=NOW() WHERE id=%s AND last_seen_at<NOW()-INTERVAL '5 minutes'", (row["session_id"],))
    return row


def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request) -> dict:
    user = current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def _audit(conn, actor: str, action: str, target_type: str, target_id: str | None, result: str, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO audit_events (id,actor,action,target_type,target_id,result,detail) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)", (uuid4(), actor, action, target_type, target_id, result, json.dumps(detail or {})))


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    email = _normalise_email(payload.email)
    with connection() as conn:
        user = conn.execute("SELECT * FROM app_users WHERE email=%s", (email,)).fetchone()
        if not user or not user["active"] or not verify_password(payload.password, user["password_hash"]):
            _audit(conn, email, "auth.login", "user", None, "denied")
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        token = secrets.token_urlsafe(48)
        session_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=get_settings().session_hours)
        client_ip = request.client.host if request.client else "unknown"
        conn.execute("INSERT INTO user_sessions (id,user_id,token_hash,expires_at,user_agent_hash,client_ip_hash) VALUES (%s,%s,%s,%s,%s,%s)", (session_id, user["id"], _token_hash(token), expires_at, _fingerprint(request.headers.get("user-agent", "")), _fingerprint(client_ip)))
        conn.execute("UPDATE app_users SET last_login_at=NOW(),updated_at=NOW() WHERE id=%s", (user["id"],))
        _audit(conn, email, "auth.login", "session", str(session_id), "success")
    response.set_cookie(SESSION_COOKIE, token, max_age=get_settings().session_hours * 3600, httponly=True, secure=get_settings().session_cookie_secure, samesite="strict", path="/")
    return {"user": _public_user(user), "expires_at": expires_at}


@router.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    user = current_user(request)
    token = request.cookies.get(SESSION_COOKIE)
    with connection() as conn:
        conn.execute("UPDATE user_sessions SET revoked_at=NOW() WHERE token_hash=%s", (_token_hash(token or ""),))
        _audit(conn, user["email"], "auth.logout", "session", str(user["session_id"]), "success")
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/auth/me")
def me(request: Request) -> dict:
    return {"user": _public_user(current_user(request))}


@router.post("/auth/change-password")
def change_password(payload: PasswordChange, request: Request) -> dict:
    user = current_user(request)
    with connection() as conn:
        stored = conn.execute("SELECT password_hash FROM app_users WHERE id=%s", (user["id"],)).fetchone()
        if not stored or not verify_password(payload.current_password, stored["password_hash"]):
            raise HTTPException(status_code=422, detail="Current password is incorrect.")
        conn.execute("UPDATE app_users SET password_hash=%s,must_change_password=FALSE,updated_at=NOW() WHERE id=%s", (hash_password(payload.new_password), user["id"]))
        conn.execute("UPDATE user_sessions SET revoked_at=NOW() WHERE user_id=%s AND id<>%s", (user["id"], user["session_id"]))
        _audit(conn, user["email"], "auth.password_change", "user", str(user["id"]), "success")
    return {"status": "password_changed"}


@router.get("/admin/users")
def list_users(request: Request) -> list[dict]:
    require_admin(request)
    with connection() as conn:
        rows = conn.execute("""SELECT u.id,u.email,u.display_name,u.role,u.active,u.created_at,u.last_login_at,u.must_change_password,
                                      COUNT(s.id) FILTER (WHERE s.revoked_at IS NULL AND s.expires_at>NOW()) active_sessions
                               FROM app_users u LEFT JOIN user_sessions s ON s.user_id=u.id
                               GROUP BY u.id ORDER BY u.active DESC,u.role DESC,u.display_name""").fetchall()
    return [{**_public_user(row), "active_sessions": row["active_sessions"]} for row in rows]


@router.post("/admin/users", status_code=201)
def create_user(payload: UserCreate, request: Request) -> dict:
    admin = require_admin(request)
    email = _normalise_email(payload.email)
    user_id = uuid4()
    try:
        with connection() as conn:
            row = conn.execute("INSERT INTO app_users (id,email,display_name,password_hash,role) VALUES (%s,%s,%s,%s,%s) RETURNING *", (user_id, email, payload.display_name.strip(), hash_password(payload.password), payload.role)).fetchone()
            _audit(conn, admin["email"], "admin.user_create", "user", str(user_id), "success", {"role": payload.role})
        return _public_user(row)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="A user with this email already exists.") from exc


@router.patch("/admin/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, request: Request) -> dict:
    admin = require_admin(request)
    if str(admin["id"]) == user_id and payload.active is False:
        raise HTTPException(status_code=409, detail="You cannot remove your own access.")
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (0x41555448,))
        target = conn.execute("SELECT * FROM app_users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        if target["role"] == "admin" and (payload.role == "analyst" or payload.active is False):
            count = conn.execute("SELECT COUNT(*) count FROM app_users WHERE role='admin' AND active").fetchone()["count"]
            if count <= 1:
                raise HTTPException(status_code=409, detail="At least one active administrator is required.")
        role = payload.role or target["role"]
        active = target["active"] if payload.active is None else payload.active
        row = conn.execute("UPDATE app_users SET role=%s,active=%s,updated_at=NOW() WHERE id=%s RETURNING *", (role, active, user_id)).fetchone()
        if not active:
            conn.execute("UPDATE user_sessions SET revoked_at=NOW() WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
        _audit(conn, admin["email"], "admin.user_update", "user", user_id, "success", {"role": role, "active": active})
    return _public_user(row)


@router.get("/admin/overview")
def admin_overview(request: Request) -> dict:
    require_admin(request)
    settings = get_settings()
    with connection() as conn:
        user_counts = conn.execute("SELECT COUNT(*) count,COUNT(*) FILTER (WHERE active) active,COUNT(*) FILTER (WHERE role='admin' AND active) admins FROM app_users").fetchone()
        sessions = conn.execute("""SELECT s.id,u.email,u.display_name,u.role,s.created_at,s.last_seen_at,s.expires_at
                                   FROM user_sessions s JOIN app_users u ON u.id=s.user_id
                                   WHERE s.revoked_at IS NULL AND s.expires_at>NOW()
                                   ORDER BY s.last_seen_at DESC LIMIT 100""").fetchall()
        journeys = conn.execute("SELECT actor,action,target_type,result,created_at FROM audit_events ORDER BY created_at DESC LIMIT 100").fetchall()
        run_counts = conn.execute("SELECT status,COUNT(*) count FROM analysis_runs GROUP BY status ORDER BY status").fetchall()
        source_totals = conn.execute("SELECT COALESCE(SUM(size_bytes),0) bytes,COUNT(*) files FROM source_files WHERE upload_complete").fetchone()
    return {
        "generated_at": datetime.now(timezone.utc),
        "users": user_counts,
        "sessions": sessions,
        "journeys": journeys,
        "runs": run_counts,
        "data": {"referenced_source_bytes": source_totals["bytes"], "referenced_source_files": source_totals["files"], "run_byte_limit": settings.remote_max_total_bytes, "object_limit": settings.remote_max_objects, "scanned_key_limit": settings.remote_max_scanned_keys, "disk_reserve_bytes": settings.storage_reserve_bytes, "strategy": ["Stream gzip objects", "Aggregate URLs in batches", "Retain references instead of source copies", "One active analysis"]},
        "stack": [
            {"name": "Private gateway", "service": "Caddy", "state": "online", "connects_to": ["Web UI", "API"]},
            {"name": "Web UI", "service": "Next.js", "state": "online", "connects_to": ["API"]},
            {"name": "API", "service": "FastAPI", "state": "online", "connects_to": ["PostgreSQL", "Redis", "AWS S3"]},
            {"name": "Worker", "service": "Python worker", "state": "online", "connects_to": ["Redis", "PostgreSQL", "AWS S3"]},
            {"name": "Database", "service": "PostgreSQL", "state": "online", "connects_to": ["Backup"]},
            {"name": "Queue", "service": "Redis", "state": "online", "connects_to": ["Worker"]},
        ],
        "costs": {"currency": "USD", "period": "monthly estimate supplied by DevOps", "items": [{"name": "EC2 r8g.large", "amount": 60.28}, {"name": "100 GB gp3 EBS", "amount": 9.12}, {"name": "1 TB data transfer out estimate", "amount": 83.16}], "total": 152.56, "note": "Actual billing can differ. S3 source reads and transfer depend on usage and account routing."},
        "apis": [
            {"method": "POST", "path": "/api/v1/auth/login", "purpose": "Create a named session"},
            {"method": "POST", "path": "/api/v1/remote-runs/estimate", "purpose": "Estimate an approved selection"},
            {"method": "POST", "path": "/api/v1/remote-runs", "purpose": "Queue an analysis"},
            {"method": "GET", "path": "/api/v1/runs", "purpose": "List analysis history"},
            {"method": "GET", "path": "/api/v1/runs/{id}/metrics", "purpose": "Read evidence metrics"},
            {"method": "GET", "path": "/api/v1/admin/overview", "purpose": "Read operational telemetry"},
        ],
    }

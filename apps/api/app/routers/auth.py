from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app import db
from app.ratelimit import limit
from app.security import create_token, current_user, hash_password, verify_password
from app.services.pilot import record_consent

router = APIRouter(prefix="/v2/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=80)
    language: str = Field(default="en", pattern="^(en|kn|hi)$")
    cohort: str | None = Field(default=None, max_length=40)       # pilot group code, e.g. an RWA
    accept_terms: bool
    research_consent: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class MeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, pattern="^(en|kn|hi)$")


def _out(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u.get("name"), "role": u["role"],
            "language": u.get("language", "en"), "cohort": u.get("cohort")}


@router.post("/register", dependencies=[Depends(limit("register", 5, 3600))])
def register(body: RegisterIn):
    if not body.accept_terms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please accept the terms to create an account")
    if db.fetchone("SELECT id FROM users WHERE email = ?", (body.email.lower(),)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = {"id": db.new_id(), "email": body.email.lower(), "name": body.name, "password_hash": hash_password(body.password),
            "role": "citizen", "language": body.language, "cohort": (body.cohort or "").strip().upper() or None,
            "created_at": db.now()}
    db.insert("users", user)
    record_consent(user["id"], "terms", True)
    record_consent(user["id"], "pilot_research", body.research_consent)
    return {"token": create_token(user), "user": _out(user)}


@router.post("/login", dependencies=[Depends(limit("login", 10, 300))])
def login(body: LoginIn):
    u = db.fetchone("SELECT * FROM users WHERE email = ?", (body.email.lower(),))
    if not u or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return {"token": create_token(u), "user": _out(u)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _out(user)


@router.patch("/me")
def update_me(body: MeUpdate, user: dict = Depends(current_user)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if changes:
        db.update("users", user["id"], changes)
    return _out({**user, **changes})

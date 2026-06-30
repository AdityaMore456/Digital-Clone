from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.database import get_conn
from app.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(payload: RegisterIn):
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (payload.email,)).fetchone()
        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")
        cur = conn.execute(
            "INSERT INTO users (email, hashed_password, full_name) VALUES (?, ?, ?)",
            (payload.email, hash_password(payload.password), payload.full_name),
        )
        user_id = cur.lastrowid
    token = create_access_token(user_id)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(payload: LoginIn):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (payload.email,)).fetchone()
    if not row or not verify_password(payload.password, row["hashed_password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials.")
    token = create_access_token(row["id"])
    return {"access_token": token, "token_type": "bearer"}

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(payload: RegisterRequest):
    return {
        "message": "register endpoint scaffolded",
        "username": payload.username,
        "role": "student",
    }


@router.post("/login")
def login(payload: LoginRequest):
    return {
        "access_token": "mock-token",
        "token_type": "bearer",
        "username": payload.username,
    }


@router.post("/logout")
def logout():
    return {"message": "logout endpoint scaffolded"}


@router.get("/me")
def current_user():
    return {"username": "demo", "role": "student"}


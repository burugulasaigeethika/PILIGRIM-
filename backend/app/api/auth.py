import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, EmailStr, Field

from app.db.mongodb import get_users_collection
from app.auth.security import hash_password, verify_password
from app.auth.jwt import (
    create_access_token,
    create_email_token,
    verify_email_token,
    get_current_user
)
from app.tasks.celery_app import send_verification_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, description="User full name")
    email: EmailStr = Field(..., description="User valid email address")
    password: str = Field(..., min_length=4, description="User secure password")

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_verified: bool

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(request: RegisterRequest):
    """
    Registers a new user in MongoDB, hashes password, and triggers
    asynchronous verification email task via RabbitMQ/Celery.
    """
    users_col = get_users_collection()
    normalized_email = request.email.strip().lower()
    
    # Check for existing email
    existing = users_col.find_one({"email": normalized_email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered."
        )
    
    # Hash password
    hashed = hash_password(request.password)
    now = datetime.now(timezone.utc)
    
    user_doc = {
        "name": request.name.strip(),
        "email": normalized_email,
        "password_hash": hashed,
        "role": "user",
        "is_verified": False,
        "created_at": now,
        "updated_at": now
    }
    
    try:
        result = users_col.insert_one(user_doc)
        user_id = str(result.inserted_id)
    except Exception as e:
        logger.error(f"[AUTH] Error inserting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user."
        )
    
    # Generate email verification token
    verification_token = create_email_token(normalized_email)
    
    # Dispatch Celery background task through RabbitMQ
    try:
        send_verification_email.delay(
            email=normalized_email,
            token=verification_token,
            user_name=request.name.strip()
        )
        logger.info(f"[AUTH] Queued verification email task for {normalized_email}")
    except Exception as e:
        logger.warning(f"[AUTH] Could not queue Celery task (broker might be unavailable): {e}")

    return {
        "message": "User registered successfully.",
        "user": {
            "id": user_id,
            "name": request.name.strip(),
            "email": normalized_email,
            "role": "user",
            "is_verified": False
        }
    }

@router.post("/login", response_model=AuthResponse)
async def login_user(request: LoginRequest):
    """
    Authenticates user credentials against MongoDB, returning a signed JWT access token.
    """
    users_col = get_users_collection()
    normalized_email = request.email.strip().lower()
    
    user = users_col.find_one({"email": normalized_email})
    if not user or not verify_password(request.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = str(user["_id"])
    role = user.get("role", "user")
    
    # Generate JWT
    token_payload = {
        "sub": user_id,
        "email": user["email"],
        "role": role
    }
    access_token = create_access_token(data=token_payload)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            name=user.get("name", ""),
            email=user.get("email", ""),
            role=role,
            is_verified=user.get("is_verified", False)
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns the authenticated user's profile from JWT token.
    """
    return UserResponse(
        id=str(current_user["_id"]),
        name=current_user.get("name", ""),
        email=current_user.get("email", ""),
        role=current_user.get("role", "user"),
        is_verified=current_user.get("is_verified", False)
    )

@router.get("/verify-email")
async def verify_email_endpoint(token: str = Query(..., description="Verification token")):
    """
    Validates verification token and sets user is_verified=True in MongoDB.
    """
    email = verify_email_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token."
        )
    
    users_col = get_users_collection()
    user = users_col.find_one({"email": email.strip().lower()})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {
        "status": "success",
        "message": "Email verified successfully.",
        "email": email
    }

"""
User model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import json
import uuid
from models.database import db

class UserRole(str, Enum):
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    created_at: datetime
    post_count: int = 0
    comment_count: int = 0
    reputation: int = 0
    is_active: bool = True

class User:
    """Class for working with users in Redis"""

    @staticmethod
    async def create(user_data: UserCreate, role: UserRole = UserRole.USER) -> str:
        """Create a new user"""
        user_id = str(uuid.uuid4())

        # Check for username and email uniqueness
        if await User.get_by_username(user_data.username):
            raise ValueError("A user with this name already exists")

        if await User.get_by_email(user_data.email):
            raise ValueError("A user with this email already exists")

        user_info = {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "password_hash": user_data.password,  # In a real application, hash this!
            "role": role.value,
            "created_at": datetime.now().isoformat(),
            "post_count": 0,
            "comment_count": 0,
            "reputation": 0,
            "is_active": True
        }

        # Save the user
        await db.hset(f"user:{user_id}", user_info)

        # Create indexes for searching
        await db.set(f"username:{user_data.username}", user_id)
        await db.set(f"email:{user_data.email}", user_id)

        return user_id

    @staticmethod
    async def get_by_id(user_id: str) -> Optional[UserResponse]:
        """Get a user by ID"""
        user_data = await db.hgetall(f"user:{user_id}")
        if not user_data:
            return None

        return UserResponse(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            role=UserRole(user_data["role"]),
            created_at=datetime.fromisoformat(user_data["created_at"]),
            post_count=int(user_data.get("post_count", 0)),
            comment_count=int(user_data.get("comment_count", 0)),
            reputation=int(user_data.get("reputation", 0)),
            is_active=user_data.get("is_active", "True") == "True"
        )

    @staticmethod 
    async def get_by_username(username: str) -> Optional[UserResponse]:
        """Get a user by name"""
        user_id = await db.get(f"username:{username}")
        if not user_id:
            return None
        return await User.get_by_id(user_id)

    @staticmethod
    async def get_by_email(email: str) -> Optional[UserResponse]:
        """Get a user by email"""
        user_id = await db.get(f"email:{email}")
        if not user_id:
            return None
        return await User.get_by_id(user_id)

    @staticmethod
    async def update_stats(user_id: str, post_count_delta: int = 0, 
                          comment_count_delta: int = 0, reputation_delta: int = 0):
        """Update user statistics"""
        user_data = await db.hgetall(f"user:{user_id}")
        if not user_data:
            return

        new_post_count = int(user_data.get("post_count", 0)) + post_count_delta
        new_comment_count = int(user_data.get("comment_count", 0)) + comment_count_delta
        new_reputation = int(user_data.get("reputation", 0)) + reputation_delta

        await db.hset(f"user:{user_id}", {
            "post_count": new_post_count,
            "comment_count": new_comment_count,
            "reputation": new_reputation
        })

    @staticmethod
    async def get_user_age_days(user_id: str) -> int:
        """Get the account age in days"""
        user_data = await db.hgetall(f"user:{user_id}")
        if not user_data:
            return 0

        created_at = datetime.fromisoformat(user_data["created_at"])
        age = (datetime.now() - created_at).days
        return age

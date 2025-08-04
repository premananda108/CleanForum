"""
API routes for working with users
"""
from fastapi import APIRouter, Depends, HTTPException
from models.user import UserResponse, UserRole
from api.posts import get_current_user_id
import uuid
from datetime import datetime

router = APIRouter()

# This is a mock user database. In a real application, this would be in a database.
mock_users_db = {
    "user_demo_12345": {
        "id": "user_demo_12345",
        "username": "DemoUser",
        "email": "demo@example.com",
        "role": UserRole.USER,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
}

@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user_id: str = Depends(get_current_user_id)):
    """
    Get information about the current user.
    """
    user_data = mock_users_db.get(current_user_id)
    if user_data is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user_data)

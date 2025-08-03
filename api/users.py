"""
API роуты для работы с пользователями
"""
from fastapi import APIRouter, Depends, HTTPException
from models.user import UserResponse, UserRole
from api.posts import get_current_user_id
import uuid
from datetime import datetime

router = APIRouter()

# Это моковая база данных пользователей. В реальном приложении это будет в базе данных.
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
    Получить информацию о текущем пользователе.
    """
    user_data = mock_users_db.get(current_user_id)
    if user_data is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserResponse(**user_data)

import pytest
import pytest_asyncio
import asyncio
from models.user import User, UserCreate
from models.database import db
from config import settings

# Fixture to manage the asyncio event loop
@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Fixture to manage the database
@pytest_asyncio.fixture(scope="function", autouse=True)
async def database(monkeypatch):
    # Force test settings
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    # Connect to the DB before each test
    await db.connect()
    # Clear the DB before each test
    await db.flush_db()
    yield
    # Disconnect from the DB after each test
    await db.disconnect()

@pytest.mark.asyncio
async def test_create_user():
    """Test creating a new user"""
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="password123"
    )
    
    # Create the user
    user_id = await User.create(user_data)
    
    # Check that the user was created
    assert user_id is not None
    
    # Get the user by ID
    created_user = await User.get_by_id(user_id)
    
    # Check the user's data
    assert created_user is not None
    assert created_user.username == user_data.username
    assert created_user.email == user_data.email
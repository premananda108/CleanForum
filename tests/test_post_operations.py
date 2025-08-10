import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from models.database import db
from models.user import User, UserCreate
from models.category import Category, CategoryCreate
from models.post import Post, PostCreate, PostUpdate, PostStatus
from config import settings


@pytest_asyncio.fixture(scope="function")
async def setup_post_operations_data(monkeypatch):
    """Setup data for post operations tests"""
    # Force test settings
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    await db.connect()
    await db.flush_db()

    # Create test user
    user_data = UserCreate(
        username="postops_user",
        email="postops@example.com", 
        password="password123"
    )
    user_id = await User.create(user_data)

    # Create test category
    category_data = CategoryCreate(
        name="Post Ops Category",
        description="Category for post operations testing"
    )
    category_id = await Category.create(category_data)

    # Mock spam analysis for all tests to avoid spam detection issues
    mock_analyze = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze
    )

    yield user_id, category_id

    await db.disconnect()

@pytest.mark.asyncio
async def test_post_hard_delete(setup_post_operations_data):
    """Test hard delete functionality"""
    user_id, category_id = setup_post_operations_data

    # Create a post
    post_data = PostCreate(
        title="Post for Hard Delete",
        content="This post will be permanently deleted",
        category_id=category_id,
        tags=["harddelete"]
    )
    post_id = await Post.create(post_data, user_id)

    # Verify post exists
    post = await Post.get_by_id(post_id)
    assert post is not None

    # Hard delete the post
    success = await Post.hard_delete(post_id)
    assert success is True

    # Verify post no longer exists
    deleted_post = await Post.get_by_id(post_id)
    assert deleted_post is None

    # Verify category post count decreased
    category = await Category.get_by_id(category_id)
    assert category.post_count == 0


@pytest.mark.asyncio
async def test_post_view_count_increment(setup_post_operations_data):
    """Test view count increment functionality"""
    user_id, category_id = setup_post_operations_data

    post_data = PostCreate(
        title="View Count Test",
        content="Test post for view counting",
        category_id=category_id,
        tags=[]
    )
    post_id = await Post.create(post_data, user_id)

    # Initial view count should be 0
    post = await Post.get_by_id(post_id, increment_views=False)
    assert post.view_count == 0

    # Increment views
    post = await Post.get_by_id(post_id, increment_views=True)
    assert post.view_count == 1

    # Increment again
    post = await Post.get_by_id(post_id, increment_views=True)
    assert post.view_count == 2

    # Getting without increment should not increase
    post = await Post.get_by_id(post_id, increment_views=False)
    assert post.view_count == 2


@pytest.mark.asyncio
async def test_post_comment_count_update(setup_post_operations_data):
    """Test comment count update functionality"""
    user_id, category_id = setup_post_operations_data

    post_data = PostCreate(
        title="Comment Count Test",
        content="Test post for comment counting",
        category_id=category_id,
        tags=[]
    )
    post_id = await Post.create(post_data, user_id)

    # Initial comment count should be 0
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 0

    # Simulate adding comments
    await Post.update_comment_count(post_id, 1)
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 1

    # Add more comments
    await Post.update_comment_count(post_id, 3)
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 4

    # Remove comments
    await Post.update_comment_count(post_id, -2)
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 2

    # Should not go below 0
    await Post.update_comment_count(post_id, -5)
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 0


@pytest.mark.asyncio
async def test_post_reading_time_calculation(setup_post_operations_data):
    """Test reading time calculation"""
    user_id, category_id = setup_post_operations_data

    # Short post (less than 200 words)
    short_content = "This is a short post with only a few words."
    short_post_data = PostCreate(
        title="Short Post",
        content=short_content,
        category_id=category_id,
        tags=[]
    )
    short_post_id = await Post.create(short_post_data, user_id)
    short_post = await Post.get_by_id(short_post_id)
    assert short_post.reading_time == 1  # Minimum 1 minute

    # Longer post (approximately 400 words)
    long_content = " ".join(["word"] * 400)
    long_post_data = PostCreate(
        title="Long Post",
        content=long_content,
        category_id=category_id,
        tags=[]
    )
    long_post_id = await Post.create(long_post_data, user_id)
    long_post = await Post.get_by_id(long_post_id)
    assert long_post.reading_time == 2  # 400 words / 200 words per minute = 2 minutes


@pytest.mark.asyncio
async def test_post_pagination(setup_post_operations_data):
    """Test pagination in get_all and get_by_category"""
    user_id, category_id = setup_post_operations_data

    # Create multiple posts
    for i in range(5):
        post_data = PostCreate(
            title=f"Post {i+1}",
            content=f"Content for post {i+1}",
            category_id=category_id,
            tags=[]
        )
        await Post.create(post_data, user_id)

    # Test get_all pagination
    posts, total = await Post.get_all(limit=2, offset=0)
    assert len(posts) == 2
    assert total == 5

    posts, total = await Post.get_all(limit=2, offset=2)
    assert len(posts) == 2
    assert total == 5

    posts, total = await Post.get_all(limit=2, offset=4)
    assert len(posts) == 1  # Last page with only 1 post
    assert total == 5

    # Test get_by_category pagination
    posts, total = await Post.get_by_category(category_id, limit=3, offset=0)
    assert len(posts) == 3
    assert total == 5

    posts, total = await Post.get_by_category(category_id, limit=3, offset=3)
    assert len(posts) == 2
    assert total == 5


@pytest.mark.asyncio
async def test_post_update_validation(setup_post_operations_data):
    """Test post update with various data"""
    user_id, category_id = setup_post_operations_data

    # Create original post
    original_data = PostCreate(
        title="Original Title",
        content="Original content",
        category_id=category_id,
        tags=["original"]
    )
    post_id = await Post.create(original_data, user_id)
    original_post = await Post.get_by_id(post_id)

    # Test partial update (only title)
    update_data = PostUpdate(title="Updated Title")
    success = await Post.update(post_id, update_data)
    assert success is True

    updated_post = await Post.get_by_id(post_id)
    assert updated_post.title == "Updated Title"
    assert updated_post.content == "Original content"  # Unchanged
    assert updated_post.updated_at > original_post.updated_at

    # Test partial update (only content)
    update_data = PostUpdate(content="Updated content")
    success = await Post.update(post_id, update_data)
    assert success is True

    updated_post = await Post.get_by_id(post_id)
    assert updated_post.title == "Updated Title"  # From previous update
    assert updated_post.content == "Updated content"

    # Test updating tags
    update_data = PostUpdate(tags=["updated", "tags"])
    success = await Post.update(post_id, update_data)
    assert success is True

    updated_post = await Post.get_by_id(post_id)
    assert set(updated_post.tags) == {"updated", "tags"}

    # Test updating category
    new_category_data = CategoryCreate(
        name="New Category",
        description="A new category for testing"
    )
    new_category_id = await Category.create(new_category_data)

    update_data = PostUpdate(category_id=new_category_id)
    success = await Post.update(post_id, update_data)
    assert success is True

    updated_post = await Post.get_by_id(post_id)
    assert updated_post.category_id == new_category_id


@pytest.mark.asyncio
async def test_post_update_nonexistent(setup_post_operations_data):
    """Test updating a non-existent post"""
    user_id, category_id = setup_post_operations_data

    update_data = PostUpdate(title="This should fail")
    success = await Post.update("nonexistent-id", update_data)
    assert success is False


@pytest.mark.asyncio
async def test_post_delete_nonexistent(setup_post_operations_data):
    """Test deleting a non-existent post"""
    user_id, category_id = setup_post_operations_data

    success = await Post.mark_as_deleted("nonexistent-id")
    assert success is False

    success = await Post.hard_delete("nonexistent-id")
    assert success is False

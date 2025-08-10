import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from models.user import User, UserCreate
from models.post import Post, PostCreate
from models.category import Category, CategoryCreate
from models.comment import Comment, CommentCreate, CommentStatus
from models.database import db
from config import settings


@pytest_asyncio.fixture(scope="function")
async def setup_data(monkeypatch):
    # Force test settings
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    await db.connect()
    await db.flush_db()

    # Create test user
    user_data = UserCreate(
        username="testuser_comments",
        email="test_comments@example.com",
        password="password123"
    )
    user_id = await User.create(user_data)

    # Create test category
    category_data = CategoryCreate(
        name="Test Category",
        description="A category for testing"
    )
    category_id = await Category.create(category_data)

    # Create test post
    post_data = PostCreate(
        title="Test Post",
        content="This is a test post content",
        category_id=category_id,
        tags=[]
    )
    # Mock spam detection for post creation
    mock_analyze = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze
    )
    
    post_id = await Post.create(post_data, user_id)

    yield user_id, post_id, category_id

    await db.disconnect()


@pytest.mark.asyncio
async def test_create_comment_success(setup_data, monkeypatch):
    """Test successful comment creation"""
    user_id, post_id, _ = setup_data

    # Mock spam analysis to return not spam
    mock_analyze_comment = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.2
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_comment
    )

    comment_data = CommentCreate(
        content="This is a test comment",
        post_id=post_id
    )

    comment_id = await Comment.create(comment_data, user_id)
    assert comment_id is not None

    # Verify comment was created
    comment = await Comment.get_by_id(comment_id)
    assert comment is not None
    assert comment.content == "This is a test comment"
    assert comment.post_id == post_id
    assert comment.author_id == user_id
    assert comment.status == CommentStatus.PUBLISHED
    assert comment.is_spam is False

    # Verify post comment count was updated
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 1


@pytest.mark.asyncio
async def test_create_comment_spam_rejected(setup_data, monkeypatch):
    """Test that spam comments are rejected"""
    user_id, post_id, _ = setup_data

    # Mock spam analysis to return spam
    mock_analyze_comment = AsyncMock(return_value={
        "is_spam": True,
        "spam_score": 0.9
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_comment
    )

    comment_data = CommentCreate(
        content="Click here for free money!!!",
        post_id=post_id
    )

    # Spam comment should not be created
    comment_id = await Comment.create(comment_data, user_id)
    assert comment_id is None

    # Verify post comment count was not updated
    post = await Post.get_by_id(post_id)
    assert post.comment_count == 0


@pytest.mark.asyncio
async def test_get_comments_by_post(setup_data, monkeypatch):
    """Test getting comments for a post"""
    user_id, post_id, _ = setup_data

    # Mock spam analysis
    mock_analyze_comment = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_comment
    )

    # Create multiple comments
    comment1_data = CommentCreate(content="First comment", post_id=post_id)
    comment2_data = CommentCreate(content="Second comment", post_id=post_id)

    comment1_id = await Comment.create(comment1_data, user_id)
    comment2_id = await Comment.create(comment2_data, user_id)

    # Get comments for the post
    comments = await Comment.get_by_post(post_id)
    
    assert len(comments) == 2
    comment_ids = {comment.id for comment in comments}
    assert comment_ids == {comment1_id, comment2_id}

    # Check content
    comment_contents = {comment.content for comment in comments}
    assert comment_contents == {"First comment", "Second comment"}


@pytest.mark.asyncio
async def test_update_comment(setup_data, monkeypatch):
    """Test updating a comment"""
    user_id, post_id, _ = setup_data

    # Mock spam analysis
    mock_analyze_comment = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_comment
    )

    # Create a comment
    comment_data = CommentCreate(
        content="Original content",
        post_id=post_id
    )
    comment_id = await Comment.create(comment_data, user_id)

    # Update the comment
    from models.comment import CommentUpdate
    update_data = CommentUpdate(content="Updated content")
    success = await Comment.update(comment_id, update_data)
    assert success is True

    # Verify update
    updated_comment = await Comment.get_by_id(comment_id)
    assert updated_comment.content == "Updated content"
    assert updated_comment.updated_at > updated_comment.created_at


@pytest.mark.asyncio
async def test_mark_comment_as_spam(setup_data, monkeypatch):
    """Test marking a comment as spam"""
    user_id, post_id, _ = setup_data

    # Mock spam analysis
    mock_analyze_comment = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_comment
    )

    # Create a comment
    comment_data = CommentCreate(
        content="Normal comment",
        post_id=post_id
    )
    comment_id = await Comment.create(comment_data, user_id)

    # Mark as spam
    await Comment.mark_as_spam(comment_id, 0.8, True)

    # Verify it's marked as spam
    comment = await Comment.get_by_id(comment_id)
    assert comment.is_spam is True
    assert comment.spam_score == 0.8
    assert comment.status == CommentStatus.SPAM

    # Verify it's in spam set
    spam_count = await Comment.count_spam()
    assert spam_count == 1


@pytest.mark.asyncio
async def test_comment_count_methods(setup_data, monkeypatch):
    """Test comment counting methods"""
    user_id, post_id, _ = setup_data

    # Initially should be 0
    total_count = await Comment.count_all()
    spam_count = await Comment.count_spam()
    assert total_count == 0
    assert spam_count == 0

    # Mock spam analysis - one normal, one spam
    mock_analyze_normal = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    mock_analyze_spam = AsyncMock(return_value={
        "is_spam": True,
        "spam_score": 0.9
    })

    # Create normal comment
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_normal
    )
    comment1_data = CommentCreate(content="Normal comment", post_id=post_id)
    await Comment.create(comment1_data, user_id)

    # Try to create spam comment (should be rejected)
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_comment",
        mock_analyze_spam
    )
    comment2_data = CommentCreate(content="Spam comment", post_id=post_id)
    spam_id = await Comment.create(comment2_data, user_id)
    assert spam_id is None  # Spam comments are not created

    # Check counts
    total_count = await Comment.count_all()
    spam_count = await Comment.count_spam()
    assert total_count == 1  # Only the normal comment was created
    assert spam_count == 0   # No spam comments in the system

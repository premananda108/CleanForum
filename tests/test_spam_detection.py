import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
from models.database import db
from models.user import User, UserCreate
from models.category import Category, CategoryCreate
from models.post import Post, PostCreate, PostStatus
from config import settings


@pytest_asyncio.fixture(scope="function")
async def setup_spam_test_data(monkeypatch):
    """Setup test data for spam detection tests"""
    # Force test settings
    monkeypatch.setattr(settings, 'TESTING', True)
    monkeypatch.setattr(settings, 'REDIS_PORT', 6380)

    await db.connect()
    await db.flush_db()

    # Create test user
    user_data = UserCreate(
        username="spamtest_user",
        email="spamtest@example.com", 
        password="password123"
    )
    user_id = await User.create(user_data)

    # Create test category
    category_data = CategoryCreate(
        name="Spam Test Category",
        description="Category for spam testing"
    )
    category_id = await Category.create(category_data)

    yield user_id, category_id

    await db.disconnect()


@pytest.mark.asyncio
async def test_post_not_spam(setup_spam_test_data, monkeypatch):
    """Test that legitimate posts get PUBLISHED status"""
    user_id, category_id = setup_spam_test_data

    # Mock spam analysis to return not spam
    mock_analyze = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1,
        "details": "Low spam probability"
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze
    )

    legitimate_post_data = PostCreate(
        title="How to Learn Python Programming",
        content="Python is a great programming language for beginners. Here are some tips...",
        category_id=category_id,
        tags=["python", "programming", "learning"]
    )

    # Create the legitimate post
    post_id = await Post.create(legitimate_post_data, user_id)
    assert post_id is not None

    # Verify it's marked as legitimate
    post = await Post.get_by_id(post_id)
    assert post.status == PostStatus.PUBLISHED
    assert post.is_spam is False
    assert post.spam_score == 0.1

    # Verify spam count is still 0
    spam_count = await Post.count_spam()
    assert spam_count == 0


@pytest.mark.asyncio
async def test_post_filtering_by_status(setup_spam_test_data, monkeypatch):
    """Test that get_all only returns published posts"""
    user_id, category_id = setup_spam_test_data

    # Create one legitimate post
    mock_analyze_legit = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze_legit
    )

    legit_post_data = PostCreate(
        title="Legitimate Post",
        content="This is a normal post",
        category_id=category_id,
        tags=[]
    )
    await Post.create(legit_post_data, user_id)

    # Create one spam post
    mock_analyze_spam = AsyncMock(return_value={
        "is_spam": True,
        "spam_score": 0.9
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze_spam
    )

    spam_post_data = PostCreate(
        title="SPAM POST!!!",
        content="Free money click here!!!",
        category_id=category_id,
        tags=[]
    )
    await Post.create(spam_post_data, user_id)

    # get_all should only return the published post
    posts, total = await Post.get_all()
    assert len(posts) == 1
    assert total == 1
    assert posts[0].title == "Legitimate Post"
    assert posts[0].status == PostStatus.PUBLISHED


@pytest.mark.asyncio
async def test_post_filtering_by_category_and_status(setup_spam_test_data, monkeypatch):
    """Test that get_by_category only returns published posts"""
    user_id, category_id = setup_spam_test_data

    # Create another category
    other_category_data = CategoryCreate(
        name="Other Category",
        description="Another category"
    )
    other_category_id = await Category.create(other_category_data)

    # Create legitimate post in first category
    mock_analyze_legit = AsyncMock(return_value={
        "is_spam": False,
        "spam_score": 0.1
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze_legit
    )

    legit_post_data = PostCreate(
        title="Legitimate Post in Category 1",
        content="This is a normal post in category 1",
        category_id=category_id,
        tags=[]
    )
    await Post.create(legit_post_data, user_id)

    # Create spam post in first category
    mock_analyze_spam = AsyncMock(return_value={
        "is_spam": True,
        "spam_score": 0.9
    })
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze_spam
    )

    spam_post_data = PostCreate(
        title="SPAM in Category 1",
        content="Free money!!!",
        category_id=category_id,
        tags=[]
    )
    await Post.create(spam_post_data, user_id)

    # Create legitimate post in second category
    monkeypatch.setattr(
        "services.vector_classifier.vector_classifier.analyze_with_vectors",
        mock_analyze_legit
    )

    other_legit_post_data = PostCreate(
        title="Legitimate Post in Category 2",
        content="This is a normal post in category 2",
        category_id=other_category_id,
        tags=[]
    )
    await Post.create(other_legit_post_data, user_id)

    # get_by_category for first category should only return the legitimate post
    posts, total = await Post.get_by_category(category_id)
    assert len(posts) == 1
    assert total == 1
    assert posts[0].title == "Legitimate Post in Category 1"
    assert posts[0].category_id == category_id

    # get_by_category for second category should return its legitimate post
    posts, total = await Post.get_by_category(other_category_id)
    assert len(posts) == 1
    assert total == 1
    assert posts[0].title == "Legitimate Post in Category 2"
    assert posts[0].category_id == other_category_id


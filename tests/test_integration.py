import sys
import os
import pytest
from fastapi.testclient import TestClient
import redis
import time

# Set the environment variable for the test Redis database BEFORE importing the app
os.environ['REDIS_URL'] = 'redis://localhost:6381/1'

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

@pytest.fixture(scope="function")
def client():
    """A fixture to create a TestClient for the app."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def setup_and_teardown(client):
    """Clean the test database before each test."""
    test_redis = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
    test_redis.flushdb()
    yield
    test_redis.flushdb()
    test_redis.close()


def test_health_check(client):
    """Tests that the API is healthy."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_full_flow_with_training(client):
    """
    Tests the full flow:
    1. Before training, posts are blocked because they are dissimilar.
    2. Train the model synchronously.
    3. Post a legitimate message, which should now be accepted.
    4. Post a spam message, which should be blocked.
    5. Check that stats are updated correctly.
    """
    # 1. Before training, check that a post is blocked
    pre_train_response = client.post("/api/posts", json={
        "author": "testuser",
        "title": "A legit post",
        "content": "This is a normal discussion about Python."
    })
    assert pre_train_response.status_code == 403
    assert "Post is too dissimilar" in pre_train_response.json()["detail"]

    # 2. Train the model in the foreground
    train_response = client.post("/api/train?background=false")
    assert train_response.status_code == 202  # 202 is correct, the task is accepted
    
    # Give the background task a moment to complete.
    # This is a pragmatic compromise for testing background tasks.
    time.sleep(30) # Wait for training to likely finish

    # 3. Post a legitimate message
    legit_response = client.post("/api/posts", json={
        "author": "testuser",
        "title": "A legit post",
        "content": "This is a normal discussion about Python."
    })
    assert legit_response.status_code == 201
    assert legit_response.json()["title"] == "A legit post"

    # 4. Post a spam message
    spam_response = client.post("/api/posts", json={
        "author": "spammer",
        "title": "Free Money",
        "content": "click here to earn money fast"
    })
    assert spam_response.status_code == 403
    assert "Post rejected as spam" in spam_response.json()["detail"]

    # 5. Check statistics
    stats_response = client.get("/api/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    # total_classified should be 3: one blocked before training, one legit, one spam
    assert stats["total_classified"] == 3
    # spam_detected should be 2: one dissimilar, one actual spam
    assert stats["spam_detected"] == 2
    assert stats["vectors_in_db"] > 0

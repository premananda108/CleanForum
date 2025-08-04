# 🧪 API Request Examples for Testing

After populating the database using `populate_database.py`, you can test the API with these requests.

## 📋 Prerequisites

1. Start the server:
   ```bash
   python main.py
   ```

2. The server will be available at: `http://localhost:8000`

## 🔍 Basic API Requests

### 1. Get a list of all posts
```bash
curl -X GET "http://localhost:8000/api/posts?limit=10&offset=0"
```

### 2. Get posts of a specific category
```bash
# First, get the category ID from the list of categories
curl -X GET "http://localhost:8000/api/categories"

# Then, request posts of the category (replace CATEGORY_ID)
curl -X GET "http://localhost:8000/api/posts?category_id=CATEGORY_ID&limit=5"
```

### 3. Get a specific post
```bash
# Replace POST_ID with a real post ID from the list
curl -X GET "http://localhost:8000/api/posts/POST_ID"
```

### 4. Search for posts
```bash
# Search by keyword
curl -X GET "http://localhost:8000/api/search?q=earnings&limit=5"

# Vector search for similar posts
curl -X POST "http://localhost:8000/api/search/similar" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "How to make money",
    "content": "I want to find ways to make money online",
    "tags": ["money", "earnings"]
  }'
```

### 5. Get categories
```bash
curl -X GET "http://localhost:8000/api/categories"
```

### 6. Create a new post
```bash
curl -X POST "http://localhost:8000/api/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Post",
    "content": "This is the content of the test post for API checking",
    "category_id": "CATEGORY_ID",
    "tags": ["test", "api"]
  }'
```

### 7. Moderator Panel
```bash
# Get all posts for moderation (including spam)
curl -X GET "http://localhost:8000/api/moderator/posts?limit=20"

# Get spam statistics
curl -X GET "http://localhost:8000/api/moderator/spam-stats"

# Get information about the vector classifier
curl -X GET "http://localhost:8000/api/moderator/classifier-stats"
```

### 8. Spam analysis for a post
```bash
# Get spam analysis results (replace POST_ID)
curl -X GET "http://localhost:8000/api/posts/POST_ID/spam-analysis"
```

## 🌐 Web Interface

HTML pages are also available:

- **Main page:** http://localhost:8000/
- **Create post:** http://localhost:8000/create
- **Moderator panel:** http://localhost:8000/moderator
- **Search:** http://localhost:8000/search
- **Category:** http://localhost:8000/category/CATEGORY_ID
- **Post page:** http://localhost:8000/posts/POST_ID

## 📊 Useful Debugging Queries

### Health check
```bash
curl -X GET "http://localhost:8000/health"
```

### Get application logs
```bash
curl -X GET "http://localhost:8000/api/logs"
```

### API documentation (Swagger)
Open in browser: http://localhost:8000/docs

## 🧪 Test Scenarios

### Scenario 1: Spam filtering check
1. Get a list of all posts
2. Pay attention to posts with the status "spam"
3. Try to create a new post with suspicious content
4. Check how the system detects spam

### Scenario 2: Search testing
1. Perform a text search for the word "earnings"
2. Try a vector search with similar content
3. Compare the results of regular and vector search

### Scenario 3: Moderator actions
1. Open the moderator panel
2. View all posts, including spam
3. Check the classification statistics

## 🔧 API Response Examples

### Successful response for getting posts:
```json
[
  {
    "id": "uuid-string",
    "title": "Post Title",
    "content": "Post content...",
    "category_id": "category-uuid",
    "category_name": "Technology",
    "author_id": "user-uuid",
    "author_username": "alice_blogger",
    "tags": ["tag1", "tag2"],
    "status": "published",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00",
    "view_count": 5,
    "comment_count": 0,
    "vote_score": 0,
    "is_spam": false,
    "spam_score": 0.1,
    "reading_time": 2
  }
]
```

### Response when creating a spam post:
```json
{
  "detail": "Your post has been identified as spam and cannot be published."
}
```

## 🚨 Error Handling

### 404 - Post not found
```json
{
  "detail": "Post not found"
}
```

### 422 - Spam detected
```json
{
  "detail": "Your post has been identified as spam and cannot be published."
}
```

### 500 - Internal server error
```json
{
  "detail": "Internal error creating post"
}
```

## 📝 Additional Tools

### HTTPie (alternative to curl)
```bash
# Installation
pip install httpie

# Usage examples
http GET localhost:8000/api/posts
http POST localhost:8000/api/posts title="Test" content="Content" category_id="CATEGORY_ID" tags:='["test"]'
```

### Postman Collection
Import the URL `http://localhost:8000/docs` into Postman to automatically create a collection of requests.

# 🗄️ Database Management Scripts

This set of scripts is intended for managing the CleanForum forum database.

## 📋 List of Scripts

### 1. `populate_database.py` - Populate the database with test data
Creates a full set of test data without spam checking:
- 5 users (including a moderator)
- 5 categories
- Posts from `spam_dataset.json` (marked as spam)
- Additional legitimate posts
- Vector indexes for search

### 2. `clear_database.py` - Clear the database
Completely deletes all data from the Redis database.

### 3. `reindex_posts.py` - Re-index posts
Recreates vector indexes for all existing posts.

### 4. `drop_index.py` - Delete the search index
Deletes only the vector search index.

## 🚀 Usage

### Initial Database Setup

1. **Clear the database (if you need to start over):**
   ```bash
   python clear_database.py
   ```
   ⚠️ **WARNING:** Deletes ALL data!

2. **Populate with test data:**
   ```bash
   python populate_database.py
   ```

### Search Index Management

3. **Re-index existing posts:**
   ```bash
   python reindex_posts.py
   ```

4. **Delete only the search index:**
   ```bash
   python drop_index.py
   ```

## 📊 What `populate_database.py` Creates

### Users:
- `alice_blogger` - regular user
- `bob_writer` - regular user
- `charlie_spam` - spammer user
- `diana_expert` - expert
- `moderator_1` - moderator

### Categories:
- General
- Technology
- Finance
- Health
- Flood
- Spam

### Posts:
- 8 spam posts from `spam_dataset.json`
- 5 legitimate posts with useful content
- All posts have random creation dates (1-30 days ago)
- Vector indexes for search are created

## 🔧 Implementation Details

### Bypassing Spam Check
The `populate_database.py` script creates posts using a special method `create_post_without_spam_check()`, which:
- Skips analysis by the vector classifier
- Sets the post status directly
- Creates vector indexes for search
- Updates all necessary counters

### Logging
All scripts provide detailed logging of operations:
- ✅ Successful operations
- ❌ Errors with details
- 📊 Statistics of created data

### Security
- `clear_database.py` requires "YES" confirmation
- All operations are performed in try-catch blocks
- Correct closing of database connections

## 🎯 Usage Examples

### Full Reset and Population:
```bash
# 1. Clear the database
python clear_database.py
# Enter "YES" when prompted

# 2. Populate with new data
python populate_database.py
```

### Update Only Indexes:
```bash
# Delete the index
python drop_index.py

# Recreate the index
python reindex_posts.py
```

## 📈 Execution Result

After running `populate_database.py`, you will get:
- 5 users with different roles
- 5 categories for posts
- ~13 posts (8 spam + 5 legitimate)
- Fully configured vector indexes
- Correct counters and statistics

### Example Statistics Output:
```
📊 Statistics of created data:
👥 Users: 5
📁 Categories: 5
📝 Total posts: 13
🚫 Spam posts: 8
✅ Legitimate posts: 5
🔍 Vectors in search index: 13
```

## 🐛 Troubleshooting

### Problem: "User already exists"
The script automatically skips the creation of existing users and uses their IDs.

### Problem: "Vector index is not created"
1. Make sure Redis supports RediSearch
2. Check the installation of sentence-transformers
3. Check the settings in `config.py`

### Problem: "Error connecting to Redis"
Check the Redis settings in the `.env` file:
```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## 📝 Logs and Debugging

All scripts create detailed logs in the console. For debugging, you can change the logging level:

```python
logging.basicConfig(level=logging.DEBUG)  # For detailed debugging
```

## ⚠️ Important Notes

1. **Security:** User passwords are stored in plain text for testing purposes
2. **Performance:** The script creates vectors synchronously - it may be slow for large amounts of data
3. **Data:** All creation dates are generated randomly in the range of 1-365 days ago
4. **Indexes:** Vector indexes are created automatically when adding posts

## 🔗 Related Files

- `spam_dataset.json` - Source data for spam posts
- `config.py` - Application settings
- `models/` - Data models
- `services/` - Services for working with vectors and spam detection

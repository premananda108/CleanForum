---
title: A Practical Guide to Building a "Similar Posts" Feature with Redis and Python
tags: [redis, python, ai, tutorial]
cover_image: https://res.cloudinary.com/practicaldev/image/fetch/s--V8b3g2_G--/c_imagga_scale,f_auto,fl_progressive,h_420,q_auto,w_1000/https://raw.githubusercontent.com/redis-developer/Redis-AI-Challenge/main/images/vector-search-animation.gif
---

Ever wondered how sites like DEV.to or Stack Overflow magically show you a list of "similar posts"? It's a key feature for user engagement, keeping readers on your site by showing them relevant content. In this article, we'll walk through exactly how to build this feature from scratch using the power of Redis Stack and Python.

This system is the backbone of our project, **CleanForum**, where we use it not only to show users related content but also as a core component of our AI-powered spam detector. This is our entry for the **[Redis AI Challenge](https://dev.to/devteam/join-the-redis-ai-challenge-3000-in-prizes-3oj2)**.

### The Core Idea: From Words to Vectors

To find "similar" posts, we first need to quantify what "similar" means. We do this by converting the text of each post into a **vector embedding**—a list of numbers that acts as a semantic fingerprint. Two posts with similar meanings will have vectors that are "close" to each other in multi-dimensional space.

We use the popular `SentenceTransformer` library in Python to handle this conversion.

### Step 1: Storing the Data in Redis

A key part of our design is separating the canonical post data from the data used for searching. This keeps our search index lean and fast. We use two different Redis `HASH` structures for each post.

#### The "Source of Truth" Hash

This hash stores everything needed to display and interact with a post. It is the single source of truth.

-   **Key**: `post:<uuid>`
-   **Schema**:
    | Field | Data Type | Description |
    |---|---|---|
    | `id` | `string` | Post UUID. |
    | `title` | `string` | Full title of the post. |
    | `content` | `string` | Clean text of the post. |
    | `is_spam` | `string` | `"True"` or `"False"`. |
    | `...` | `...` | (Other metadata) |

#### The "Search Index" Hash

This hash stores only the data needed by RediSearch. It's a lightweight record designed purely for indexing.

-   **Key**: `vector:post:<uuid>`
-   **Schema**:
    | Field | Data Type (in Redis) | Description |
    |---|---|---|
    | `vector` | `binary` | Binary vector (embedding) of the post. |
    | `title` | `string` (TEXT) | Title for full-text search. |
    | `content` | `string` (TEXT) | Text for full-text search. |

Here's the Python code that creates this search record:

```python
# From services/redis_manager.py
async def add_vector(self, doc_id: str, vector: np.ndarray, 
                    title: str, content: str) -> bool:
    """Add a vector to the index."""
    doc_key = f"vector:{doc_id}"
    vector_bytes = vector.astype(np.float32).tobytes()

    # Store only the data needed for search
    await self.redis_client.hset(doc_key, mapping={
        "vector": vector_bytes,
        "title": title.encode('utf-8'),
        "content": content[:500].encode('utf-8')
    })
    return True
```

### Step 2: The Magic of a RediSearch Schema

We define a search index that tells Redis what to pay attention to. We configure it to automatically index any hash whose key starts with `vector:`.

```python
# From services/redis_manager.py
async def create_index(self):
    """Create the search index schema."""
    schema = [
        "vector", "VECTOR", "HNSW", "6",
        "TYPE", "FLOAT32",
        "DIM", "384", # all-MiniLM-L6-v2 model dimension
        "DISTANCE_METRIC", "COSINE",
        "title", "TEXT",
        "content", "TEXT"
    ]

    await self.redis_client.execute_command(
        "FT.CREATE", self.index_name,
        "ON", "HASH",
        "PREFIX", "1", "vector:", # Index keys with this prefix
        "SCHEMA", *schema
    )
```

### Step 3: Finding Similar Posts with a Query

This is where the magic happens. To find posts similar to a new one, we generate its vector and use it in a **K-Nearest Neighbor (KNN)** query.

The query looks like this: `*=>[KNN 9 @vector $blob AS score]`

-   `*`: A filter that matches all documents.
-   `=>`: Indicates this is a hybrid query.
-   `[KNN 9 @vector $blob AS score]`: This is the vector search part.
    -   `KNN 9`: Find the 9 nearest neighbors.
    -   `@vector`: Search in the `vector` field of our index.
    -   `$blob`: A parameter for our query vector.
    -   `AS score`: Name the result of the distance calculation `score`.

Our Python function handles sending this query to Redis:

```python
# From services/redis_manager.py
async def search_similar(self, query_vector: np.ndarray, k: int = 9):
    """Search for k-nearest neighbors."""
    query_bytes = query_vector.astype(np.float32).tobytes()
    
    query = f"*=>[KNN {k} @vector $blob AS score]"
    
    results = await self.redis_client.execute_command(
        "FT.SEARCH", self.index_name, query,
        "PARAMS", "2", "blob", query_bytes,
        "DIALECT", "2",
        "RETURN", "3", "score", "title", "doc_id"
    )
    # ... logic to parse results ...
    return parsed_results
```

This command is incredibly fast and returns a list of the closest document IDs.

### Step 4: Putting It All Together - The User View

The search gives us a list of IDs. We then loop through these IDs and fetch the full "source of truth" hash for each one (`post:<id>`). This gives us a list of complete, real-time post objects that we can display to the user.

Because we fetch the full post object, we can show its title, author, and its real-time spam status, ensuring the data is always consistent.

### Bonus: The Power of a Hybrid System (Spam Detection)

This "similar posts" feature is powerful on its own, but it's also the engine for our spam detector. The logic is simple:

1.  Find the list of similar posts for a new submission.
2.  Check the real-time `is_spam` flag for each of those neighbors.
3.  If a high percentage of the neighbors are spam, the new post is probably spam too.

This hybrid approach, combining a user-facing feature with a backend security system, allowed us to build a robust and efficient application with Redis as the core.

### Conclusion

Redis is far more than a simple key-value store. By using its integrated Hash, Sorted Set, and RediSearch capabilities, we were able to build a sophisticated AI-powered "similar posts" feature with a surprisingly simple and maintainable architecture. It's a testament to the power of having a true multi-model database at your fingertips.

#RedisAIChallenge

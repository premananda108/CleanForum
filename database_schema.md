# Technical Specification: Redis Data Schema

Date: 02.08.2025
Version: 1.0

This document describes the structure and purpose of the keys used in the Redis database for the CleanForum project. It serves as a technical specification for developers to ensure data consistency.

---

## 1. Main Post Object

Stores complete information about a post. It is the **source of truth** for display on pages.

- **Key Template:** `post:<uuid>`
- **Type:** `HASH`
- **Example Key:** `post:a1b2c3d4-e5f6-7890-1234-567890abcdef`

### Fields:

| Field            | Data Type | Description                                                              |
|------------------|-----------|--------------------------------------------------------------------------|
| `id`             | `string`  | Post UUID, duplicates part of the key.                                   |
| `title`          | `string`  | Full title of the post.                                                  |
| `content`        | `string`  | The content of the post in Markdown format. |
| `category_id`    | `string`  | UUID of the category to which the post belongs.                          |
| `author_id`      | `string`  | UUID of the post's author.                                               |
| `tags`           | `string`  | JSON array of strings with tags, e.g., `["python", "redis"]`.            |
| `status`         | `string`  | Post status: `published`, `draft`, `moderated`, `spam`, `deleted`.       |
| `created_at`     | `string`  | Creation date in ISO 8601 format.                                        |
| `updated_at`     | `string`  | Last update date in ISO 8601 format.                                     |
| `view_count`     | `integer` | View counter.                                                            |
| `comment_count`  | `integer` | Comment counter.                                                         |
| `vote_score`     | `integer` | Post rating (sum of votes).                                              |
| `is_spam`        | `string`  | Spam flag: `"True"` or `"False"`.                                        |
| `spam_score`     | `float`   | Spam score from 0.0 to 1.0.                                              |
| `reading_time`   | `integer` | Estimated reading time in minutes.                                       |

---

## 2. Post Index Object (for Search)

Stores data intended **exclusively for the RediSearch search engine**. It is created and updated in parallel with the main post object.

- **Key Template:** `vector:post:<uuid>`
- **Type:** `HASH`
- **Example Key:** `vector:post:a1b2c3d4-e5f6-7890-1234-567890abcdef`
- **Important:** This key is indexed by RediSearch according to the `PREFIX` rule in the index schema.

### Fields:

| Field     | Data Type (in Redis) | Description                                                              |
|-----------|----------------------|--------------------------------------------------------------------------|
| `vector`  | `binary`             | Binary vector (embedding) of the post for vector search.                 |
| `title`   | `string` (TEXT)      | Post title for full-text search.                                         |
| `content` | `string` (TEXT)      | Clean text of the post for full-text search.                             |
| `doc_id`  | `string`             | Post UUID without prefixes for feedback.                                 |

---

## 3. Lists and Sets (for Relations and Sorting)

These structures are used for quickly retrieving lists of posts without scanning the entire database.

- **All posts (sorted by time):**
  - **Key:** `posts:all`
  - **Type:** `SORTED SET`
  - **Value:** `post_id`
  - **Score:** `timestamp` of post creation.

- **Posts by category:**
  - **Key:** `posts:category:<category_id>`
  - **Type:** `SORTED SET`

- **Posts by author:**
  - **Key:** `posts:author:<author_id>`
  - **Type:** `SORTED SET`

- **Posts marked as spam:**
  - **Key:** `posts:spam`
  - **Type:** `SET`

---

## 4. Category Object

- **Key Template:** `category:<uuid>`
- **Type:** `HASH`

### Fields:

| Field       | Data Type | Description                               |
|-------------|-----------|-------------------------------------------|
| `id`        | `string`  | Category UUID.                            |
| `name`      | `string`  | Category name.                            |
| `description`| `string` | Category description.                     |
| `post_count`| `integer` | Number of posts in this category.         |
| `color`     | `string`  | Category color in HEX (e.g., `#FF5733`). |

---

## 5. Search Index

- **Index Name:** `forum_posts_index` (set in `config.py`)
- **Indexed Prefixes:** `vector:post:`, `vector:comment:`
- **Schema:**
  - `vector`: VECTOR (HNSW)
  - `title`: TEXT
  - `content`: TEXT

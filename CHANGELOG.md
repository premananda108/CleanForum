# Changelog

## [Unreleased]

### Added
- **Infrastructure for automated testing:**
    - A separate Docker container with Redis has been configured for safe test execution, isolated from the main database.
    - `pytest` and `pytest-anyio` have been integrated into the project for asynchronous API testing.
    - The first test (`test_get_similar_posts`) has been created, which checks the correctness of the similar posts search function. The test automatically prepares test data (categories, posts) and verifies that the API returns relevant results.
- **Post editing:** Authors can now edit their own posts. An editing page and corresponding logic on the backend and frontend have been added.
- **Post deletion by moderator:** The ability to "soft" delete posts has been added to the moderator panel.
- **Modern text editor:** The standard text input field has been replaced with the modern block-style editor Editor.js, which saves content in a safe JSON format.

### Changed
- **Text search:**
    - Fixed an issue with full-text search in RediSearch where queries returned no results.
    - Identified and fixed a bug related to incorrect decoding of `doc_id` in `models/post.py` when using `decode_responses=True` in the Redis client.
    - Simplified the search query in `models/post.py` for basic exact word matching.
    - Ensured the use of the `NOCONTENT` option in RediSearch queries to prevent errors when decoding binary fields.
- **Spam handling logic:**
    - Posts and comments identified as spam are no longer saved to the database. Instead, the API returns a `422 Unprocessable Entity` error.
    - **Fixed the feedback system:** Now, when a moderator marks content as spam or approves it, the corresponding `label` in the Redis vector database is immediately updated. This allows the system to learn from moderator actions in real-time and improve spam detection quality.
- **Moderator interface:**
    - In the moderator panel (`/moderator`), the "Content Statistics" and "Comments for Moderation" blocks have been swapped for more convenient access.
- **Visual style:**
    - The site's color scheme has been updated to green and gold. The changes have been applied to the base template (`base.html`) and the main page (`index.html`).

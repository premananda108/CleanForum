# Changelog

## [Unreleased] - 2025-08-09

### Fixed

- Resolved a `KeyError` that occurred when viewing the spam analysis for some posts. The error was caused by incomplete data for "neighbor" posts in the Redis cache.
- The `Post.get_by_id` method in `models/post.py` has been made more robust to handle cases where fields such as `category_id` or `author_id` are missing from the cached post data. The method now uses the `.get()` dictionary method to safely access these fields, preventing crashes and allowing the spam analysis to be displayed even with incomplete data.

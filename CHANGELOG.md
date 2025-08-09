# Changelog

## [Unreleased] - 2025-08-09

### Added

- Added a "Published/Spam" filter for posts in the moderator panel.
- Added a "Published/Spam" filter for comments in the moderator panel.
- Added a "Not Moderated/Moderated" filter for posts in the moderator panel.
- When a moderator approves a post, a `moderated: True` flag is now added to the post's data in Redis for informational purposes.
- The moderator panel now displays a "Moderated" badge for posts that have the `moderated` flag, providing more information to the moderators.

### Fixed

- Fixed a bug where the toggle switches for the filters were not visually changing when toggled.
- Fixed a bug where the "Moderated" badge was not appearing when a moderator marked a post as spam.
- Resolved a `TypeError` in the `moderate_post` function in `api/moderator.py` by correcting the usage of the `db.hset` method.
- Resolved a `KeyError` that occurred when viewing the spam analysis for some posts. The error was caused by incomplete data for "neighbor" posts in the Redis cache.
- The `Post.get_by_id` method in `models/post.py` has been made more robust to handle cases where fields such as `category_id` or `author_id` are missing from the cached post data. The method now uses the `.get()` dictionary method to safely access these fields, preventing crashes and allowing the spam analysis to be displayed even with incomplete data.

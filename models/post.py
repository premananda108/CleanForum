"""
Post model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid
import json
from models.database import db
from config import settings

class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    MODERATED = "moderated"
    SPAM = "spam"
    DELETED = "deleted"

class PostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10)
    category_id: str
    tags: List[str] = Field(default_factory=list, max_length=10)

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    category_id: Optional[str] = None
    tags: Optional[List[str]] = Field(None, max_length=10)

class PostResponse(BaseModel):
    id: str
    title: str
    content: str  # Now this is Markdown content
    category_id: str
    category_name: str = ""
    author_id: str
    author_username: str = ""
    tags: List[str]
    status: PostStatus
    created_at: datetime
    updated_at: datetime
    view_count: int = 0
    comment_count: int = 0
    vote_score: int = 0
    is_spam: bool = False
    spam_score: float = 0.0
    reading_time: int = 0  # in minutes
    similar_posts: Optional[List['PostResponse']] = None
    moderated: bool = False

class Post:
    """Class for working with posts"""

    @staticmethod
    def calculate_reading_time(text_content: str) -> int:
        """Calculate reading time (approximately 200 words per minute) based on plain text."""
        word_count = len(text_content.split())
        return max(1, word_count // 200)

    @staticmethod
    async def create(post_data: PostCreate, author_id: str) -> Optional[str]:
        """
        Create a new post with immediate spam analysis.
        If the post is identified as spam, it is saved with the SPAM status.
        """
        post_id = str(uuid.uuid4())
        now = datetime.now()

        # Markdown content
        text_for_analysis = post_data.content

        # Perform spam analysis
        from services.vector_classifier import vector_classifier
        analysis_results = await vector_classifier.analyze_with_vectors(
            post_id, post_data.title, text_for_analysis, post_data.tags, author_id
        )

        is_spam = analysis_results.get("is_spam", False)
        spam_score = analysis_results.get("spam_score", 0.0)

        if is_spam:
            import logging
            logging.warning(f"Post from {author_id} was identified as SPAM (score: {spam_score:.2f}) and will be saved with 'spam' status.")
            status = PostStatus.SPAM
        else:
            status = PostStatus.PUBLISHED

        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": text_for_analysis,
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": status.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": 0,
            "comment_count": 0,
            "vote_score": 0,
            "is_spam": str(is_spam),
            "spam_score": spam_score,
            "reading_time": Post.calculate_reading_time(text_for_analysis)
        }

        # Save the post
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"post:{post_id}", mapping=post_info)
            timestamp = now.timestamp()
            pipe.zadd("posts:all", {post_id: timestamp})
            pipe.zadd(f"posts:author:{author_id}", {post_id: timestamp})
            pipe.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
            await pipe.execute()

        # --- Start of new code ---
        # After successful saving, add the post to the search index
        try:
            from services.redis_manager import vector_manager
            # Make sure the classifier is initialized to create a vector
            if not vector_classifier.is_initialized:
                await vector_classifier.initialize()

            post_vector = vector_classifier.create_vector(post_data.title, text_for_analysis, post_data.tags)

            await vector_manager.add_vector(
                doc_id=f"post:{post_id}",
                vector=post_vector,
                title=post_data.title,
                content=text_for_analysis
            )
            import logging
            logging.info(f"Post {post_id} successfully added to the search index.")
        except Exception as e:
            import logging
            logging.error(f"Could not add post {post_id} to the search index: {e}", exc_info=True)
        # --- End of new code ---

        return post_id

    @staticmethod
    async def get_by_id(post_id: str, increment_views: bool = False) -> Optional[PostResponse]:
        """Get a post by ID"""
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return None

        # Increment the view counter
        if increment_views:
            new_view_count = int(post_data.get("view_count", 0)) + 1
            await db.hset(f"post:{post_id}", {"view_count": new_view_count})
            post_data["view_count"] = str(new_view_count)

        # Get additional information
        from models.category import Category
        from models.user import User

        category_id = post_data.get("category_id")
        category = await Category.get_by_id(category_id) if category_id else None

        author_id = post_data.get("author_id")
        author = await User.get_by_id(author_id) if author_id else None

        return PostResponse(
            id=post_data.get("id"),
            title=post_data.get("title"),
            content=post_data.get("content"),
            category_id=category_id,
            category_name=category.name if category else "Unknown",
            author_id=author_id,
            author_username=author.username if author else "Unknown",
            tags=json.loads(post_data.get("tags", "[]")),
            status=PostStatus(post_data.get("status", "draft")),
            created_at=datetime.fromisoformat(post_data.get("created_at")),
            updated_at=datetime.fromisoformat(post_data.get("updated_at")),
            view_count=int(post_data.get("view_count", 0)),
            comment_count=int(post_data.get("comment_count", 0)),
            vote_score=int(post_data.get("vote_score", 0)),
            is_spam=post_data.get("is_spam", "False") == "True",
            spam_score=float(post_data.get("spam_score", 0.0)),
            reading_time=int(post_data.get("reading_time", 1)),
            moderated=post_data.get("moderated", "False") == "True"
        )

    @staticmethod
    async def get_all(limit: int = 20, offset: int = 0) -> (List[PostResponse], int):
        """Get a list of posts and the total count of published posts."""
        all_post_ids = await db.zrevrange("posts:all", 0, -1)

        # Use a pipeline to fetch all statuses efficiently
        pipe = db.redis_client.pipeline()
        for post_id in all_post_ids:
            pipe.hget(f"post:{post_id}", "status")
        statuses = await pipe.execute()

        published_post_ids = [
            post_id for post_id, status in zip(all_post_ids, statuses)
            if status and status == PostStatus.PUBLISHED.value
        ]

        total_published = len(published_post_ids)

        paginated_ids = published_post_ids[offset : offset + limit]

        posts = []
        for post_id in paginated_ids:
            post = await Post.get_by_id(post_id)
            if post: # Should always be true as we filtered
                posts.append(post)

        return posts, total_published

    @staticmethod
    async def get_by_category(category_id: str, limit: int = 20, offset: int = 0) -> (List[PostResponse], int):
        """Get posts by category and the total count."""
        all_post_ids_in_category = await db.zrevrange(f"posts:category:{category_id}", 0, -1)

        # Use a pipeline to fetch all statuses efficiently
        pipe = db.redis_client.pipeline()
        for post_id in all_post_ids_in_category:
            pipe.hget(f"post:{post_id}", "status")
        statuses = await pipe.execute()

        published_post_ids = [
            post_id for post_id, status in zip(all_post_ids_in_category, statuses)
            if status and status == PostStatus.PUBLISHED.value
        ]

        total_published = len(published_post_ids)

        paginated_ids = published_post_ids[offset : offset + limit]

        posts = []
        for post_id in paginated_ids:
            post = await Post.get_by_id(post_id)
            if post:
                posts.append(post)

        return posts, total_published

    @staticmethod
    async def get_all_for_moderation(limit: int = 50, offset: int = 0, status: Optional[str] = None, moderation: Optional[str] = None) -> (List[PostResponse], int):
        """Get all posts for moderation, with filtering and pagination."""
        all_post_ids = await db.zrevrange("posts:all", 0, -1)

        # Inefficient, but necessary for filtering without complex indexing
        filtered_ids = []
        for post_id in all_post_ids:
            post = await Post.get_by_id(post_id) # Inefficient to fetch full post here
            if post:
                # Apply filters
                if status and post.status.value != status:
                    continue
                if moderation == "moderated" and not post.moderated:
                    continue
                if moderation == "not_moderated" and post.moderated:
                    continue
                filtered_ids.append(post_id)

        total_count = len(filtered_ids)
        paginated_ids = filtered_ids[offset : offset + limit]

        # Fetch full details for the paginated list
        posts = []
        for post_id in paginated_ids:
            post = await Post.get_by_id(post_id)
            if post:
                posts.append(post)

        return posts, total_count

    @staticmethod
    async def update(post_id: str, post_data: PostUpdate) -> bool:
        """Update a post"""
        existing_data = await db.hgetall(f"post:{post_id}")
        if not existing_data:
            return False

        update_fields = {}
        reanalyze_spam = False

        if post_data.title is not None:
            update_fields["title"] = post_data.title
            reanalyze_spam = True
        if post_data.content is not None:
            update_fields["content"] = post_data.content
            update_fields["reading_time"] = Post.calculate_reading_time(post_data.content)
            reanalyze_spam = True
        if post_data.category_id is not None:
            update_fields["category_id"] = post_data.category_id
        if post_data.tags is not None:
            update_fields["tags"] = json.dumps(post_data.tags)
            reanalyze_spam = True

        if update_fields:
            update_fields["updated_at"] = datetime.now().isoformat()
            # Reset the spam status on any update to trigger a re-check
            if reanalyze_spam:
                update_fields["is_spam"] = str(False)
                update_fields["spam_score"] = 0.0
                update_fields["status"] = PostStatus.PUBLISHED.value

            await db.hset(f"post:{post_id}", mapping=update_fields)

        return True

    @staticmethod
    async def mark_as_spam(post_id: str, spam_score: float, is_spam: bool = True, moderated: bool = False):
        """Mark a post as spam and update its status."""
        if is_spam:
            status = PostStatus.SPAM.value
        elif moderated:
            status = PostStatus.MODERATED.value
        else:
            status = PostStatus.PUBLISHED.value

        await db.hset(f"post:{post_id}", {
            "is_spam": str(is_spam),
            "spam_score": spam_score,
            "status": status
        })

        if is_spam:
            await db.sadd("posts:spam", post_id)
        else:
            await db.srem("posts:spam", post_id)

    @staticmethod
    async def mark_as_deleted(post_id: str) -> bool:
        """
        Marks a post as deleted (soft delete).
        Removes the post from all lists, updates counters, and deletes the vector.
        """
        # 1. Get post data to know author_id and category_id
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return False  # Post not found

        author_id = post_data.get("author_id")
        category_id = post_data.get("category_id")

        # 2. Use a transaction for atomicity
        async with db.redis_client.pipeline(transaction=True) as pipe:
            # Mark the post as deleted
            pipe.hset(f"post:{post_id}", "status", PostStatus.DELETED.value)

            # Remove the post ID from all sorted sets
            pipe.zrem("posts:all", post_id)
            if category_id:
                pipe.zrem(f"posts:category:{category_id}", post_id)
            if author_id:
                pipe.zrem(f"posts:author:{author_id}", post_id)

            # Remove from the spam set if it was there
            pipe.srem("posts:spam", post_id)

            # Execute the transaction
            await pipe.execute()

        # 3. Update the post count in the category (outside the transaction)
        if category_id:
            from models.category import Category
            await Category.update_post_count(category_id, -1)

        # 4. Delete the vector from the search index (outside the transaction)
        from services.redis_manager import vector_manager
        await vector_manager.delete_vector(f"post:{post_id}")

        import logging
        logging.info(f"Post {post_id} was marked as deleted.")

        return True

    @staticmethod
    async def update_comment_count(post_id: str, delta: int = 1):
        """Update the number of comments"""
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            return

        new_count = int(post_data.get("comment_count", 0)) + delta
        await db.hset(f"post:{post_id}", {"comment_count": max(0, new_count)})

    @staticmethod
    async def count_all() -> int:
        """Count the total number of posts."""
        return await db.zcard("posts:all")

    @staticmethod
    async def count_spam() -> int:
        """Count the number of spam posts."""
        return await db.scard("posts:spam")

    @staticmethod
    async def count_published() -> int:
        """Count the number of published posts."""
        all_post_ids = await db.zrevrange("posts:all", 0, -1)
        published_count = 0
        for post_id in all_post_ids:
            post_data = await db.hgetall(f"post:{post_id}")
            if post_data and post_data.get("status") == PostStatus.PUBLISHED.value:
                published_count += 1
        return published_count

    @staticmethod
    async def get_similar_posts(post_id: str, limit: int = 5) -> List['PostResponse']:
        """Find similar posts using vector search."""
        import logging
        from services.redis_manager import vector_manager

        logging.info(f"Starting search for similar posts for post_id: {post_id}")

        vector_doc_id = f"post:{post_id}"
        post_vector = await vector_manager.get_vector_by_id(vector_doc_id)

        if post_vector is None:
            logging.warning(f"Vector for {vector_doc_id} not found. Cannot find similar posts.")
            return []

        logging.info(f"Vector for {vector_doc_id} retrieved successfully.")

        try:
            # Request one more, as the post itself might be returned
            similar_results = await vector_manager.search_similar(
                post_vector,
                k=limit + 5  # Request more to compensate for filtering
            )
            logging.info(f"Found {len(similar_results)} similar results for {vector_doc_id}.")
        except Exception as e:
            logging.error(f"Error searching for similar vectors for {vector_doc_id}: {e}", exc_info=True)
            return []

        similar_posts = []
        for result in similar_results:
            similar_post_id = result.get('doc_id', '').replace('post:', '')
            if not similar_post_id or similar_post_id == post_id:
                continue

            # Check the similarity threshold
            score = result.get('score', 1.0)
            if score > settings.SIMILARITY_THRESHOLD:
                continue

            post = await Post.get_by_id(similar_post_id)
            # As per customer requirement, remove status filtering
            if post:
                similar_posts.append(post)

            if len(similar_posts) >= limit:
                break

        logging.info(f"Returning {len(similar_posts)} similar posts for {post_id}.")
        return similar_posts


    @staticmethod
    async def search_by_text(query: str, limit: int = 20, offset: int = 0) -> List['PostResponse']:
        """Full-text search for posts using RediSearch (simplified version)."""

        # Escape special characters and add an asterisk for prefix search
        # New, simplified syntax: search for the word in ANY text field and filter by tag
        escaped_query = query.replace("-", "\\-")
        redis_query = f"{escaped_query}~2"

        try:
            # Perform the search, not returning the content of the fields for efficiency
            search_results = await db.redis_client.execute_command(
                "FT.SEARCH",
                settings.VECTOR_INDEX_NAME,
                redis_query,
                "LIMIT", offset, limit,
                "NOCONTENT"
            )
        except Exception as e:
            # In case of an error (e.g., the index is not created), return an empty list
            import logging
            logging.error(f"Full-text search error: {e}", exc_info=True)
            return []

        # Result: [number_of_results, doc_id_1, doc_id_2, ...]
        if not search_results or search_results[0] == 0:
            return []

        # Extract post IDs from the result. Skip the first element (the count).
        # Keys are stored as bytes, they need to be decoded.
        # Documents are stored with the prefix 'post:', which needs to be removed.
        post_ids = [
            doc_id.replace("vector:post:", "")
            for doc_id in search_results[1:] if isinstance(doc_id, str)
        ]

        # Get the full post data by the found IDs
        posts = []
        for post_id in post_ids:
            post = await Post.get_by_id(post_id)
            # Additional check in case of desynchronization between the index and the main DB
            if post and post.status == PostStatus.PUBLISHED:
                posts.append(post)

        return posts

    @staticmethod
    async def recreate_search_index():
        """
        Recreates the search index and re-indexes all published posts.
        """
        import logging
        from services.redis_manager import vector_manager
        from services.vector_classifier import vector_classifier

        logging.info("Starting search index recreation...")

        # 1. Create the index (the create_index method itself checks for existence)
        await vector_manager.create_index()
        logging.info("Index schema successfully created/verified.")

        # 2. Get all published posts
        all_post_ids = await db.zrevrange("posts:all", 0, -1)
        logging.info(f"Found {len(all_post_ids)} posts for possible re-indexing.")

        # 3. Iterate over and index each post
        indexed_count = 0
        for post_id_bytes in all_post_ids:
            post_id = post_id_bytes
            post = await Post.get_by_id(post_id)

            if post and post.status == PostStatus.PUBLISHED:
                try:
                    # Make sure the classifier is initialized
                    if not vector_classifier.is_initialized:
                        await vector_classifier.initialize()

                    post_vector = vector_classifier.create_vector(post.title, post.content, post.tags)

                    # Add to the index
                    vector_doc_id = f"post:{post.id}"
                    await vector_manager.add_vector(
                        doc_id=vector_doc_id,
                        vector=post_vector,
                        title=post.title,
                        content=post.content
                    )
                    indexed_count += 1
                except Exception as e:
                    logging.error(f"Error re-indexing post {post.id}: {e}")

        logging.info(f"Re-indexing complete. Successfully indexed {indexed_count} posts.")

    @staticmethod
    async def hard_delete(post_id: str) -> bool:
        """
        Permanently deletes a post and all its related data.
        This is a hard delete and is irreversible.
        """
        import logging
        from models.comment import Comment
        from services.redis_manager import vector_manager

        # 1. Get post data to know author_id and category_id
        post_data = await db.hgetall(f"post:{post_id}")
        if not post_data:
            logging.warning(f"Attempted to hard delete non-existent post {post_id}")
            return False

        author_id = post_data.get("author_id")
        category_id = post_data.get("category_id")

        # 2. Delete all comments associated with the post
        comment_ids_bytes = await db.zrevrange(f"post:{post_id}:comments", 0, -1)
        comment_ids = [cid.decode('utf-8') for cid in comment_ids_bytes]
        for comment_id in comment_ids:
            await Comment.hard_delete(comment_id)
        
        logging.info(f"Deleted {len(comment_ids)} comments for post {post_id}")

        # 3. Use a transaction for atomicity
        async with db.redis_client.pipeline(transaction=True) as pipe:
            # Delete the main post hash
            pipe.delete(f"post:{post_id}")

            # Remove the post ID from all sorted sets
            pipe.zrem("posts:all", post_id)
            if category_id:
                pipe.zrem(f"posts:category:{category_id}", post_id)
            if author_id:
                pipe.zrem(f"posts:author:{author_id}", post_id)

            # Remove from the spam set if it was there
            pipe.srem("posts:spam", post_id)
            
            # Decrement total posts counter
            pipe.decr("total_posts")
            
            # Decrement user's post count
            if author_id:
                pipe.hincrby(f"user:{author_id}:stats", "post_count", -1)

            # Execute the transaction
            await pipe.execute()

        # 4. Update the post count in the category (outside the transaction)
        if category_id:
            from models.category import Category
            await Category.update_post_count(category_id, -1)

        # 5. Delete the vector from the search index (outside the transaction)
        await vector_manager.delete_vector(f"post:{post_id}")

        logging.info(f"Post {post_id} was permanently deleted.")

        return True

# This is needed to update the links in the Pydantic models after all classes have been defined
PostResponse.model_rebuild()

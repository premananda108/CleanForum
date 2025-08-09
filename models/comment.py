"""
Comment model
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum
from models.database import db

class CommentStatus(str, Enum):
    """Comment status"""
    PUBLISHED = "published"
    MODERATED = "moderated"
    SPAM = "spam"
    DELETED = "deleted"

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    post_id: str

class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentResponse(BaseModel):
    id: str
    content: str
    post_id: str
    author_id: str
    author_username: str = ""
    created_at: datetime
    updated_at: datetime
    vote_score: int = 0
    is_spam: bool = False
    spam_score: float = 0.0
    status: CommentStatus

class Comment:
    """Class for working with comments"""

    @staticmethod
    async def create(comment_data: CommentCreate, author_id: str) -> Optional[str]:
        """
        Create a new comment with immediate spam analysis.
        If the comment is identified as spam, it is not saved and None is returned.
        """
        comment_id = str(uuid.uuid4())
        now = datetime.now()

        # Perform analysis to get a spam score
        from services.vector_classifier import vector_classifier
        analysis_results = await vector_classifier.analyze_comment(
            comment_id, comment_data.content, author_id
        )

        is_spam = analysis_results.get("is_spam", False)

        # If the comment is spam, do not save it
        if is_spam:
            import logging
            logging.warning(f"Comment from {author_id} on post {comment_data.post_id} was identified as spam and will not be saved.")
            return None

        spam_score = analysis_results.get("spam_score", 0.0)
        status = CommentStatus.PUBLISHED

        comment_info = {
            "id": comment_id,
            "content": comment_data.content,
            "post_id": comment_data.post_id,
            "author_id": author_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "vote_score": 0,
            "is_spam": str(is_spam), # will always be False
            "spam_score": spam_score,
            "status": status.value
        }

        # Save the comment and its analysis in a single transaction
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"comment:{comment_id}", mapping=comment_info)
            timestamp = now.timestamp()
            pipe.zadd("comments:all", {comment_id: timestamp})
            pipe.zadd(f"comments:post:{comment_data.post_id}", {comment_id: timestamp})
            pipe.zadd(f"comments:author:{author_id}", {comment_id: timestamp})
            # Update the comment counter in the post
            pipe.hincrby(f"post:{comment_data.post_id}", "comment_count", 1)
            await pipe.execute()

        return comment_id

    @staticmethod
    async def get_by_id(comment_id: str) -> Optional[CommentResponse]:
        """Get a comment by ID"""
        comment_data = await db.hgetall(f"comment:{comment_id}")
        if not comment_data:
            return None

        from models.user import User
        author = await User.get_by_id(comment_data["author_id"])

        return CommentResponse(
            id=comment_data["id"],
            content=comment_data["content"],
            post_id=comment_data["post_id"],
            author_id=comment_data["author_id"],
            author_username=author.username if author else "Unknown",
            created_at=datetime.fromisoformat(comment_data["created_at"]),
            updated_at=datetime.fromisoformat(comment_data["updated_at"]),
            vote_score=int(comment_data.get("vote_score", 0)),
            is_spam=comment_data.get("is_spam", "False") == "True",
            spam_score=float(comment_data.get("spam_score", 0.0)),
            status=CommentStatus(comment_data.get("status", "published"))
        )

    @staticmethod
    async def get_by_post(post_id: str, limit: int = 50, offset: int = 0) -> List[CommentResponse]:
        """Get comments for a post (published only)"""
        comment_ids = await db.zrange(f"comments:post:{post_id}", offset, offset + limit - 1)

        comments = []
        for comment_id in comment_ids:
            comment = await Comment.get_by_id(comment_id)
            if comment and comment.status == CommentStatus.PUBLISHED:
                comments.append(comment)

        return comments

    @staticmethod
    async def get_all_for_moderation(limit: int = 50, offset: int = 0, status: Optional[str] = None) -> (List[CommentResponse], int):
        """Get all comments for moderation, with filtering and pagination."""
        all_comment_ids = await db.zrevrange("comments:all", 0, -1)

        # This is inefficient, but necessary for filtering without complex indexing
        # A better approach would be to use separate sorted sets for different statuses
        filtered_ids = []
        if status:
            for comment_id in all_comment_ids:
                comment_status = await db.hget(f"comment:{comment_id}", "status")
                if comment_status == status:
                    filtered_ids.append(comment_id)
        else:
            filtered_ids = all_comment_ids

        total_count = len(filtered_ids)
        paginated_ids = filtered_ids[offset : offset + limit]

        comments = []
        for comment_id in paginated_ids:
            comment = await Comment.get_by_id(comment_id)
            if comment:
                comments.append(comment)

        return comments, total_count

    @staticmethod
    async def update(comment_id: str, comment_data: CommentUpdate) -> bool:
        """Update a comment"""
        update_fields = {
            "content": comment_data.content,
            "updated_at": datetime.now().isoformat(),
            "status": CommentStatus.PUBLISHED.value, # Reset status on update
            "is_spam": str(False),
            "spam_score": 0.0
        }
        await db.hset(f"comment:{comment_id}", mapping=update_fields)
        # Remove from spam list if it was there
        await db.srem("comments:spam", comment_id)
        return True

    @staticmethod
    async def mark_as_spam(comment_id: str, spam_score: float, is_spam: bool):
        """Mark a comment as spam and update its status."""
        status = CommentStatus.SPAM if is_spam else CommentStatus.PUBLISHED
        await db.hset(f"comment:{comment_id}", mapping={
            "is_spam": str(is_spam),
            "spam_score": spam_score,
            "status": status.value
        })

        if is_spam:
            await db.sadd("comments:spam", comment_id)
        else:
            await db.srem("comments:spam", comment_id)

    @staticmethod
    async def count_all() -> int:
        """Count the total number of comments."""
        return await db.zcard("comments:all")

    @staticmethod
    async def count_spam() -> int:
        """Count the number of spam comments."""
        return await db.scard("comments:spam")

    @staticmethod
    async def hard_delete(comment_id: str) -> bool:
        """
        Permanently deletes a comment.
        This is a hard delete and is irreversible.
        """
        import logging
        from services.redis_manager import vector_manager

        # 1. Get comment data to know post_id and author_id
        comment_data = await db.hgetall(f"comment:{comment_id}")
        if not comment_data:
            logging.warning(f"Attempted to hard delete non-existent comment {comment_id}")
            return False

        post_id = comment_data.get("post_id")
        author_id = comment_data.get("author_id")

        # 2. Use a transaction for atomicity
        async with db.redis_client.pipeline(transaction=True) as pipe:
            # Delete the main comment hash
            pipe.delete(f"comment:{comment_id}")

            # Remove the comment ID from all sorted sets
            pipe.zrem("comments:all", comment_id)
            if post_id:
                pipe.zrem(f"comments:post:{post_id}", comment_id)
            if author_id:
                pipe.zrem(f"comments:author:{author_id}", comment_id)

            # Remove from the spam set if it was there
            pipe.srem("comments:spam", comment_id)

            # Decrement post's comment count
            if post_id:
                pipe.hincrby(f"post:{post_id}", "comment_count", -1)
            
            # Decrement user's comment count
            if author_id:
                pipe.hincrby(f"user:{author_id}:stats", "comment_count", -1)

            # Execute the transaction
            await pipe.execute()

        # 3. Delete the vector from the search index (outside the transaction)
        await vector_manager.delete_vector(f"comment:{comment_id}")

        logging.info(f"Comment {comment_id} was permanently deleted.")

        return True

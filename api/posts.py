"""
API routes for working with posts
"""
from fastapi import APIRouter, HTTPException, Depends, Query
import logging
from typing import List, Optional
from models.post import Post, PostCreate, PostUpdate, PostResponse, PostStatus
from models.category import Category
from models.user import User, UserRole
from services.vector_classifier import vector_classifier
import uuid

router = APIRouter()

# Temporary function to get the current user
async def get_current_user_id() -> str:
    """Temporary stub to get the user ID. Always returns the same user."""
    # In a real application, this would be JWT authorization
    return "user_demo_12345"

@router.post("/posts", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    current_user: str = Depends(get_current_user_id)
):
    """Create a new post"""
    logging.info(f"Attempting to create a post from user {current_user}")
    logging.debug(f"Post data: {post_data.model_dump_json(exclude={'content'})[:500]}")

    # Check if the category exists
    category = await Category.get_by_id(post_data.category_id)
    if not category:
        logging.warning(f"Category {post_data.category_id} not found.")
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        post_id = await Post.create(post_data, current_user)
        # post_id can no longer be None, the check has been removed.
        # Spam posts are now saved with the 'spam' status.
        logging.info(f"Post {post_id} saved to the DB successfully.")

    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error creating post in the DB: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error creating post")

    # Get the created post
    post = await Post.get_by_id(post_id, increment_views=False)
    if not post:
        logging.error(f"Could not retrieve post {post_id} after creation.")
        raise HTTPException(status_code=500, detail="Error retrieving post after creation")

    # Update the post count in the category
    await Category.update_post_count(post_data.category_id, 1)
    logging.info(f"Post count for category {post_data.category_id} updated.")

    logging.info(f"Post {post_id} processed and returned to the client successfully.")
    return post

@router.get("/posts", response_model=List[PostResponse])
async def get_posts(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    category_id: Optional[str] = None
):
    """Get a list of posts"""

    if category_id:
        posts = await Post.get_by_category(category_id, limit, offset)
    else:
        posts = await Post.get_all(limit, offset)

    return posts

@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: str, increment_views: bool = True):
    """Get a post by ID"""

    post = await Post.get_by_id(post_id, increment_views)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Get similar posts
    similar_posts = await Post.get_similar_posts(post_id)
    post.similar_posts = similar_posts

    return post

@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    post_data: PostUpdate,
    current_user: str = Depends(get_current_user_id)
):
    """Update a post"""

    # Check if the post exists
    existing_post = await Post.get_by_id(post_id)
    if not existing_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check editing permissions
    if existing_post.author_id != current_user:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this post")

    # Update the post
    success = await Post.update(post_id, post_data)
    if not success:
        raise HTTPException(status_code=500, detail="Error updating post")

    # If the content or title was updated, re-analyze for spam
    if post_data.content is not None or post_data.title is not None or post_data.tags is not None:
        updated_post = await Post.get_by_id(post_id, increment_views=False)
        if updated_post:
            # Now content is always Markdown
            text_for_analysis = updated_post.content
            
            analysis_results = await vector_classifier.analyze_with_vectors(
                post_id, 
                updated_post.title, 
                text_for_analysis, 
                updated_post.tags, 
                updated_post.author_id
            )

            if analysis_results.get("is_spam", False):
                # If the post becomes spam after editing, it is deleted
                await Post.mark_as_deleted(post_id)
                raise HTTPException(
                    status_code=422,
                    detail="Your post was identified as spam after editing and has been deleted."
                )

    # Return the updated post
    post = await Post.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found after update")
    
    return post

@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Delete a post. Only available to the author of the post.
    """
    logging.info(f"Attempting to delete post {post_id} by user {current_user_id}")

    # 1. Check if the post exists
    existing_post = await Post.get_by_id(post_id, increment_views=False)
    if not existing_post:
        logging.warning(f"Attempt to delete non-existent post {post_id}")
        raise HTTPException(status_code=404, detail="Post not found")

    # 2. Check deletion permissions
    if existing_post.author_id != current_user_id:
        logging.error(f"User {current_user_id} tried to delete someone else's post {post_id} (author: {existing_post.author_id})")
        raise HTTPException(status_code=403, detail="You do not have permission to delete this post")

    # 3. Mark the post as deleted
    success = await Post.mark_as_deleted(post_id)
    if not success:
        # This error can occur if the post was deleted between get_by_id and mark_as_deleted
        logging.error(f"An error occurred while trying to mark post {post_id} as deleted")
        raise HTTPException(status_code=500, detail="Error deleting post")

    logging.info(f"Post {post_id} successfully marked as deleted by user {current_user_id}")
    
    # Return 204 No Content, as is customary for DELETE requests
    return

@router.get("/posts/{post_id}/spam-analysis")
async def get_spam_analysis(post_id: str):
    """Get spam analysis results for a post"""

    from models.database import db

    # Get spam analysis
    analysis_data = await db.hgetall(f"vector_analysis:{post_id}")
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Spam analysis not found")

    return {
        "post_id": analysis_data.get("post_id"),
        "spam_score": float(analysis_data.get("spam_score", 0)),
        "is_spam": analysis_data.get("is_spam") == "True",
        "heuristic_score": float(analysis_data.get("heuristic_score", 0)),
        "vector_score": float(analysis_data.get("vector_score", 0)),
        "vector_prediction": analysis_data.get("vector_prediction"),
        "vector_confidence": float(analysis_data.get("vector_confidence", 0)),
        "similar_posts_count": int(analysis_data.get("similar_posts_count", 0)),
        "analyzed_at": analysis_data.get("analyzed_at")
    }

#!/usr/bin/env python3
"""
Script for initially populating the database from JSON files.
Creates test users, categories, and posts WITHOUT spam checking.
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random
import os

from models.database import db
from models.post import Post, PostCreate, PostStatus
from models.user import User, UserCreate, UserRole
from models.category import Category, CategoryCreate
from services.vector_classifier import vector_classifier
from services.redis_manager import vector_manager
from config import settings

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Test users to create
TEST_USERS = [
    {
        "username": "alice_blogger",
        "email": "alice@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "bob_writer",
        "email": "bob@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "charlie_spam",
        "email": "charlie@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "diana_expert",
        "email": "diana@example.com",
        "password": "password123",
        "role": UserRole.USER
    },
    {
        "username": "moderator_1",
        "email": "mod1@example.com",
        "password": "password123",
        "role": UserRole.MODERATOR
    }
]

# Categories to create
TEST_CATEGORIES = [
    {
        "name": "General",
        "description": "Discussions on any topic"
    },
    {
        "name": "Technology",
        "description": "All about high-tech"
    },
    {
        "name": "Finance",
        "description": "Discussion of financial issues"
    },
    {
        "name": "Health",
        "description": "Health and medicine topics"
    },
    {
        "name": "Off-topic",
        "description": "For non-serious discussions"
    }
]


class DatabasePopulator:
    """Class for populating the database with test data"""

    def __init__(self):
        self.created_users = []
        self.created_categories = []

    async def populate_all(self):
        """Main method to populate the entire database"""
        logging.info("🚀 Starting database population...")

        # Connect to the DB
        await db.connect()
        await vector_classifier.initialize()

        try:
            # Create users
            await self.create_users()

            # Create categories
            await self.create_categories()

            # Create posts from JSON files
            await self.create_posts_from_json_files()

            # Print statistics
            await self.print_statistics()

            # Analyze created posts
            await self._analyze_created_posts()

            logging.info("✅ Database population completed successfully!")

        except Exception as e:
            logging.error(f"❌ Error while populating the database: {e}", exc_info=True)
        finally:
            await db.disconnect()

    async def create_users(self):
        """Creating test users"""
        logging.info("👥 Creating test users...")

        for user_data in TEST_USERS:
            try:
                # Check if user exists
                existing_user = await User.get_by_username(user_data["username"])
                if existing_user:
                    logging.info(f"User {user_data['username']} already exists, skipping")
                    self.created_users.append(existing_user.id)
                    continue

                user_create = UserCreate(
                    username=user_data["username"],
                    email=user_data["email"],
                    password=user_data["password"]
                )

                user_id = await User.create(user_create, user_data["role"])
                self.created_users.append(user_id)

                # Setting a random creation date (from 30 to 365 days ago)
                days_ago = random.randint(30, 365)
                creation_date = datetime.now() - timedelta(days=days_ago)
                await db.hset(f"user:{user_id}", mapping={"created_at": creation_date.isoformat()})

                logging.info(f"✓ Created user: {user_data['username']} (ID: {user_id})")

            except Exception as e:
                logging.error(f"Error creating user {user_data['username']}: {e}")

    async def create_categories(self):
        """Creating test categories"""
        logging.info("📁 Creating categories...")

        for cat_data in TEST_CATEGORIES:
            try:
                # Check if category exists
                existing_categories = await Category.get_all()
                existing_names = [cat.name for cat in existing_categories]

                if cat_data["name"] in existing_names:
                    logging.info(f"Category '{cat_data['name']}' already exists, skipping")
                    # Finding the ID of the existing category
                    for cat in existing_categories:
                        if cat.name == cat_data["name"]:
                            self.created_categories.append(cat.id)
                            break
                    continue

                category_create = CategoryCreate(
                    name=cat_data["name"],
                    description=cat_data["description"]
                )

                category_id = await Category.create(category_create)
                self.created_categories.append(category_id)

                logging.info(f"✓ Created category: {cat_data['name']} (ID: {category_id})")

            except Exception as e:
                logging.error(f"Error creating category {cat_data['name']}: {e}")

    async def create_posts_from_json_files(self):
        """Creating posts from default_spam_dataset.json and default_dataset.json files"""
        logging.info("📝 Creating posts from JSON files...")

        datasets = ["default_spam_dataset.json", "default_dataset.json"]
        posts_created = 0
        spam_posts_created = 0
        legit_posts_created = 0

        for filename in datasets:
            if not os.path.exists(filename):
                logging.warning(f"Data file {filename} not found, skipping.")
                continue

            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                    if not content:
                        logging.warning(f"File {filename} is empty, skipping.")
                        continue
                    dataset = json.loads(content)
            except json.JSONDecodeError as e:
                logging.error(f"Error reading JSON file {filename}: {e}")
                continue

            if not dataset:
                logging.info(f"File {filename} contains no posts.")
                continue

            logging.info(f"Loading posts from {filename}...")
            for post_data in dataset:
                try:
                    if not self.created_users:
                        logging.error("No created users to assign as authors.")
                        return
                    author_id = random.choice(self.created_users)

                    # Determining category
                    category_name = post_data.get("category")
                    category_id = self.get_category_id_by_name(category_name)

                    if not category_id:
                        category_id = self.choose_category_by_tags(post_data.get("tags", []))

                    post_create = PostCreate(
                        title=post_data["title"],
                        content=post_data["content"],
                        category_id=category_id,
                        tags=post_data.get("tags", [])
                    )

                    is_spam = post_data.get("label") == "spam"

                    post_id = await self.create_post_without_spam_check(
                        post_create,
                        author_id,
                        is_spam=is_spam
                    )

                    if post_id:
                        posts_created += 1
                        if is_spam:
                            spam_posts_created += 1
                        else:
                            legit_posts_created += 1
                        logging.info(f"✓ Created post: {post_data['title'][:50]}... (ID: {post_id}, spam: {is_spam})")

                except Exception as e:
                    logging.error(
                        f"Error creating post '{post_data.get('title', 'Untitled')}' from file {filename}: {e}",
                        exc_info=True)

        logging.info(f"📊 Total posts created from files: {posts_created}")
        logging.info(f"    -> Legitimate: {legit_posts_created}")
        logging.info(f"    -> Spam: {spam_posts_created}")

    def get_category_id_by_name(self, name: str) -> str:
        """Returns a category ID by its name"""
        if not name:
            return ""
        # It is assumed that TEST_CATEGORIES and self.created_categories have the same order
        try:
            index = [cat['name'] for cat in TEST_CATEGORIES].index(name)
            if index < len(self.created_categories):
                return self.created_categories[index]
        except ValueError:
            return ""
        return ""

    def choose_category_by_tags(self, tags: List[str]) -> str:
        """Choosing a category based on post tags"""
        if not self.created_categories:
            return ""

        tech_tags = ["technology", "ai", "programming", "machine_learning", "camera", "photography"]
        health_tags = ["health", "nutrition", "diet", "weight_loss", "pills"]
        finance_tags = ["finance", "money", "earnings", "bitcoin", "cryptocurrency", "forex", "credit", "trading"]

        lower_tags = [tag.lower() for tag in tags]

        if any(tag in lower_tags for tag in tech_tags):
            return self.created_categories[1] if len(self.created_categories) > 1 else self.created_categories[0]
        elif any(tag in lower_tags for tag in finance_tags):
            return self.created_categories[2] if len(self.created_categories) > 2 else self.created_categories[0]
        elif any(tag in lower_tags for tag in health_tags):
            return self.created_categories[3] if len(self.created_categories) > 3 else self.created_categories[0]

        return random.choice([self.created_categories[0], self.created_categories[4]]) if len(
            self.created_categories) > 4 else self.created_categories[0]

    async def create_post_without_spam_check(self, post_data: PostCreate, author_id: str, is_spam: bool = False) -> str:
        """
        Creating a post WITHOUT spam checking (for populating with test data).
        Version updated to work with Markdown.
        """
        post_id = str(uuid.uuid4())
        now = datetime.now()

        # Content is already Markdown text
        text_content = post_data.content
        status = PostStatus.SPAM if is_spam else PostStatus.PUBLISHED

        post_info = {
            "id": post_id,
            "title": post_data.title,
            "content": text_content,  # Saving Markdown directly
            "category_id": post_data.category_id,
            "author_id": author_id,
            "tags": json.dumps(post_data.tags),
            "status": status.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "view_count": random.randint(10, 1000),
            "comment_count": random.randint(0, 50),
            "vote_score": random.randint(-5, 20),
            "is_spam": str(is_spam),
            "spam_score": 0.95 if is_spam else random.uniform(0.01, 0.2),
            "reading_time": Post.calculate_reading_time(text_content)
        }

        # Setting a random creation date for realism
        days_ago = random.randint(1, 30)
        random_date = datetime.now() - timedelta(days=days_ago)
        post_info["created_at"] = random_date.isoformat()
        post_info["updated_at"] = random_date.isoformat()

        # Saving to Redis
        async with db.redis_client.pipeline(transaction=True) as pipe:
            pipe.hset(f"post:{post_id}", mapping=post_info)
            timestamp = random_date.timestamp()
            pipe.zadd("posts:all", {post_id: timestamp})
            pipe.zadd(f"posts:author:{author_id}", {post_id: timestamp})
            pipe.zadd(f"posts:category:{post_data.category_id}", {post_id: timestamp})
            if is_spam:
                pipe.sadd("posts:spam", post_id)
            await pipe.execute()

        # Adding vector to the search index
        try:
            if not vector_classifier.is_initialized:
                await vector_classifier.initialize()

            post_vector = vector_classifier.create_vector(post_data.title, text_content, post_data.tags)

            await vector_manager.add_vector(
                doc_id=f"post:{post_id}",
                vector=post_vector,
                title=post_data.title,
                content=text_content
            )
        except Exception as e:
            logging.warning(f"Failed to add post {post_id} to the search index: {e}")

        # Updating counters
        await User.update_stats(author_id, post_count_delta=1)
        await Category.update_post_count(post_data.category_id, 1)

        return post_id

    async def print_statistics(self):
        """Output statistics of created data"""
        logging.info("📊 Statistics of created data:")
        total_users = len(self.created_users)
        logging.info(f"👥 Users: {total_users}")
        total_categories = len(self.created_categories)
        logging.info(f"📁 Categories: {total_categories}")
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()
        legitimate_posts = total_posts - spam_posts
        logging.info(f"📝 Total posts: {total_posts}")
        logging.info(f"🚫 Spam posts: {spam_posts}")
        logging.info(f"✅ Legitimate posts: {legitimate_posts}")
        try:
            index_info = await vector_manager.get_index_info()
            vector_count = index_info.get("num_docs", 0)
            logging.info(f"🔍 Vectors in search index: {vector_count}")
        except Exception as e:
            logging.warning(f"Failed to get vector index statistics: {e}")

    async def _analyze_created_posts(self):
        """Runs analysis on all posts that haven't been analyzed."""
        logging.info("🔬 Starting spam analysis for all created posts...")

        # Getting all posts that were created in this script run or already existed.
        # Since we don't know exactly which ones are new, we just iterate through all of them.
        # In a real system, this would be a more complex background process.
        all_post_ids = await db.zrevrange("posts:all", 0, -1)

        analyzed_count = 0
        skipped_count = 0

        for post_id in all_post_ids:
            try:
                # Checking if analysis already exists
                analysis_exists = await db.exists(f"vector_analysis:post:{post_id}")
                if not analysis_exists:
                    post = await Post.get_by_id(post_id)
                    if post:
                        await vector_classifier.analyze_with_vectors(
                            post.id, post.title, post.content, post.tags, post.author_id
                        )
                        analyzed_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logging.error(f"Error analyzing post {post_id}: {e}")

        logging.info(f"🔬 Analysis finished. Analyzed: {analyzed_count}, skipped (already existed): {skipped_count}")


async def main():
    """Main script function"""
    logging.info("🎯 Database population script")
    logging.info("=" * 50)
    populator = DatabasePopulator()
    await populator.populate_all()
    logging.info("=" * 50)
    logging.info("🏁 Script finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Script interrupted by user")
    except Exception as e:
        logging.error(f"❌ Critical error: {e}", exc_info=True)

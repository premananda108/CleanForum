#!/usr/bin/env python3
"""
Script for a quick check of the data created in the database.
"""
import asyncio
import logging
from models.database import db
from models.post import Post
from models.user import User
from models.category import Category
from services.redis_manager import vector_manager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def check_database():
    """Checks the database content"""
    logging.info("🔍 Checking database content")
    logging.info("=" * 50)
    
    await db.connect()
    
    try:
        # Check general statistics
        logging.info("📊 GENERAL STATISTICS:")
        
        # Number of keys in Redis
        keys_count = await db.redis_client.dbsize()
        logging.info(f"🗄️  Total keys in Redis: {keys_count}")
        
        # Post statistics
        total_posts = await Post.count_all()
        spam_posts = await Post.count_spam()
        published_posts = await Post.count_published()
        
        logging.info(f"📝 Total posts: {total_posts}")
        logging.info(f"✅ Published: {published_posts}")
        logging.info(f"🚫 Spam posts: {spam_posts}")
        
        # Check users
        logging.info("\n👥 USERS:")
        test_usernames = ["alice_blogger", "bob_writer", "charlie_spam", "diana_expert", "moderator_1"]
        
        for username in test_usernames:
            user = await User.get_by_username(username)
            if user:
                logging.info(f"✓ {username} (ID: {user.id}, role: {user.role.value}, posts: {user.post_count})")
            else:
                logging.warning(f"❌ {username} not found")
        
        # Check categories
        logging.info("\n📁 CATEGORIES:")
        categories = await Category.get_all()
        for category in categories:
            posts_in_category = len(await Post.get_by_category(category.id, limit=100))
            logging.info(f"✓ {category.name} (ID: {category.id}, posts: {posts_in_category})")
        
        # Check recent posts
        logging.info("\n📝 RECENT POSTS:")
        recent_posts = await Post.get_all(limit=5)
        for i, post in enumerate(recent_posts, 1):
            status_emoji = "🚫" if post.status.value == "spam" else "✅"
            logging.info(f"{i}. {status_emoji} '{post.title[:50]}...' (author: {post.author_username}, status: {post.status.value})")
        
        # Check vector index
        logging.info("\n🔍 VECTOR SEARCH INDEX:")
        try:
            await vector_manager.connect()
            index_info = await vector_manager.get_index_info()
            
            if index_info:
                logging.info(f"✓ Index exists: {vector_manager.index_name}")
                logging.info(f"📊 Vectors in index: {index_info.get('num_docs', 'N/A')}")
                logging.info(f"💾 Index size: {index_info.get('inverted_sz_mb', 'N/A')} MB")
            else:
                logging.warning("❌ Vector index not found")
                
        except Exception as e:
            logging.error(f"❌ Error checking vector index: {e}")
        
        # Test search
        logging.info("\n🔎 TESTING SEARCH:")
        try:
            search_results = await Post.search_by_text("money", limit=3)
            logging.info(f"Search for 'money': found {len(search_results)} results")
            for result in search_results:
                logging.info(f"  - '{result.title[:40]}...'")
        except Exception as e:
            logging.error(f"❌ Error during search test: {e}")
        
        logging.info("\n" + "=" * 50)
        logging.info("✅ Database check finished")
        
    except Exception as e:
        logging.error(f"❌ Error during database check: {e}", exc_info=True)
    finally:
        await db.disconnect()

async def main():
    """Main function"""
    await check_database()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Check interrupted by user")
    except Exception as e:
        logging.error(f"❌ Critical error: {e}", exc_info=True)
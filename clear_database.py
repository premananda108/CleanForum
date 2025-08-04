#!/usr/bin/env python3
"""
Script to clear the Redis database.
WARNING: Deletes ALL data from the database!
"""
import asyncio
import logging
from models.database import db
from services.redis_manager import vector_manager
from config import settings

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def clear_database():
    """Complete database cleanup"""
    logging.warning("🚨 WARNING: Starting a full database cleanup!")
    
    # Connect to Redis
    await db.connect()
    
    try:
        # Get stats before cleanup
        keys_count = await db.redis_client.dbsize()
        logging.info(f"📊 Number of keys in the database before cleanup: {keys_count}")
        
        # Drop the vector index
        try:
            await db.redis_client.execute_command("FT.DROPINDEX", settings.VECTOR_INDEX_NAME)
            logging.info("✓ Vector index dropped")
        except Exception as e:
            logging.info(f"Vector index not found or already deleted: {e}")
        
        # Clear the entire database
        await db.redis_client.flushdb()
        logging.info("✓ Database completely cleared")
        
        # Check the result
        keys_count_after = await db.redis_client.dbsize()
        logging.info(f"📊 Number of keys in the database after cleanup: {keys_count_after}")
        
        logging.info("✅ Database cleanup completed successfully!")
        
    except Exception as e:
        logging.error(f"❌ Error during database cleanup: {e}", exc_info=True)
    finally:
        await db.disconnect()

async def main():
    # Request confirmation
    confirmation = input("Are you sure you want to delete ALL data? Type 'YES' to confirm: ")

    """Main function"""
    logging.info("🗑️  Database cleanup script")
    logging.info("=" * 50)

    if confirmation == "YES":
        await clear_database()
    else:
        logging.info("❌ Operation cancelled by user")
    
    logging.info("=" * 50)
    logging.info("🏁 Script finished")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("❌ Script interrupted by user")
    except Exception as e:
        logging.error(f"❌ Critical error: {e}", exc_info=True)
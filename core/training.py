"""
Logic for training the spam classification model.
"""
import asyncio
import aiohttp
import json
import logging
import random
from typing import List, Dict, Tuple
from redis.asyncio import Redis

from models import DevToPost
from .classification import SpamClassifier, VECTOR_DIM, INDEX_NAME, INDEX_PREFIX
from db import create_redis_index

logger = logging.getLogger(__name__)

# --- Data Collection ---
class DevToDataCollector:
    """Fetches recent articles from the dev.to API for heuristic labeling."""
    BASE_URL = "https://dev.to/api"

    async def collect_articles(self, num_articles: int = 500) -> List[Dict]:
        """Collects a target number of articles."""
        all_articles = []
        per_page = 100
        num_pages = (num_articles + per_page - 1) // per_page
        
        logger.info(f"Starting data collection from dev.to, aiming for ~{num_articles} articles.")
        async with aiohttp.ClientSession() as session:
            for page in range(1, num_pages + 1):
                params = {'page': page, 'per_page': per_page}
                try:
                    async with session.get(f"{self.BASE_URL}/articles/latest", params=params) as response:
                        if response.status == 200:
                            articles = await response.json()
                            if not articles: break
                            all_articles.extend(articles)
                            logger.info(f"Fetched page {page}/{num_pages}, total articles: {len(all_articles)}")
                        else:
                            logger.error(f"Failed to fetch articles (page {page}): {response.status}")
                        await asyncio.sleep(0.5) # Basic rate limiting
                except Exception as e:
                    logger.error(f"Error fetching articles (page {page}): {e}")
        
        logger.info(f"Collected {len(all_articles)} articles from dev.to.")
        return all_articles

# --- Heuristic Labeling ---
class SpamLabelGenerator:
    """Generates spam labels for articles based on a set of heuristics."""
    SPAM_KEYWORDS = [
        'earn money', 'get rich', 'click here', 'free offer', 'buy now', 
        'limited time', 'guaranteed', 'crypto trading', 'investment opportunity'
    ]
    QUALITY_INDICATORS = [
        'tutorial', 'guide', 'how to', 'best practices', 'deep dive', 'introduction'
    ]

    def _calculate_spam_score(self, article: Dict) -> float:
        """Calculates a spam score."""
        score = 0.0
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        
        if any(keyword in title or keyword in description for keyword in self.SPAM_KEYWORDS):
            score += 0.5
        if any(indicator in title for indicator in self.QUALITY_INDICATORS):
            score -= 0.2
        if article.get('reading_time_minutes', 0) < 2 and article.get('public_reactions_count', 0) < 3:
            score += 0.3
        if not article.get('description'):
            score += 0.2
        if article.get('user', {}).get('followers_count', 0) < 5:
            score += 0.15
        return min(max(score, 0.0), 1.0)

    def generate_label(self, article: Dict) -> int:
        """Generates a final label (0 for legit, 1 for spam)."""
        return 1 if self._calculate_spam_score(article) > 0.5 else 0

# --- Model Training Orchestration ---
class ModelTrainer:
    def __init__(self, classifier: SpamClassifier):
        self.classifier = classifier
        self.redis_client = classifier.redis_client

    async def _store_training_vector(self, post_id: int, vector: bytes, label: int, title: str, url: str):
        """Saves a single vectorized post to Redis for training."""
        post_key = f"{INDEX_PREFIX}{post_id}"
        await self.redis_client.hset(post_key, mapping={
            "vector": vector,
            "label": "spam" if label == 1 else "not_spam",
            "title": title or "",
            "url": url or ""
        })

    async def _prepare_and_vectorize_data(self, data: List[Tuple[Dict, int]]) -> List[Tuple]:
        """Converts raw data into vectorized format for storage."""
        vectorized_data = []
        for item, label in data:
            try:
                post = DevToPost(**item)
                vector, _ = await self.classifier._vectorize_post(post)
                vectorized_data.append((post.id, vector.tobytes(), label, post.title, post.url))
            except Exception as e:
                logger.error(f"Skipping invalid article during vectorization (ID: {item.get('id')}): {e}")
        return vectorized_data

    async def run_training_pipeline(self) -> Dict:
        """
        Executes the full training pipeline: data collection, labeling, vectorizing, and storing.
        """
        logger.info("Starting training pipeline...")
        
        # 1. Ensure Redis index exists
        await create_redis_index(self.redis_client, INDEX_NAME, VECTOR_DIM, INDEX_PREFIX)

        # 2. Gather data from all sources
        # Source A: Local high-quality spam dataset
        base_spam_data = []
        try:
            with open('spam_dataset.json', 'r', encoding='utf-8') as f:
                base_spam_data = [(item, 1) for item in json.load(f)]
            logger.info(f"Loaded {len(base_spam_data)} articles from local spam dataset.")
        except FileNotFoundError:
            logger.warning("spam_dataset.json not found. Training will proceed without it.")

        # Source B: Live data from dev.to with heuristic labels
        collector = DevToDataCollector()
        label_generator = SpamLabelGenerator()
        live_articles = await collector.collect_articles(num_articles=300)
        heuristic_data = [(article, label_generator.generate_label(article)) for article in live_articles]
        logger.info(f"Collected and labeled {len(heuristic_data)} articles from dev.to.")

        # 3. Combine data (local dataset takes priority)
        combined_data = {item['id']: (item, label) for item, label in heuristic_data}
        combined_data.update({item['id']: (item, label) for item, label in base_spam_data})
        
        final_training_data = list(combined_data.values())
        if not final_training_data:
            logger.error("No training data available. Aborting.")
            return {"status": "failed", "reason": "No data"}

        logger.info(f"Total unique samples for training: {len(final_training_data)}")

        # 4. Vectorize and store in Redis
        vectorized_samples = await self._prepare_and_vectorize_data(final_training_data)
        
        logger.info(f"Storing {len(vectorized_samples)} vectors in Redis...")
        tasks = [self._store_training_vector(*sample) for sample in vectorized_samples]
        await asyncio.gather(*tasks)
        
        logger.info("Training pipeline completed successfully!")
        
        # 5. (Optional) Evaluation step can be added here if there's a separate test set
        
        return {
            "status": "success",
            "total_samples_processed": len(final_training_data),
            "vectors_stored": len(vectorized_samples)
        }
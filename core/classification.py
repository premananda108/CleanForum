"""
Core logic for spam classification.
"""
import logging
import re
import numpy as np
from sentence_transformers import SentenceTransformer
import asyncio
import aiohttp
from collections import Counter
from typing import List, Optional, Dict, Any, Tuple
from redis.asyncio import Redis

from models import DevToPost, SimilarPostInfo

# --- Globals ---
logger = logging.getLogger(__name__)
VECTOR_DIM = 384 + 3  # 384 from model, 3 from numeric features
INDEX_NAME = "spam_vectors"
INDEX_PREFIX = "post_vector:"

# --- Singleton for SentenceTransformer Model ---
class ModelSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logger.info("Loading SentenceTransformer model for the first time...")
            cls._instance = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("SentenceTransformer model loaded.")
        return cls._instance

# --- Main Classification Logic ---
class SpamClassifier:
    def __init__(self, redis_client: Redis, k: int = 9):
        self.redis_client = redis_client
        self.model = ModelSingleton.get_instance()
        self.k = k

    def _preprocess_text(self, text: Optional[str]) -> str:
        """Cleans up text for processing."""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'http[s]?://\S+', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.lower().strip()

    def _get_heuristic_spam_indicators(self, features: Dict[str, Any]) -> List[str]:
        """Determines spam indicators based on simple rules."""
        indicators = []
        if features.get('reading_time', 0) < 2 and features.get('reactions_count', 0) < 5:
            indicators.append("Short post with low engagement")
        
        spam_words = ['earn money', 'get rich', 'click here', 'free offer', 'buy now', 'limited time']
        title_lower = features.get('title', '').lower()
        if any(word in title_lower for word in spam_words):
            indicators.append("Contains spam keywords")
        
        if not features.get('description'):
            indicators.append("Missing description")
        
        if len(features.get('tags', [])) > 10:
            indicators.append("Too many tags")
            
        if features.get('user_followers', -1) < 10 and features.get('user_followers') != -1:
            indicators.append(f"Low follower count ({features['user_followers']})")
            
        return indicators

    async def _vectorize_post(self, post: DevToPost) -> tuple[np.ndarray, Dict[str, Any]]:
        """Creates a vector from a post's features."""
        features = {
            'title': self._preprocess_text(post.title),
            'description': self._preprocess_text(post.description),
            'tags': post.tag_list,
            'reading_time': post.reading_time_minutes,
            'reactions_count': post.public_reactions_count,
            'comments_count': post.comments_count,
            'user_followers': -1,
            'user_id': post.user.get('id') if post.user else None
        }

        # --- Feature Enrichment (Example: fetching user followers) ---
        user_id = features.get('user_id')
        if user_id:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://dev.to/api/users/{user_id}") as response:
                        if response.status == 200:
                            user_data = await response.json()
                            features['user_followers'] = user_data.get('followers_count', 0)
            except Exception as e:
                logger.warning(f"Could not fetch user data for user {user_id}: {e}")

        # --- Vector Creation ---
        combined_text = f"{features['title']} {features['description']}"
        
        loop = asyncio.get_event_loop()
        text_vector = await loop.run_in_executor(None, self.model.encode, combined_text)
        
        numeric_features = np.array([
            features['reading_time'],
            features['user_followers'] if features['user_followers'] != -1 else 0,
            len(features['tags'])
        ], dtype=np.float32)
        
        # Normalize numeric features to prevent them from overpowering the text vector
        norm = np.linalg.norm(numeric_features)
        if norm > 0:
            numeric_features = numeric_features / norm
        
        final_vector = np.concatenate([text_vector, numeric_features])
        return final_vector.astype(np.float32), features

    async def _find_similar_posts_in_redis(self, query_vector: np.ndarray) -> List[Dict[str, Any]]:
        """Finds similar posts in Redis using vector search."""
        if not self.redis_client:
            return []
        try:
            # Correctly build the query using the Query class
            from redis.commands.search.query import Query
            
            q = (
                Query("*=>[KNN $k @vector $blob AS score]")
                .sort_by("score")
                .return_fields("id", "score", "title", "url", "label")
                .dialect(2)
            )
            
            query_params = {"k": self.k, "blob": query_vector.tobytes()}
            
            results = await self.redis_client.ft(INDEX_NAME).search(q, query_params)
            
            return [
                {
                    "post_id": doc.id.split(':')[-1],
                    "score": 1 - float(doc.score),  # Convert cosine distance to similarity
                    "title": doc.title,
                    "url": doc.url,
                    "label": doc.label
                } for doc in results.docs
            ]
        except Exception as e:
            logger.error(f"Redis search failed: {e}")
            return []

    async def classify(self, post: DevToPost) -> Tuple[bool, float, List[str], List[SimilarPostInfo]]:
        """
        Classifies a post as spam or not.
        Returns: (is_spam, confidence, reasoning, similar_posts_info)
        """
        query_vector, features = await self._vectorize_post(post)
        similar_posts = await self._find_similar_posts_in_redis(query_vector)
        
        # --- Decision Logic ---
        # 1. Vector-based classification (if similar posts are found)
        if similar_posts:
            labels = [p['label'] for p in similar_posts]
            label_counts = Counter(labels)
            
            if not label_counts:
                 # This case should ideally not be hit if similar_posts is not empty,
                 # but as a safeguard, we fall through to the cautious blocking below.
                 pass
            else:
                predicted_label_str, count = label_counts.most_common(1)[0]
                is_spam = (predicted_label_str == "spam")
                confidence = count / len(labels)
                
                reasoning = [f"Similar to {count} known '{predicted_label_str}' posts (via vector search)."]
                reasoning.extend(self._get_heuristic_spam_indicators(features))
                
                similar_posts_info = [SimilarPostInfo(**p) for p in similar_posts]
                return is_spam, confidence, reasoning, similar_posts_info

        # 2. Cautious blocking if no similar posts are found
        spam_indicators = self._get_heuristic_spam_indicators(features)
        is_spam = True
        confidence = 0.99  # High confidence because we are being cautious
        reasoning = ["Post is too dissimilar from any known content.", "Blocked as a precaution."]
        reasoning.extend(spam_indicators)
        return is_spam, confidence, reasoning, []
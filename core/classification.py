"""
Core logic for spam classification, based on the proven solution from /samples.
"""
import logging
import re
import numpy as np
from sentence_transformers import SentenceTransformer
import asyncio
from redis.asyncio import Redis
from collections import Counter
from typing import List, Optional, Dict, Any, Tuple
from redis.commands.search.query import Query

from models import DevToPost, SimilarPostInfo

# --- Globals ---
logger = logging.getLogger(__name__)
VECTOR_DIM = 384 + 3
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
        self.index_name = INDEX_NAME

    def _preprocess_text(self, text: Optional[str]) -> str:
        if not text: return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'http[s]?://\S+', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.lower().strip()

    def _get_heuristic_spam_indicators(self, features: Dict[str, Any]) -> List[str]:
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

        # Vector Creation
        combined_text = f"{features['title']} {features['description']}"
        
        loop = asyncio.get_event_loop()
        text_vector = await loop.run_in_executor(None, self.model.encode, combined_text)
        
        numeric_features = np.array([
            features['reading_time'],
            features['user_followers'] if features['user_followers'] != -1 else 0,
            len(features['tags'])
        ], dtype=np.float32)
        
        norm = np.linalg.norm(numeric_features)
        if norm > 0:
            numeric_features = numeric_features / norm
        
        final_vector = np.concatenate([text_vector, numeric_features])
        return final_vector.astype(np.float32), features

    async def _find_similar_posts_in_redis(self, query_vector: np.ndarray) -> List[Dict[str, Any]]:
        if not self.redis_client:
            return []
        try:
            # This is the proven method from the samples
            query = (
                f"*=>[KNN {self.k} @vector $blob AS score]"
            )
            results = await self.redis_client.execute_command(
                "FT.SEARCH", self.index_name, query, 
                "PARAMS", "2", "blob", query_vector.tobytes(), 
                "DIALECT", "2", 
                "RETURN", "5", "score", "title", "url", "label", "id"
            )
            
            similar_posts = []
            # Response: [count, doc1_id, [fields1], doc2_id, [fields2], ...]
            for i in range(1, len(results), 2):
                doc_id = results[i]
                fields = results[i+1]
                fields_dict = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
                
                similar_posts.append({
                    "post_id": doc_id.split(':')[-1],
                    "score": 1 - float(fields_dict.get('score', 1.0)),
                    "title": fields_dict.get('title', 'No Title'),
                    "url": fields_dict.get('url', ''),
                    "label": fields_dict.get('label', 'unknown')
                })
            return similar_posts
            
        except Exception as e:
            # If the index doesn't exist, Redis throws an error. We catch it here.
            logger.error(f"Redis search failed. This is expected if the index doesn't exist yet. Error: {e}")
            return []

    async def classify(self, post: DevToPost) -> Tuple[bool, float, List[str], List[SimilarPostInfo]]:
        query_vector, features = await self._vectorize_post(post)
        similar_posts = await self._find_similar_posts_in_redis(query_vector)
        
        if similar_posts:
            labels = [p['label'] for p in similar_posts if p['label'] != 'unknown']
            if labels:
                label_counts = Counter(labels)
                predicted_label_str, count = label_counts.most_common(1)[0]
                is_spam = (predicted_label_str == "spam")
                confidence = count / len(labels)
                
                reasoning = [f"Similar to {count} known '{predicted_label_str}' posts (via vector search)."]
                reasoning.extend(self._get_heuristic_spam_indicators(features))
                
                similar_posts_info = [SimilarPostInfo(**p) for p in similar_posts]
                return is_spam, confidence, reasoning, similar_posts_info

        # Fallback if no similar posts with known labels are found
        spam_indicators = self._get_heuristic_spam_indicators(features)

        # If no similar posts are found, rely on heuristics. Default to NOT SPAM.
        if "Contains spam keywords" in spam_indicators:
            is_spam = True
            confidence = 0.80
            reasoning = ["Classified as spam based on keywords (no similar posts found)."]
            reasoning.extend(spam_indicators)
        else:
            is_spam = False
            confidence = 0.95
            reasoning = ["Allowed: No similar posts found and no strong spam indicators."]

        return is_spam, confidence, reasoning, []

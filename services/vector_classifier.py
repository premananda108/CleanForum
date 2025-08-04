"""
Vector classifier for spam detection using SentenceTransformer
"""
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import json
import logging
from datetime import datetime
from collections import Counter
from config import settings
from services.redis_manager import vector_manager
from services.spam_detector import spam_detector
from models.database import db
from models.post import PostStatus

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ SentenceTransformers is not installed. Only heuristic analysis is used.")

class VectorSpamClassifier:
    """Spam classifier based on vector search"""

    def __init__(self):
        self.model = None
        self.is_initialized = False

    async def initialize(self):
        """Initialize the model"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logging.warning("SentenceTransformers is not installed. Vector classification is not available.")
            return

        try:
            logging.info("Loading SentenceTransformer model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.is_initialized = True
            logging.info("SentenceTransformer model loaded successfully!")

            # Connect to the vector manager
            await vector_manager.connect()

        except Exception as e:
            logging.error(f"Error loading SentenceTransformer model: {e}", exc_info=True)
            self.is_initialized = False

    def create_vector(self, title: str, content: str, tags: List[str]) -> np.ndarray:
        """Create a vector from the post text"""
        if not self.is_initialized:
            # Return a random vector if the model is not loaded
            return np.random.random(settings.VECTOR_DIM).astype(np.float32)

        # Combine all the text
        combined_text = f"{title}. {content}. Tags: {', '.join(tags)}"

        # Create the embedding
        vector = self.model.encode(combined_text)
        return vector.astype(np.float32)

    async def analyze_with_vectors(self, post_id: str, title: str, content: str,
                                  tags: List[str], author_id: str) -> Dict[str, Any]:
        """Analyze a post using vector search"""
        logging.info(f"[ANALYSIS] Starting spam analysis for post {post_id}.")

        # 1. First, perform heuristic analysis
        heuristic_result = await spam_detector.analyze_post(post_id, title, content, tags, author_id)
        logging.info(f"[ANALYSIS] Heuristics for {post_id}: score={heuristic_result.get('spam_score', 0.0):.2f}, reasons: {heuristic_result.get('reasons')}")

        # 2. Create the post vector
        post_vector = self.create_vector(title, content, tags)
        logging.info(f"[ANALYSIS] Vector for post {post_id} created.")

        # 3. Search for similar posts in the vector database
        similar_posts = await vector_manager.search_similar(post_vector, k=9)
        logging.info(f"[ANALYSIS] Found {len(similar_posts)} similar documents for post {post_id}.")

        # 4. Conduct a vote among similar posts
        vector_result = await self._classify_by_similarity(similar_posts)
        logging.info(f"[ANALYSIS] Vector analysis for {post_id}: prediction={vector_result.get('vector_prediction')}, confidence={vector_result.get('vector_confidence', 0.0):.2f}")

        # 5. Combine the results
        final_result = self._combine_results(heuristic_result, vector_result)
        logging.info(f"[ANALYSIS] Final result for {post_id}: is_spam={final_result.get('is_spam')}, score={final_result.get('spam_score', 0.0):.2f}")

        # 6. Save the post vector to the database (for training future classifications)
        vector_doc_id = f"post:{post_id}"
        await vector_manager.add_vector(vector_doc_id, post_vector, title, content)
        logging.info(f"[ANALYSIS] Vector for post {post_id} saved to Redis.")

        # 7. Save the full analysis result
        await self._save_analysis_result(post_id, final_result, "post")
        logging.info(f"[ANALYSIS] Full analysis result for post {post_id} saved.")

        return final_result

    async def _classify_by_similarity(self, similar_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Classification based on voting of similar documents.
        The status (spam/not spam) of each neighbor is requested from the main DB in real-time.
        """
        from models.post import Post  # Avoid circular import
        from models.comment import Comment

        if not similar_docs:
            return {
                "vector_prediction": "unknown", "vector_confidence": 0.0,
                "similar_posts_count": 0, "spam_neighbors": 0,
                "legitimate_neighbors": 0, "neighbors": []
            }

        spam_votes = 0
        legitimate_votes = 0
        neighbor_details = []

        for doc in similar_docs:
            doc_id_full = doc.get("doc_id", "")
            is_post = doc_id_full.startswith("post:")
            entity_id = doc_id_full.replace("post:", "").replace("comment:", "")

            if not entity_id:
                continue

            # Get the current status from the main database
            entity = await Post.get_by_id(entity_id) if is_post else await Comment.get_by_id(entity_id)

            if entity:
                if entity.is_spam:
                    spam_votes += 1
                else:
                    legitimate_votes += 1
                neighbor_details.append(entity)

        total_votes = spam_votes + legitimate_votes
        if total_votes == 0:
             return {
                "vector_prediction": "unknown", "vector_confidence": 0.0,
                "similar_posts_count": 0, "spam_neighbors": 0,
                "legitimate_neighbors": 0, "neighbors": []
            }


        if spam_votes > legitimate_votes:
            prediction = "spam"
            confidence = spam_votes / total_votes
        else:
            prediction = "legitimate"
            confidence = legitimate_votes / total_votes

        return {
            "vector_prediction": prediction,
            "vector_confidence": confidence,
            "similar_posts_count": len(neighbor_details),
            "spam_neighbors": spam_votes,
            "legitimate_neighbors": legitimate_votes,
            "neighbors": neighbor_details
        }

    def _combine_results(self, heuristic: Dict[str, Any], vector: Dict[str, Any]) -> Dict[str, Any]:
        """Combine the results of heuristic and vector analysis"""

        # Weights for combining
        heuristic_weight = 0.6  # Heuristic analysis is more reliable for obvious spam
        vector_weight = 0.4     # Vector analysis is good for subtle differences

        # Get the scores
        heuristic_score = heuristic.get("spam_score", 0.0)

        # Vector score
        vector_confidence = vector.get("vector_confidence", 0.0)
        vector_is_spam = vector.get("vector_prediction") == "spam"
        vector_score = vector_confidence if vector_is_spam else (1.0 - vector_confidence)

        # Combined score
        combined_score = (heuristic_score * heuristic_weight + vector_score * vector_weight)

        # Final decision
        is_spam = combined_score >= settings.SPAM_THRESHOLD

        # Gather reasons
        reasons = heuristic.get("reasons", [])
        if vector.get("vector_prediction") == "spam" and vector.get("vector_confidence", 0) > 0.7:
            reasons.append(f"Similar to known spam (confidence: {vector.get('vector_confidence', 0):.2f})")

        return {
            "spam_score": combined_score,
            "is_spam": is_spam,
            "reasons": reasons,
            "heuristic_score": heuristic_score,
            "vector_score": vector_score,
            "vector_prediction": vector.get("vector_prediction", "unknown"),
            "vector_confidence": vector.get("vector_confidence", 0.0),
            "similar_posts_count": vector.get("similar_posts_count", 0),
            "spam_neighbors": vector.get("spam_neighbors", 0),
            "legitimate_neighbors": vector.get("legitimate_neighbors", 0),
            "neighbors": vector.get("neighbors", []),
            "user_age_days": heuristic.get("user_age_days", 0)
        }

    async def _save_analysis_result(self, entity_id: str, result: Dict[str, Any], entity_type: str):
        """Save the analysis result (for a post or comment)"""
        analysis_key = f"vector_analysis:{entity_type}:{entity_id}"

        # Convert Pydantic models to dictionaries for JSON serialization
        neighbors_as_dicts = [neighbor.model_dump() for neighbor in result.get("neighbors", [])]

        analysis_data = {
            "entity_id": entity_id,
            "type": entity_type,
            "spam_score": result["spam_score"],
            "is_spam": str(result["is_spam"]),
            "heuristic_score": result["heuristic_score"],
            "vector_score": result["vector_score"],
            "vector_prediction": result["vector_prediction"],
            "vector_confidence": result["vector_confidence"],
            "similar_posts_count": result["similar_posts_count"],
            "reasons": json.dumps(result.get("reasons", [])),
            "neighbors": json.dumps(neighbors_as_dicts, default=str), # default=str to handle datetime
            "analyzed_at": datetime.now().isoformat()
        }
        await db.hset(analysis_key, mapping=analysis_data)

    async def analyze_comment(self, comment_id: str, content: str, author_id: str) -> Dict[str, Any]:
        """Analyze a comment using vector search."""
        # 1. Heuristic analysis
        heuristic_result = await spam_detector.analyze_comment(comment_id, content, author_id)

        # 2. Create a vector
        comment_vector = self.create_vector("", content, []) # No title or tags

        # 3. Search for similar items
        similar_items = await vector_manager.search_similar(comment_vector, k=7)

        # 4. Classify
        vector_result = await self._classify_by_similarity(similar_items)

        # 5. Combine
        final_result = self._combine_results(heuristic_result, vector_result)

        # 6. Save the vector
        vector_doc_id = f"comment:{comment_id}"
        await vector_manager.add_vector(vector_doc_id, comment_vector, content[:100], content)

        # 7. Save the analysis result
        await self._save_analysis_result(comment_id, final_result, "comment")

        return final_result

    async def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics"""

        try:
            # Get information about the vector index
            index_info = await vector_manager.get_index_info()

            return {
                "model_loaded": self.is_initialized,
                "vector_index_exists": bool(index_info),
                "total_vectors": index_info.get("num_docs", 0),
                "index_size": index_info.get("inverted_sz_mb", 0),
                "vector_dimension": settings.VECTOR_DIM
            }
        except Exception as e:
            logging.error(f"Classifier: error getting statistics: {e}")
            return {
                "model_loaded": self.is_initialized,
                "error": str(e)
            }

    async def retrain_with_feedback(self, entity_id: str, entity_type: str, is_spam: bool, moderator_id: str):
        """
        Record feedback for an entity and potentially trigger retraining.
        In a real system, this would update the label in the vector DB.
        """
        logging.info(f"Feedback received for {entity_type} {entity_id}: is_spam={is_spam} by {moderator_id}")
        # This is a stub. In a real application, you would update the vector's metadata.
        pass

# Global classifier instance
vector_classifier = VectorSpamClassifier()

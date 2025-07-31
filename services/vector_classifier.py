"""
Векторный классификатор для определения спама с использованием SentenceTransformer
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

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ SentenceTransformers не установлен. Используется только эвристический анализ.")

class VectorSpamClassifier:
    """Классификатор спама на основе векторного поиска"""

    def __init__(self):
        self.model = None
        self.is_initialized = False

    async def initialize(self):
        """Инициализация модели"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("⚠️ Векторная классификация недоступна")
            return

        try:
            print("🤖 Загружаем модель SentenceTransformer...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.is_initialized = True
            print("✅ Модель загружена успешно!")

            # Подключаемся к векторному менеджеру
            await vector_manager.connect()

        except Exception as e:
            print(f"❌ Ошибка загрузки модели: {e}")
            self.is_initialized = False

    def create_vector(self, title: str, content: str, tags: List[str]) -> np.ndarray:
        """Создать вектор из текста поста"""
        if not self.is_initialized:
            # Возвращаем случайный вектор если модель не загружена
            return np.random.random(settings.VECTOR_DIM).astype(np.float32)

        # Объединяем весь текст
        combined_text = f"{title}. {content}. Tags: {', '.join(tags)}"

        # Создаем эмбеддинг
        vector = self.model.encode(combined_text)
        return vector.astype(np.float32)

    async def analyze_with_vectors(self, post_id: str, title: str, content: str, 
                                  tags: List[str], author_id: str) -> Dict[str, Any]:
        """Анализ поста с использованием векторного поиска"""

        # 1. Сначала проводим эвристический анализ
        heuristic_result = await spam_detector.analyze_post(post_id, title, content, tags, author_id)

        # 2. Создаем вектор поста
        post_vector = self.create_vector(title, content, tags)

        # 3. Ищем похожие посты в векторной базе
        similar_posts = await vector_manager.search_similar(post_vector, k=9)

        # 4. Проводим голосование среди похожих постов
        vector_result = await self._classify_by_similarity(similar_posts)

        # 5. Комбинируем результаты
        final_result = self._combine_results(heuristic_result, vector_result)

        # 6. Сохраняем вектор поста в базу (для обучения будущих классификаций)
        label = "spam" if final_result["is_spam"] else "legitimate"
        await vector_manager.add_vector(post_id, post_vector, label, title, content[:500])

        # 7. Сохраняем полный результат анализа
        await self._save_analysis_result(post_id, final_result)

        return final_result

    async def _classify_by_similarity(self, similar_posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Классификация на основе голосования похожих постов"""

        if not similar_posts:
            return {
                "vector_prediction": "unknown",
                "vector_confidence": 0.0,
                "similar_posts_count": 0,
                "spam_neighbors": 0,
                "legitimate_neighbors": 0
            }

        # Собираем голоса
        labels = [post.get("label", "legitimate") for post in similar_posts]
        label_counts = Counter(labels)

        # Определяем предсказание
        total_votes = len(labels)
        spam_votes = label_counts.get("spam", 0)
        legitimate_votes = label_counts.get("legitimate", 0)

        if spam_votes > legitimate_votes:
            prediction = "spam"
            confidence = spam_votes / total_votes
        else:
            prediction = "legitimate"
            confidence = legitimate_votes / total_votes

        return {
            "vector_prediction": prediction,
            "vector_confidence": confidence,
            "similar_posts_count": total_votes,
            "spam_neighbors": spam_votes,
            "legitimate_neighbors": legitimate_votes,
            "neighbor_scores": [(post.get("score", 0), post.get("label", "unknown")) 
                               for post in similar_posts[:5]]  # Показываем топ-5
        }

    def _combine_results(self, heuristic: Dict[str, Any], vector: Dict[str, Any]) -> Dict[str, Any]:
        """Комбинирование результатов эвристического и векторного анализа"""

        # Веса для комбинирования
        heuristic_weight = 0.6  # Эвристический анализ более надежен для явного спама
        vector_weight = 0.4     # Векторный анализ хорош для тонких различий

        # Получаем оценки
        heuristic_score = heuristic.get("spam_score", 0.0)

        # Векторная оценка
        vector_confidence = vector.get("vector_confidence", 0.0)
        vector_is_spam = vector.get("vector_prediction") == "spam"
        vector_score = vector_confidence if vector_is_spam else (1.0 - vector_confidence)

        # Комбинированная оценка
        combined_score = (heuristic_score * heuristic_weight + vector_score * vector_weight)

        # Итоговое решение
        is_spam = combined_score >= settings.SPAM_THRESHOLD

        # Собираем причины
        reasons = heuristic.get("reasons", [])
        if vector.get("vector_prediction") == "spam" and vector.get("vector_confidence", 0) > 0.7:
            reasons.append(f"Похож на известный спам (уверенность: {vector.get('vector_confidence', 0):.2f})")

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
            "neighbor_scores": vector.get("neighbor_scores", []),
            "user_age_days": heuristic.get("user_age_days", 0)
        }

    async def _save_analysis_result(self, post_id: str, result: Dict[str, Any]):
        """Сохранить результат анализа"""
        analysis_key = f"vector_analysis:{post_id}"
        analysis_data = {
            "post_id": post_id,
            "spam_score": result["spam_score"],
            "is_spam": result["is_spam"],
            "heuristic_score": result["heuristic_score"],
            "vector_score": result["vector_score"],
            "vector_prediction": result["vector_prediction"],
            "vector_confidence": result["vector_confidence"],
            "similar_posts_count": result["similar_posts_count"],
            "reasons": json.dumps(result["reasons"]),
            "analyzed_at": datetime.now().isoformat()
        }

        await db.hset(analysis_key, analysis_data)

    async def retrain_with_feedback(self, post_id: str, is_spam: bool, moderator_id: str):
        """Переобучение на основе обратной связи модератора"""
        logging.info(f"💡 Получена обратная связь для поста {post_id} от модератора {moderator_id}: {'спам' if is_spam else 'не спам'}")
        # Сохраняем обратную связь
        feedback_key = f"feedback:{post_id}"
        feedback_data = {
            "post_id": post_id,
            "is_spam": is_spam,
            "moderator_id": moderator_id,
            "feedback_at": datetime.now().isoformat()
        }

        await db.hset(feedback_key, feedback_data)

        # Обновляем метку в векторной базе
        # В реальной реализации здесь можно было бы обновить существующий вектор
        logging.info(f"Обратная связь для поста {post_id} сохранена.")

    async def get_classification_stats(self) -> Dict[str, Any]:
        """Получить статистику классификации"""

        try:
            # Получаем информацию о векторном индексе
            index_info = await vector_manager.get_index_info()

            return {
                "model_loaded": self.is_initialized,
                "vector_index_exists": bool(index_info),
                "total_vectors": index_info.get("num_docs", 0),
                "index_size": index_info.get("inverted_sz_mb", 0),
                "vector_dimension": settings.VECTOR_DIM
            }
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {
                "model_loaded": self.is_initialized,
                "error": str(e)
            }

# Глобальный экземпляр классификатора
vector_classifier = VectorSpamClassifier()

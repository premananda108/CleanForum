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
from models.post import PostStatus

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
            logging.warning("SentenceTransformers не установлен. Векторная классификация недоступна.")
            return

        try:
            logging.info("Загружаем модель SentenceTransformer...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.is_initialized = True
            logging.info("Модель SentenceTransformer загружена успешно!")

            # Подключаемся к векторному менеджеру
            await vector_manager.connect()

        except Exception as e:
            logging.error(f"Ошибка загрузки модели SentenceTransformer: {e}", exc_info=True)
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
        logging.info(f"[АНАЛИЗ] Начало анализа спама для поста {post_id}.")

        # 1. Сначала проводим эвристический анализ
        heuristic_result = await spam_detector.analyze_post(post_id, title, content, tags, author_id)
        logging.info(f"[АНАЛИЗ] Эвристика для {post_id}: score={heuristic_result.get('spam_score', 0.0):.2f}, причины: {heuristic_result.get('reasons')}")

        # 2. Создаем вектор поста
        post_vector = self.create_vector(title, content, tags)
        logging.info(f"[АНАЛИЗ] Вектор для поста {post_id} создан.")

        # 3. Ищем похожие посты в векторной базе
        similar_posts = await vector_manager.search_similar(post_vector, k=9)
        logging.info(f"[АНАЛИЗ] Найдено {len(similar_posts)} похожих документов для поста {post_id}.")

        # 4. Проводим голосование среди похожих постов
        vector_result = await self._classify_by_similarity(similar_posts)
        logging.info(f"[АНАЛИЗ] Векторный анализ для {post_id}: prediction={vector_result.get('vector_prediction')}, confidence={vector_result.get('vector_confidence', 0.0):.2f}")

        # 5. Комбинируем результаты
        final_result = self._combine_results(heuristic_result, vector_result)
        logging.info(f"[АНАЛИЗ] Итоговый результат для {post_id}: is_spam={final_result.get('is_spam')}, score={final_result.get('spam_score', 0.0):.2f}")

        # 6. Сохраняем вектор поста в базу (для обучения будущих классификаций)
        vector_doc_id = f"post:{post_id}"
        await vector_manager.add_vector(vector_doc_id, post_vector, title, content)
        logging.info(f"[АНАЛИЗ] Вектор для поста {post_id} сохранен в Redis.")

        # 7. Сохраняем полный результат анализа
        await self._save_analysis_result(post_id, final_result, "post")
        logging.info(f"[АНАЛИЗ] Полный результат анализа для поста {post_id} сохранен.")

        return final_result

    async def _classify_by_similarity(self, similar_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Классификация на основе голосования похожих документов.
        Статус (спам/не спам) каждого соседа запрашивается из основной БД в реальном времени.
        """
        from models.post import Post  # Избегаем циклического импорта
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

            # Получаем актуальный статус из основной базы данных
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
            "neighbors": vector.get("neighbors", []),
            "user_age_days": heuristic.get("user_age_days", 0)
        }

    async def _save_analysis_result(self, entity_id: str, result: Dict[str, Any], entity_type: str):
        """Сохранить результат анализа (для поста или комментария)"""
        analysis_key = f"vector_analysis:{entity_type}:{entity_id}"

        # Конвертируем Pydantic модели в словари для JSON-сериализации
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
            "neighbors": json.dumps(neighbors_as_dicts, default=str), # default=str для обработки datetime
            "analyzed_at": datetime.now().isoformat()
        }
        await db.hset(analysis_key, mapping=analysis_data)

    async def analyze_comment(self, comment_id: str, content: str, author_id: str) -> Dict[str, Any]:
        """Анализ комментария с использованием векторного поиска."""
        # 1. Эвристический анализ
        heuristic_result = await spam_detector.analyze_comment(comment_id, content, author_id)

        # 2. Создаем вектор
        comment_vector = self.create_vector("", content, []) # Нет заголовка и тегов

        # 3. Ищем похожие
        similar_items = await vector_manager.search_similar(comment_vector, k=7)

        # 4. Классифицируем
        vector_result = await self._classify_by_similarity(similar_items)

        # 5. Комбинируем
        final_result = self._combine_results(heuristic_result, vector_result)

        # 6. Сохраняем вектор
        vector_doc_id = f"comment:{comment_id}"
        await vector_manager.add_vector(vector_doc_id, comment_vector, content[:100], content)

        # 7. Сохраняем результат анализа
        await self._save_analysis_result(comment_id, final_result, "comment")

        return final_result

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
            logging.error(f"Classifier: ошибка получения статистики: {e}")
            return {
                "model_loaded": self.is_initialized,
                "error": str(e)
            }

# Глобальный экземпляр классификатора
vector_classifier = VectorSpamClassifier()

"""
Система обнаружения спама с использованием эвристик и векторной классификации
"""
from typing import Dict, List, Any, Optional
import re
import json
from datetime import datetime, timedelta
from config import settings
from models.database import db
from models.user import User

class SpamDetector:
    """Эвристический детектор спама"""

    def __init__(self):
        # Ключевые слова спама
        self.spam_keywords = {
            "money": ["заработок", "деньги", "доход", "прибыль", "income", "money", "earn", "$", "cryptocurrency", "bitcoin"],
            "promotion": ["реклама", "продажа", "скидка", "акция", "sale", "discount", "promo", "buy now"],
            "suspicious": ["бесплатно", "free", "win", "winner", "congratulations", "urgent", "срочно", "limited time"],
            "links": ["http://", "https://", "www.", ".com", ".ru", "click here", "нажми", "ссылка"],
            "scam": ["лохотрон", "развод", "scam", "fraud", "fake", "phishing"]
        }

        # Регулярные выражения для поиска подозрительных паттернов
        self.suspicious_patterns = [
            r'[0-9]+\s*[$€₽]\s*(в|в\s+день|в\s+месяц|per\s+day|per\s+month)',  # суммы денег
            r'(зарабат|earn).{0,20}[0-9]+',  # заработок + числа
            r'[A-Z]{3,}\s*[A-Z]{3,}',  # много заглавных букв подряд
            r'[!]{3,}',  # много восклицательных знаков
            r'[\s]{3,}',  # много пробелов
            r'(.){4,}'  # повторяющиеся символы
        ]

    def calculate_spam_score(self, title: str, content: str, tags: List[str], 
                           author_id: str, user_age_days: int) -> Dict[str, Any]:
        """Рассчитать оценку спама для поста"""

        combined_text = f"{title} {content} {' '.join(tags)}".lower()
        score = 0.0
        reasons = []

        # 1. Проверка ключевых слов спама
        keyword_score = 0
        for category, keywords in self.spam_keywords.items():
            found_keywords = [kw for kw in keywords if kw in combined_text]
            if found_keywords:
                category_score = len(found_keywords) * 0.2
                keyword_score += category_score
                reasons.append(f"Найдены спам-слова ({category}): {', '.join(found_keywords)}")

        score += min(keyword_score, 0.4)  # Максимум 40% за ключевые слова

        # 2. Проверка подозрительных паттернов
        pattern_count = 0
        for pattern in self.suspicious_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                pattern_count += len(matches) 
                reasons.append(f"Подозрительный паттерн: {pattern}")

        if pattern_count > 0:
            pattern_score = min(pattern_count * 0.1, 0.25)  # Максимум 25%
            score += pattern_score

        # 3. Анализ структуры текста
        if len(title) < 10:
            score += 0.1
            reasons.append("Слишком короткий заголовок")

        if len(content) < 50:
            score += 0.15
            reasons.append("Слишком короткий контент")

        if len(content) > 10000:
            score += 0.1
            reasons.append("Слишком длинный контент")

        # 4. Анализ заглавных букв
        capital_ratio = sum(1 for c in combined_text if c.isupper()) / max(len(combined_text), 1)
        if capital_ratio > 0.3:
            score += 0.2
            reasons.append(f"Слишком много заглавных букв ({capital_ratio:.1%})")

        # 5. Анализ повторяющихся символов
        repeated_chars = re.findall(r'(.){3,}', combined_text)
        if repeated_chars:
            score += 0.1
            reasons.append("Найдены повторяющиеся символы")

        # 6. Анализ возраста пользователя
        if user_age_days < settings.MIN_USER_AGE_DAYS:
            score += 0.3
            reasons.append(f"Новый пользователь (возраст: {user_age_days} дней)")

        # 7. Анализ тегов
        if len(tags) > 8:
            score += 0.1
            reasons.append(f"Слишком много тегов ({len(tags)})")

        # 8. Проверка на спам-домены
        spam_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 't.co']
        for domain in spam_domains:
            if domain in combined_text:
                score += 0.2
                reasons.append(f"Подозрительный домен: {domain}")

        # Нормализуем оценку
        final_score = min(max(score, 0.0), 1.0)
        is_spam = final_score >= settings.SPAM_THRESHOLD

        return {
            "spam_score": final_score,
            "is_spam": is_spam,
            "reasons": reasons,
            "keyword_matches": keyword_score,
            "pattern_matches": pattern_count,
            "user_age_days": user_age_days
        }

    async def analyze_post(self, post_id: str, title: str, content: str, 
                          tags: List[str], author_id: str) -> Dict[str, Any]:
        """Анализировать пост на спам"""
        logging.info(f"Запуск эвристического анализа для поста {post_id}")

        # Получаем возраст пользователя
        user_age_days = await User.get_user_age_days(author_id)

        # Рассчитываем оценку спама
        result = self.calculate_spam_score(title, content, tags, author_id, user_age_days)
        logging.info(f"Эвристический анализ для поста {post_id} завершен. Оценка: {result['spam_score']:.2f}")

        # Сохраняем результат анализа
        analysis_key = f"spam_analysis:{post_id}"
        analysis_data = {
            "post_id": post_id,
            "author_id": author_id,
            "spam_score": result["spam_score"],
            "is_spam": result["is_spam"],
            "reasons": json.dumps(result["reasons"]),
            "analyzed_at": datetime.now().isoformat(),
            "user_age_days": result["user_age_days"]
        }

        await db.hset(analysis_key, analysis_data)

        return result

    async def get_spam_statistics(self) -> Dict[str, Any]:
        """Получить статистику спама"""
        # В реальном приложении можно использовать более сложные запросы Redis
        return {
            "total_analyzed": 0,  # Заглушка
            "spam_detected": 0,
            "accuracy": 0.0,
            "false_positives": 0,
            "false_negatives": 0
        }

# Глобальный экземпляр детектора
spam_detector = SpamDetector()

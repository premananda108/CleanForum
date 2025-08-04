"""
Spam detection system using heuristics and vector classification
"""
from typing import Dict, List, Any, Optional
import re
import json
import logging
from datetime import datetime, timedelta
from config import settings
from models.database import db
from models.user import User

class SpamDetector:
    """Heuristic spam detector"""

    def __init__(self):
        # Spam keywords
        self.spam_keywords = {
            "money": ["earnings", "money", "income", "profit", "income", "money", "earn", "$", "cryptocurrency", "bitcoin"],
            "promotion": ["advertisement", "sale", "discount", "promo", "sale", "discount", "promo", "buy now"],
            "suspicious": ["free", "free", "win", "winner", "congratulations", "urgent", "urgent", "limited time"],
            "links": ["http://", "https://", "www.", ".com", ".ru", "click here", "click", "link"],
            "scam": ["scam", "fraud", "scam", "fraud", "fake", "phishing"]
        }

        # Regular expressions for finding suspicious patterns
        self.suspicious_patterns = [
            r'[0-9]+\s*[$€₽]\s*(in|per\s+day|per\s+month)',  # sums of money
            r'(earn).{0,20}[0-9]+',  # earnings + numbers
            r'[A-Z]{3,}\s*[A-Z]{3,}',  # many consecutive capital letters
            r'[!]{3,}',  # many exclamation marks
            r'[\s]{3,}'  # many spaces
        ]

    def calculate_spam_score(self, title: str, content: str, tags: List[str],
                           author_id: str, user_age_days: int) -> Dict[str, Any]:
        """Calculate the spam score for a post"""

        combined_text = f"{title} {content} {' '.join(tags)}".lower()
        score = 0.0
        reasons = []

        # 1. Check for spam keywords
        keyword_score = 0
        for category, keywords in self.spam_keywords.items():
            found_keywords = [kw for kw in keywords if kw in combined_text]
            if found_keywords:
                category_score = len(found_keywords) * 0.2
                keyword_score += category_score
                reasons.append(f"Found spam keywords ({category}): {', '.join(found_keywords)}")

        score += min(keyword_score, 0.4)  # Maximum 40% for keywords

        # 2. Check for suspicious patterns
        pattern_count = 0
        for pattern in self.suspicious_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                pattern_count += len(matches)
                reasons.append(f"Suspicious pattern: {pattern}")

        if pattern_count > 0:
            pattern_score = min(pattern_count * 0.1, 0.25)  # Maximum 25%
            score += pattern_score

        # 3. Analyze text structure
        if len(title) < 10:
            score += 0.1
            reasons.append("Title too short")

        if len(content) < 50:
            score += 0.15
            reasons.append("Content too short")

        if len(content) > 10000:
            score += 0.1
            reasons.append("Content too long")

        # 4. Analyze capital letters
        capital_ratio = sum(1 for c in combined_text if c.isupper()) / max(len(combined_text), 1)
        if capital_ratio > 0.3:
            score += 0.2
            reasons.append(f"Too many capital letters ({capital_ratio:.1%})")

        # 5. Analyze repeating characters (6+ in a row)
        repeated_chars = re.findall(r'(.)\1{5,}', combined_text)
        if repeated_chars:
            score += 0.15
            reasons.append("Found long sequences of repeating characters")

        # 6. Analyze user age
        if user_age_days < settings.MIN_USER_AGE_DAYS:
            score += 0.3
            reasons.append(f"New user (age: {user_age_days} days)")

        # 7. Analyze tags
        if len(tags) > 8:
            score += 0.1
            reasons.append(f"Too many tags ({len(tags)})")

        # 8. Check for spam domains
        spam_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 't.co']
        for domain in spam_domains:
            if domain in combined_text:
                score += 0.2
                reasons.append(f"Suspicious domain: {domain}")

        # Normalize the score
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

    def calculate_comment_spam_score(self, content: str, author_id: str, user_age_days: int) -> Dict[str, Any]:
        """Calculate the spam score for a comment (simplified version)"""
        text = content.lower()
        score = 0.0
        reasons = []

        # 1. Keywords
        keyword_score = 0
        for category, keywords in self.spam_keywords.items():
            found = [kw for kw in keywords if kw in text]
            if found:
                keyword_score += len(found) * 0.25
                reasons.append(f"Found spam keywords ({category}): {', '.join(found)}")
        score += min(keyword_score, 0.5)

        # 2. Patterns
        pattern_count = sum(1 for pattern in self.suspicious_patterns if re.search(pattern, text))
        if pattern_count > 0:
            score += min(pattern_count * 0.15, 0.3)
            reasons.append(f"Found {pattern_count} suspicious patterns")

        # 3. Structure
        if len(content) < 15:
            score += 0.15
            reasons.append("Comment too short")
        if len(content) > 2000:
            score += 0.1
            reasons.append("Comment too long")

        # 4. Capital letters
        capital_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
        if capital_ratio > 0.4:
            score += 0.25
            reasons.append(f"Too many capital letters ({capital_ratio:.1%})")

        # 5. User age
        if user_age_days < settings.MIN_USER_AGE_DAYS:
            score += 0.3
            reasons.append(f"New user (age: {user_age_days} days)")

        final_score = min(max(score, 0.0), 1.0)
        return {
            "spam_score": final_score,
            "is_spam": final_score >= settings.SPAM_THRESHOLD,
            "reasons": reasons,
            "user_age_days": user_age_days
        }

    async def analyze_post(self, post_id: str, title: str, content: str,
                          tags: List[str], author_id: str) -> Dict[str, Any]:
        """Analyze a post for spam"""
        logging.info(f"Starting heuristic analysis for post {post_id}")
        user_age_days = await User.get_user_age_days(author_id)
        result = self.calculate_spam_score(title, content, tags, author_id, user_age_days)
        logging.info(f"Heuristic analysis for post {post_id} complete. Score: {result['spam_score']:.2f}")

        # Save the result
        analysis_key = f"spam_analysis:post:{post_id}"
        await db.hset(analysis_key, {
            "entity_id": post_id, "type": "post", "author_id": author_id,
            "spam_score": result["spam_score"], "is_spam": str(result["is_spam"]),
            "reasons": json.dumps(result["reasons"]), "analyzed_at": datetime.now().isoformat()
        })
        return result

    async def analyze_comment(self, comment_id: str, content: str, author_id: str) -> Dict[str, Any]:
        """Analyze a comment for spam"""
        logging.info(f"Starting heuristic analysis for comment {comment_id}")
        user_age_days = await User.get_user_age_days(author_id)
        result = self.calculate_comment_spam_score(content, author_id, user_age_days)
        logging.info(f"Heuristic analysis for comment {comment_id} complete. Score: {result['spam_score']:.2f}")

        # Save the result
        analysis_key = f"spam_analysis:comment:{comment_id}"
        await db.hset(analysis_key, {
            "entity_id": comment_id, "type": "comment", "author_id": author_id,
            "spam_score": result["spam_score"], "is_spam": str(result["is_spam"]),
            "reasons": json.dumps(result["reasons"]), "analyzed_at": datetime.now().isoformat()
        })
        return result

    async def get_spam_statistics(self) -> Dict[str, Any]:
        """Get spam statistics"""
        # In a real application, more complex Redis queries could be used
        return {
            "total_analyzed": 0,  # Stub
            "spam_detected": 0,
            "accuracy": 0.0,
            "false_positives": 0,
            "false_negatives": 0
        }

# Global detector instance
spam_detector = SpamDetector()

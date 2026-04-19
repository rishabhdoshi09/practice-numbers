"""
News sentiment scoring using keyword matching.
Optionally enhanced with a pre-trained transformer (future phase).
"""
import re
from backend.config import SENTIMENT_POSITIVE_KEYWORDS, SENTIMENT_NEGATIVE_KEYWORDS


def score_headline(headline: str) -> float:
    """
    Simple keyword-count sentiment scorer in [-1, +1].
    Positive keywords push toward +1; negative toward -1.
    """
    text = headline.lower()
    pos = sum(1 for kw in SENTIMENT_POSITIVE_KEYWORDS if re.search(r'\b' + kw + r'\b', text))
    neg = sum(1 for kw in SENTIMENT_NEGATIVE_KEYWORDS if re.search(r'\b' + kw + r'\b', text))
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 4)


def aggregate_sentiment(news_items: list[dict]) -> dict:
    """
    Aggregate sentiment across multiple news items, weighted by recency.
    Most recent article carries weight 1.0, each prior step decays by 0.7.
    """
    if not news_items:
        return {"score": 0.0, "label": "neutral", "signal": 0.0, "item_scores": []}

    scored = []
    for item in news_items:
        s = item.get("score") or score_headline(item.get("headline", ""))
        scored.append({"headline": item.get("headline", ""), "score": s})

    weights = [0.7 ** i for i in range(len(scored))]
    weighted_score = sum(s["score"] * w for s, w in zip(scored, weights))
    total_weight   = sum(weights)
    final_score    = weighted_score / (total_weight + 1e-10)

    label = "positive" if final_score > 0.1 else ("negative" if final_score < -0.1 else "neutral")
    return {
        "score": round(final_score, 4),
        "label": label,
        "signal": round(final_score, 4),   # already in [-1, +1]
        "item_scores": scored,
    }

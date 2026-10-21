"""
Trend service for keyword frequency counting and week-over-week analysis.

Trends are computed from a date window over every scraped row. There is no
report version involved: a week is a week of scrapes, not a click on a button.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.linear_model import LinearRegression

from src.db import repos

logger = logging.getLogger(__name__)

# Common tech keywords to track for frequency analysis
TECH_KEYWORDS = [
    # Languages
    "react", "typescript", "python", "javascript", "golang", "rust",
    "java", "c++", "c#", "ruby", "swift", "kotlin", "scala", "php",
    # AI/ML - Expanded for booming roles
    "machine learning", "ai", "ml", "deep learning", "llm", "nlp",
    "generative ai", "chatgpt", "openai", "tensorflow", "pytorch",
    "data science", "data scientist", "ai engineer", "ml engineer",
    "computer vision", "reinforcement learning", "prompt engineering",
    # Infrastructure
    "kubernetes", "docker", "devops", "sre", "cloud", "aws", "gcp", "azure",
    "terraform", "ansible", "ci/cd", "github actions", "jenkins",
    # Databases
    "postgres", "postgresql", "mongodb", "redis", "elasticsearch", "mysql",
    "dynamodb", "cassandra", "sqlite", "sql", "nosql",
    # Frontend
    "vue", "angular", "next.js", "svelte", "tailwind", "css", "html",
    "graphql", "apollo", "redux", "react native", "flutter",
    # Backend
    "node.js", "fastapi", "django", "flask", "rails", "spring",
    "express", "gin", "echo", "nestjs", "fiber",
    # Architecture
    "api", "grpc", "microservices", "backend", "frontend", "fullstack",
    "serverless", "lambda", "rest", "webhooks",
    # Work style
    "remote", "onsite", "hybrid", "startup", "senior", "junior", "principal",
    "lead", "manager", "director", "staff",
    # General tech
    "security", "blockchain", "web3", "iot", "5g", "edge computing",
    # Job roles - Add to track specific roles
    "frontend developer", "backend developer", "full stack developer",
    "data engineer", "ml engineer", "devops engineer", "sre",
    "product manager", "mobile developer", "qa engineer", "security engineer",
    "cloud architect", "data analyst", "software engineer", "site reliability",
    # Emerging roles
    "platform engineer", "mle", "research scientist", "applied scientist",
    "solutions architect", "technical lead", "engineering manager",
]

# Predefined declining roles (vulnerable to automation/technology shifts)
DECLINING_KEYWORDS = [
    # Roles being automated
    "manual tester", "manual qa", "test automation", "automation testing",
    "basic coding", "template developer", "wordpress developer",
    "legacy cobol", "mainframe", "asm", "assembly",
    # Outdated technologies
    "jquery", "angularjs", "backbone", "ember", "extjs",
    "silverlight", "flash", "flex", "actionscript",
    "perl", "shell scripting", "powershell",
    # Support/operations roles being automated
    "helpdesk", "technical support", "level 1 support", "tier 1 support",
    "call center", "customer service", "data entry",
    # Junior roles shrinking
    "junior developer", "entry level developer", "intern",
    # Roles shifted to AI
    "copywriter", "content writer", "technical writer",
    "basic analyst", "report analyst", "excel analyst",
]


def tokenize_text(text: str) -> set[str]:
    """Tokenize text into lowercase words, removing punctuation."""
    if not text:
        return set()

    text = text.lower()
    text = re.sub(r'[/\\()\[\]{}.,;:!?\'"<>]', ' ', text)
    return set(text.split())


async def extract_keywords(text: str, keywords: Optional[List[str]] = None) -> set[str]:
    """Extract matching keywords from text."""
    if keywords is None:
        keywords = TECH_KEYWORDS

    if not text:
        return set()

    normalized_text = text.lower()
    tokens = tokenize_text(normalized_text)

    matched = set()
    for keyword in keywords:
        if " " in keyword:
            if keyword in normalized_text:
                matched.add(keyword)
        elif keyword in tokens:
            matched.add(keyword)

    return matched


def current_week_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Week window used for trend counts: [week_start, week_end)."""
    now = now or datetime.utcnow()
    week_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_end - timedelta(days=7)
    return week_start, week_end


async def compute_keyword_frequencies() -> List[Dict[str, Any]]:
    """
    Compute keyword frequencies for the current week and the week-over-week change.

    Counts every job and news item scraped inside the current week window,
    compares with the stored previous week, and upserts one row per keyword.
    """
    week_start, week_end = current_week_bounds()
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_start

    jobs = await repos.jobs_text_since(week_start.isoformat())
    news_items = await repos.news_text_since(week_start.isoformat())

    keyword_counts: Dict[str, int] = {}

    for job in jobs:
        matched = await extract_keywords(job.get("title") or "")
        for kw in matched:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        tags = job.get("tags") or []
        tags_text = " ".join(tags) if isinstance(tags, list) else str(tags)
        if tags_text:
            matched = await extract_keywords(tags_text)
            for kw in matched:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    for item in news_items:
        matched = await extract_keywords(item.get("title") or "")
        for kw in matched:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        if item.get("summary"):
            matched = await extract_keywords(item["summary"])
            for kw in matched:
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    prev_trends = {
        t["keyword"]: t["count"]
        for t in await repos.list_trends(prev_week_start.isoformat())
    }

    results: List[Dict[str, Any]] = []
    for keyword, count in keyword_counts.items():
        prev_count = prev_trends.get(keyword, 0)
        if prev_count > 0:
            percentage_change = ((count - prev_count) / prev_count) * 100
        else:
            percentage_change = 100.0 if count > 0 else 0.0

        if percentage_change > 20:
            direction = "booming"
        elif percentage_change < -20:
            direction = "declining"
        else:
            direction = "neutral"

        await repos.upsert_trend(
            keyword=keyword,
            count=count,
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            percentage_change=percentage_change,
            direction=direction,
        )

        results.append(
            {
                "keyword": keyword,
                "count": count,
                "percentage_change": percentage_change,
                "week_start": week_start,
                "week_end": week_end,
            }
        )

    logger.info("Computed keyword frequencies for %s keywords", len(results))
    return results


async def get_trends(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get trending keywords with week-over-week analysis.

    Returns up to 5 booming and 3 declining keywords, and falls back to
    sample data when no week has been counted yet.
    """
    try:
        week_start, _ = current_week_bounds()
        trends = await repos.list_trends(week_start.isoformat())

        if not trends:
            return _get_sample_trends_with_roles()

        prev_week_start = week_start - timedelta(days=7)
        has_prev_data = bool(await repos.list_trends(prev_week_start.isoformat()))

        booming = [t for t in trends if t["percentage_change"] > 20]
        declining = [t for t in trends if t["percentage_change"] < -20]

        if not has_prev_data and (booming or declining):
            max_count = max((t["count"] for t in trends), default=1)
            for t in trends:
                t["percentage_change"] = (t["count"] / max_count) * 100 if max_count else 0
            booming = [t for t in trends if t["count"] >= max_count * 0.5]
            declining = [t for t in trends if t["count"] < max_count * 0.3]

        booming.sort(key=lambda t: abs(t["percentage_change"]), reverse=True)
        declining.sort(key=lambda t: abs(t["percentage_change"]), reverse=True)

        top_booming = booming[:5]
        top_declining = declining[:3]

        if not top_booming:
            top_booming = sorted(trends, key=lambda t: t["count"], reverse=True)[:5]
        if not top_declining:
            top_declining = sorted(trends, key=lambda t: t["count"])[:3]

        results = [
            {
                "skill": t["keyword"].title(),
                "percentage": min(abs(t["percentage_change"]), 100),
                "weeklyChange": t["percentage_change"],
                "direction": "booming",
            }
            for t in top_booming
        ]
        results.extend(
            {
                "skill": t["keyword"].title(),
                "percentage": min(abs(t["percentage_change"]), 100),
                "weeklyChange": t["percentage_change"],
                "direction": "declining",
            }
            for t in top_declining
        )

        if not [r for r in results if r["direction"] == "declining"]:
            results.extend(_get_declining_roles_sample())

        return results

    except Exception as e:
        logger.exception("Error getting trends")
        return _get_sample_trends_with_roles()


def _get_sample_trends_with_roles() -> List[Dict[str, Any]]:
    """Return sample trend data with diverse roles including ML, Data Science, Gen AI."""
    return [
        # Booming roles
        {"skill": "ML Engineer", "percentage": 92, "weeklyChange": 25, "direction": "booming"},
        {"skill": "Data Science", "percentage": 88, "weeklyChange": 22, "direction": "booming"},
        {"skill": "Gen AI", "percentage": 85, "weeklyChange": 35, "direction": "booming"},
        {"skill": "LLM Developer", "percentage": 80, "weeklyChange": 28, "direction": "booming"},
        {"skill": "Cloud Architect", "percentage": 75, "weeklyChange": 18, "direction": "booming"},
        {"skill": "DevOps/SRE", "percentage": 72, "weeklyChange": 15, "direction": "booming"},
        {"skill": "Frontend Dev", "percentage": 70, "weeklyChange": 12, "direction": "booming"},
        {"skill": "Backend Dev", "percentage": 68, "weeklyChange": 10, "direction": "booming"},
        # Declining roles
        {"skill": "Manual QA", "percentage": 35, "weeklyChange": -15, "direction": "declining"},
        {"skill": "jQuery Dev", "percentage": 28, "weeklyChange": -22, "direction": "declining"},
        {"skill": "AngularJS", "percentage": 22, "weeklyChange": -28, "direction": "declining"},
    ]


def _get_declining_roles_sample() -> List[Dict[str, Any]]:
    """Return predefined declining roles for industry context."""
    return [
        {"skill": "Manual QA", "percentage": 35, "weeklyChange": -15, "direction": "declining"},
        {"skill": "jQuery Dev", "percentage": 28, "weeklyChange": -22, "direction": "declining"},
        {"skill": "Legacy Support", "percentage": 25, "weeklyChange": -18, "direction": "declining"},
    ]


class TrendService:
    """Service class for trend operations."""

    def __init__(self):
        self.tech_keywords = TECH_KEYWORDS

    async def extract_keywords(self, text: str) -> set[str]:
        """Extract matching keywords from text."""
        return await extract_keywords(text, self.tech_keywords)

    async def compute_frequencies(self) -> List[Dict[str, Any]]:
        """Compute keyword frequencies for the current week."""
        return await compute_keyword_frequencies()

    async def get_trending(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending keywords."""
        return await get_trends(limit)

    async def predict_keywords(
        self, keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Predict W+2 and W+4 counts for the given keywords.

        Uses a linear regression on weekly counts when at least 8 weeks of
        history exist. Stores the prediction and returns it.
        """
        results: List[Dict[str, Any]] = []

        if keywords is None:
            week_start, _ = current_week_bounds()
            keywords = [t["keyword"] for t in await repos.list_trends(week_start.isoformat())]

        for kw in keywords:
            history = await repos.trend_history(kw)
            counts = [h["count"] for h in history]
            weeks = list(range(1, len(counts) + 1))

            current = counts[-1] if counts else 0
            pred_w2 = None
            pred_w4 = None
            confidence = 0.0

            if len(counts) >= 8:
                X = np.array(weeks).reshape(-1, 1)
                y = np.array(counts)
                try:
                    model = LinearRegression()
                    model.fit(X, y)
                    last_week = weeks[-1]
                    pred_w2 = int(round(model.predict(np.array([[last_week + 2]]))[0]))
                    pred_w4 = int(round(model.predict(np.array([[last_week + 4]]))[0]))
                    confidence = float(model.score(X, y))
                except Exception:
                    pred_w2 = None
                    pred_w4 = None
                    confidence = 0.0

            if pred_w2 is not None:
                await repos.insert_prediction(kw, 2, pred_w2, confidence)
            if pred_w4 is not None:
                await repos.insert_prediction(kw, 4, pred_w4, confidence)

            results.append(
                {
                    "keyword": kw,
                    "current": int(current),
                    "w2": pred_w2,
                    "w4": pred_w4,
                    "confidence": confidence,
                }
            )

        return results

    async def run_predictions_backfill(self) -> int:
        """Backfill predictions for keywords that have at least 8 weeks of data."""
        processed = 0
        keywords = await repos.distinct_trend_keywords()
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()

        for kw in keywords:
            if await repos.recent_prediction_exists(kw, cutoff):
                continue
            history = await repos.trend_history(kw)
            if len(history) >= 8:
                await self.predict_keywords([kw])
                processed += 1

        logger.info("Trend prediction backfill: %s keywords processed", processed)
        return processed


async def run_predictions_backfill() -> int:
    """Module-level helper used by API routes."""
    return await TrendService().run_predictions_backfill()

"""
Pydantic request/response models for TazaKhabar API.
"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str
    code: str
    detail: str | None = None


class JobResponse(BaseModel):
    """Job response matching frontend Job type exactly."""
    id: str
    title: str
    role: str
    company: str
    location: str
    locationType: str  # "Remote" | "Hybrid" | "On-site"
    companySize: str = "N/A"
    salary: str = "N/A"
    fundingStage: str = "N/A"
    deadline: str | None = None
    skills: list[str] = Field(default_factory=list)
    postedDays: int = 0
    hiringStatus: str = "HIRING_ACTIVE"  # "HIRING_ACTIVE" | "SLOW_HIRING"
    saved: bool = False
    applied: bool = False
    experienceTier: str = "I"  # "I" | "II" | "III" | "IV"
    emailAvailable: bool = False
    applyAvailable: bool = True


class NewsResponse(BaseModel):
    """News response matching frontend DigestItem type."""
    id: str
    headline: str  # rewritten title (use title from DB)
    source: str  # "Ask HN", "Show HN", "Top Story"
    summary: str = "N/A"  # AI summary — show "N/A" until Phase 2 LLM fills
    category: str = "ALL"  # "ALL" | "HIRING" | "LAYOFFS" | "FUNDING" | "SKILLS"
    readTime: str = "5 min read"
    featured: bool = False


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int
    skip: int
    limit: int
    has_more: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    data: list[T]
    meta: PaginationMeta


class JobFilterParams(BaseModel):
    """Query parameters for job feed filtering."""
    roles: list[str] = Field(default_factory=list)
    remote: bool = False
    startup_only: bool = False
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, le=100)


class BadgeResponse(BaseModel):
    """Badge counter response for new items since last scrape."""
    radar_new_count: int = Field(default=0, description="New job postings since last refresh")
    feed_new_count: int = Field(default=0, description="New news items since last refresh")


class RefreshResponse(BaseModel):
    """Report swap/refresh response."""
    status: str = Field(default="swapped", description="Status of the refresh operation")
    radar_new_count: int = Field(default=0, description="New job count after swap")
    feed_new_count: int = Field(default=0, description="New news count after swap")


class ObservationResponse(BaseModel):
    """Market observation response from LLM."""
    text: str
    generated_at: str | None = None
    fallback: bool = False

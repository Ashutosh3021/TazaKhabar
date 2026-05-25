"""
Job processing service for cleaning and normalizing scraped job data using LLM.
"""
import logging
from datetime import datetime

from sqlalchemy import select, update

from src.db.database import async_session
from src.db.models import Job
from src.services.llm_service import _call_llm, generate_with_retry

logger = logging.getLogger(__name__)

# System prompt for job cleaning
JOB_CLEANING_SYSTEM = """You are a job posting normalizer. Your task is to extract clean, structured information from messy job post text.
Return ONLY valid JSON with these fields:
- title: The actual job title (e.g., "Senior Frontend Engineer", "Staff DevOps Engineer")
- role: The job role category (e.g., "Frontend Dev", "Backend Dev", "ML Engineer", "Data Science", "Gen AI", "DevOps", "Full Stack", "Product Manager", "Mobile Dev", "QA Engineer", "Security", "Data Analyst")
- company: The company name (just the name, no description)
- tags: Array of relevant tech/tags (e.g., ["React", "TypeScript", "Python", "ML"])
- location_type: One of "Remote", "Onsite", "Hybrid", or "Unknown"
- job_description: Clean plain text version of the job description (remove HTML tags, clean up whitespace, max 500 chars)
- email_available: true if email/contact info found in text, false otherwise
- apply_link: true if application link/URL found in text, false otherwise
"""

JOB_CLEANING_PROMPT = """Extract clean structured data from this job posting. Return JSON only.

Raw job text:
Title: {raw_title}
Company: {raw_company}
Location: {raw_location}
Full Text (may contain HTML): {raw_text}

IMPORTANT: 
1. Look for the job role in H3 headings or similar (e.g., "<h3>Frontend Developer</h3>" or role mentions)
2. Categorize the role into: "Frontend Dev", "Backend Dev", "Full Stack", "ML Engineer", "Data Science", "Gen AI", "DevOps/SRE", "Product Manager", "Mobile Dev", "QA Engineer", "Security", "Data Analyst", "Cloud Architect", "Data Engineer"
3. Clean the job description by removing HTML tags and extracting plain text
4. Check for email addresses or "apply with email" text
5. Check for apply URLs or "apply now" links

Return this JSON format:
{{"title": "...", "role": "...", "company": "...", "tags": [...], "location_type": "...", "job_description": "...", "email_available": true/false, "apply_link": true/false}}

JSON:"""


async def process_job_with_llm(job_id: str) -> dict | None:
    """
    Process a single job with LLM to clean/normalize data.
    Returns the cleaned data or None if processing fails.
    """
    async with async_session() as session:
        stmt = select(Job).where(Job.id == job_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning(f"Job not found: {job_id}")
            return None
        
        if job.processed:
            logger.debug(f"Job already processed: {job_id}")
            return {"title": job.cleaned_title, "company": job.cleaned_company}
        
        raw_title = job.title or ""
        raw_company = job.company or ""
        raw_location = job.location or ""
        
        # Get raw text from original scraped text (use title + location as fallback)
        raw_text = f"Title: {raw_title}\nCompany: {raw_company}\nLocation: {raw_location}"
        
        # Include original description if available
        if hasattr(job, 'description') and job.description:
            raw_text = f"{raw_text}\n\nDescription: {job.description}"
        
        prompt = JOB_CLEANING_PROMPT.format(
            raw_title=raw_title,
            raw_company=raw_company,
            raw_location=raw_location,
            raw_text=raw_text,
        )
        
        try:
            response = await generate_with_retry(prompt, JOB_CLEANING_SYSTEM)
            
            # Parse JSON from response
            import json
            import re
            
            # Extract JSON from response - handle nested objects
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                cleaned = json.loads(json_match.group(0))
                
                # Update job in database
                job.cleaned_title = cleaned.get("title", raw_title)
                job.cleaned_company = cleaned.get("company", raw_company)
                
                # Handle role field - map to standardized roles
                role = cleaned.get("role", "")
                if role:
                    job.role = _normalize_role(role)
                
                job.processed = True
                
                # Update tags if LLM provided better ones
                if cleaned.get("tags"):
                    job.tags = cleaned.get("tags")
                
                # Update location_type based on LLM output
                if cleaned.get("location_type"):
                    loc_type = cleaned.get("location_type")
                    if loc_type in ["Remote", "Onsite", "Hybrid"]:
                        job.location = loc_type
                
                # Store cleaned job description
                if cleaned.get("job_description"):
                    job.description = cleaned.get("job_description")[:1000]  # Limit length
                
                # Store email/apply availability
                if cleaned.get("email_available"):
                    job.email_contact = "detected"
                if cleaned.get("apply_link"):
                    job.apply_link = job.apply_link or "detected"
                
                job.scraped_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Processed job {job_id}: {cleaned.get('title')} @ {cleaned.get('company')} | Role: {role}")
                return cleaned
            else:
                logger.warning(f"Could not parse JSON from LLM response for job {job_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")
            return None


def _normalize_role(role: str) -> str:
    """Normalize role string to standardized categories."""
    role_lower = role.lower().strip()
    
    role_mapping = {
        "frontend": "Frontend Dev",
        "front-end": "Frontend Dev",
        "react": "Frontend Dev",
        "vue": "Frontend Dev",
        "angular": "Frontend Dev",
        "ui": "Frontend Dev",
        "backend": "Backend Dev",
        "back-end": "Backend Dev",
        "api": "Backend Dev",
        "server": "Backend Dev",
        "database": "Backend Dev",
        "fullstack": "Full Stack",
        "full-stack": "Full Stack",
        "full stack": "Full Stack",
        "mern": "Full Stack",
        "mean": "Full Stack",
        "machine learning": "ML Engineer",
        "ml engineer": "ML Engineer",
        "ml": "ML Engineer",
        "deep learning": "ML Engineer",
        "data science": "Data Science",
        "data scientist": "Data Science",
        "gen ai": "Gen AI",
        "generative ai": "Gen AI",
        "llm": "Gen AI",
        "artificial intelligence": "AI/ML",
        "ai engineer": "AI/ML",
        "devops": "DevOps/SRE",
        "sre": "DevOps/SRE",
        "site reliability": "DevOps/SRE",
        "cloud": "Cloud Architect",
        "aws": "Cloud Architect",
        "azure": "Cloud Architect",
        "gcp": "Cloud Architect",
        "kubernetes": "DevOps/SRE",
        "data engineer": "Data Engineer",
        "etl": "Data Engineer",
        "pipeline": "Data Engineer",
        "data analyst": "Data Analyst",
        "analytics": "Data Analyst",
        "product manager": "Product Manager",
        "pm": "Product Manager",
        "mobile": "Mobile Dev",
        "react native": "Mobile Dev",
        "flutter": "Mobile Dev",
        "ios": "Mobile Dev",
        "android": "Mobile Dev",
        "qa": "QA Engineer",
        "quality": "QA Engineer",
        "test": "QA Engineer",
        "security": "Security",
        "appsec": "Security",
        "infosec": "Security",
    }
    
    for key, value in role_mapping.items():
        if key in role_lower:
            return value
    
    return role.title() if role else "Other"


async def process_all_unprocessed_jobs(limit: int = 50) -> dict:
    """
    Process all unprocessed jobs in the database.
    Runs in background and processes jobs in batches.
    """
    logger.info(f"Starting job processing (limit: {limit})")
    
    async with async_session() as session:
        stmt = select(Job).where(Job.processed == False).limit(limit)
        result = await session.execute(stmt)
        jobs = result.scalars().all()
    
    success_count = 0
    error_count = 0
    
    for job in jobs:
        result = await process_job_with_llm(job.id)
        if result:
            success_count += 1
        else:
            error_count += 1
    
    logger.info(f"Job processing complete: {success_count} succeeded, {error_count} failed")
    return {"success": success_count, "errors": error_count, "total": len(jobs)}

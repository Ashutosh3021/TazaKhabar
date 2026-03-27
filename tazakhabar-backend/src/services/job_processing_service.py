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
- company: The company name (just the name, no description)
- tags: Array of relevant tech/tags (e.g., ["React", "TypeScript", "Remote", "Senior"])
- location_type: One of "Remote", "Onsite", "Hybrid", or "Unknown"
"""

JOB_CLEANING_PROMPT = """Extract clean structured data from this job posting. Return JSON only.

Raw job text:
Title: {raw_title}
Company: {raw_company}
Location: {raw_location}
Text: {raw_text}

Return this JSON format:
{{"title": "...", "company": "...", "tags": [...], "location_type": "..."}}

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
            
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                cleaned = json.loads(json_match.group(0))
                
                # Update job in database
                job.cleaned_title = cleaned.get("title", raw_title)
                job.cleaned_company = cleaned.get("company", raw_company)
                job.processed = True
                
                # Update tags if LLM provided better ones
                if cleaned.get("tags"):
                    job.tags = cleaned.get("tags")
                
                # Update location_type based on LLM output
                if cleaned.get("location_type"):
                    loc_type = cleaned.get("location_type")
                    if loc_type in ["Remote", "Onsite", "Hybrid"]:
                        job.location = loc_type
                
                job.scraped_at = datetime.utcnow()
                await session.commit()
                
                logger.info(f"Processed job {job_id}: {cleaned.get('title')} @ {cleaned.get('company')}")
                return cleaned
            else:
                logger.warning(f"Could not parse JSON from LLM response for job {job_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")
            return None


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

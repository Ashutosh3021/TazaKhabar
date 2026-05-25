### P1 [DONE]
```
{
  "phase": 1,
  "pass": [
    "WhoIsHiring parse_comment sets email_contact and apply_link separately and computes is_ghost_job correctly",
    "Report 2 tagging is applied on save via report_version='2' and new_items is stored in scraper Report rows",
    "Badge counter is exposed by /api/badge using get_badge_counts"
  ],
  "fail": [
    {
      "item": "APScheduler registration interval",
      "broken": "scheduler.add_job(\n _ask_hn_job,\n trigger=CronTrigger(hour=\"/4\"),\n id=\"ask_hn\",\n name=\"Ask HN Scraper\",\n replace_existing=True,\n)\n...\nscheduler.add_job(\n _show_hn_job,\n trigger=CronTrigger(hour=\"/6\"),\n id=\"show_hn\",\n name=\"Show HN Scraper\",\n replace_existing=True,\n)",
      "fixed": "scheduler.add_job(\n ask_hn_job,\n trigger=CronTrigger(hour=\"/2\"),\n id=\"ask_hn\",\n name=\"Ask HN Scraper\",\n replace_existing=True,\n)\n...\nscheduler.add_job(\n _show_hn_job,\n trigger=CronTrigger(hour=\"/2\"),\n id=\"show_hn\",\n name=\"Show HN Scraper\",\n replace_existing=True,\n)"
    },
    {
      "item": "Deduplication logic",
      "broken": "if await self.check_exists(session, hn_item_id, Job):\n continue",
      "fixed": "existing_job = await session.execute(select(Job).where(Job.hn_item_id == hn_item_id))\nexisting = existing_job.scalar_one_or_none()\nif existing and not has_deadline_passed(existing.deadline):\n continue\n# If existing deadline has passed, preserve/refresh or insert as a new item instead of skipping."
    }
  ],
  "missing": [
    {
      "item": "contact_extractor module",
      "broken": "No dedicated contact_extractor file or module found in backend/src",
      "fixed": "Create a dedicated contact_extractor.py and move the email/apply_link extraction logic from WhoIsHiringScraper.parse_comment into it, then import it from the scraper."
    }
  ],
  "critical_bugs": [
    "Scheduler intervals outside 1-2 hour requirement for Ask HN and Show HN",
    "Job deduplication only checks HN item_id and ignores deadline handling"
  ],
  "files_checked": [
    "backend/src/scheduler.py",
    "backend/src/scrapers/who_is_hiring.py",
    "backend/src/scrapers/ask_hn.py",
    "backend/src/scrapers/show_hn.py",
    "backend/src/scrapers/top_stories.py",
    "backend/src/scrapers/base_scraper.py",
    "backend/src/services/report_service.py",
    "backend/src/api/badge.py",
    "backend/src/db/schemas.py"
  ]
}
```
### P2 [DONE]
```
{
  "phase": 2,
  "pass": [
    {
      "item": "Refresh swap is user-triggered",
      "notes": "Report swap only occurs on POST /api/refresh and there is no automatic mid-session swap path in the backend."
    },
    {
      "item": "Dedicated badge endpoint exists",
      "notes": "GET /api/badge is implemented and returns badge counts from report service."
    }
  ],
  "fail": [
    {
      "item": "Diff calculation after scrape",
      "notes": "No implementation compares Report 2 vs Report 1 separately or stores separate new_jobs/new_news counts; badge service only counts active report_version='1' items."
    },
    {
      "item": "Frontend refresh banner and action",
      "notes": "No refresh banner appears in the UI; no component calls triggerRefresh(), so user cannot tap to swap and clear badges."
    },
    {
      "item": "Badge response naming",
      "notes": "Endpoint returns radar_new_count/feed_new_count instead of new_jobs/new_news, which is a mismatch to the requested payload shape."
    },
    {
      "item": "Swap race protection",
      "notes": "swap_reports uses a single DB session but there is no explicit lock/queue to prevent concurrent scraper writes during a swap."
    }
  ],
  "missing": [
    {
      "item": "Frontend swap UI",
      "notes": "No refresh banner or refresh-button wiring exists in the React frontend."
    },
    {
      "item": "Separate new_jobs/new_news counters",
      "notes": "Backend does not persist separate new job and new news diff counts anywhere."
    },
    {
      "item": "Contact point for race locking",
      "notes": "No explicit swap lock, mutex, or queue is present around report swapping and scraper writes."
    }
  ],
  "critical_bugs": [
    "Missing frontend refresh flow means badge counts can never be cleared by the user.",
    "No separate report diff for jobs vs news makes badge semantics imprecise.",
    "API field-name mismatch may continue P1 badge_counter failures."
  ],
  "files_checked": [
    "backend/src/services/report_service.py",
    "backend/src/api/refresh.py",
    "backend/src/api/badge.py",
    "src/lib/api.ts",
    "src/components/TopNav.tsx"
  ]
}
```
### P3 [DONE]
```
{
  "phase": 3,
  "pass": [
    {
      "item": "Summarization scheduled after scrape",
      "notes": "save_news() schedules summarize_top_news() for new items, and summarize_news_item() stores the LLM summary on News.summary."
    },
    {
      "item": "Summarization prompt enforces job-market focus",
      "notes": "SUMMARIZATION_PROMPT asks for 2-3 sentence summaries focused on job market impact, and SUMMARIZATION_SYSTEM is a tech job market analyst."
    },
    {
      "item": "Trend observation prompt enforces one paragraph",
      "notes": "OBSERVATION_PROMPT asks for one paragraph of actionable insights based on booming/declining keywords."
    },
    {
      "item": "LLM retry/backoff exists for rate-limit errors",
      "notes": "_call_llm() is wrapped by tenacity with exponential backoff and retries on 429/quota/503-like errors."
    }
  ],
  "fail": [
    {
      "item": "Trend narration pipeline endpoint",
      "notes": "The /api/trends/observation endpoint returns static placeholder text; actual generated observation is stored in Observation table by scheduler, not surfaced here."
    },
    {
      "item": "Headline rewriter / display_title",
      "notes": "No display_title field exists and no headline rewrite pipeline is implemented for news headlines; only Job.cleaned_title exists for job normalization."
    },
    {
      "item": "Rate limiter on Gemini calls",
      "notes": "Rate-limiting DB helpers exist, but summarization and observation calls do not call check_rate_limit/check_and_increment; the LLM pipeline is not guarded by request quotas."
    },
    {
      "item": "Gemini API call path",
      "notes": "The backend uses OpenRouter/Groq wrappers for LLM calls; there is no direct Gemini 1.5 Flash API invocation in the audited pipeline."
    },
    {
      "item": "500 error retry behavior",
      "notes": "_is_retryable_error() does not classify HTTP 500 as retryable, so 500 responses are not retried with backoff."
    }
  ],
  "missing": [
    {
      "item": "Headline display_title field",
      "notes": "There is no display_title property or dedicated headline rewriting storage for news or jobs in the current model schema."
    },
    {
      "item": "Queued retry on rate-limit hit",
      "notes": "There is no queueing mechanism for Gemini calls when limits are exceeded; requests are not deferred to the next window."
    },
    {
      "item": "Direct Gemini prompt implementation",
      "notes": "No actual Gemini-specific call or Gemini prompt wrapper exists; only OpenRouter/Groq wrappers are present."
    }
  ],
  "critical_bugs": [
    "No headline rewrite pipeline despite Phase 3 scope for cleaner display titles.",
    "LLM summarization is not quota-guarded, so high-volume async summarization can exceed API limits silently.",
    "Trend narration is stored separately from trends table and the trend observation endpoint is placeholder, so the narrative pipeline is not fully exposed."
  ],
  "files_checked": [
    "backend/src/services/llm_service.py",
    "backend/src/scrapers/base_scraper.py",
    "backend/src/services/trend_service.py",
    "backend/src/scheduler.py",
    "backend/src/api/trends.py",
    "backend/src/api/observation.py",
    "backend/src/services/job_processing_service.py",
    "backend/src/db/models.py"
  ]
}
```
### P4 [DONE]
```
{
  "phase": 4,
  "title": "Resume upload, ATS scoring, and resume intelligence",
  "status": "completed",
  "backend": {
    "files": [
      "backend/src/api/resume.py",
      "backend/src/services/resume_service.py"
    ],
    "changes": [
      "Integrated resume section chunking into /api/resume/analyse",
      "Added live trending keyword retrieval via TrendService for suggested additions",
      "Improved suggested additions prompt to use parsed resume skills and experience sections",
      "Retained missing_keywords output from ATS scoring response"
    ],
    "validation": {
      "syntax": "passed",
      "tested_files": [
        "backend/src/api/resume.py",
        "backend/src/services/resume_service.py"
      ]
    }
  },
  "frontend": {
    "files": [
      "src/app/profile/page.tsx"
    ],
    "changes": [
      "Rendered ATS missing_keywords in resume intelligence UI",
      "Refreshed backend profile state after successful resume analysis",
      "Preserved original stored resume content type when re-analyzing stored resume",
      "Improved analyze button behavior to support re-analysis from stored resume"
    ],
    "validation": {
      "typescript": "passed",
      "tested_files": [
        "src/app/profile/page.tsx"
      ]
    }
  },
  "outcome": {
    "implemented": [
      "Section chunking is now part of resume analysis workflow",
      "Keyword suggestions use live trend data instead of static proxy",
      "Missing keywords are surfaced in the profile UI",
      "Profile state is refreshed after analysis"
    ],
    "remaining_gaps": [
      "No explicit end-to-end automated resume analysis test coverage added yet",
      "LM prompt quality still depends on external LLM response consistency"
    ]
  }
}

```
### P5 
### P6 
### P7 
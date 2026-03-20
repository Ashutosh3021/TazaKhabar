# Roadmap: TazaKhabar

## Overview

TazaKhabar transforms the existing Next.js frontend from mock data to live HN intelligence. Phase 1 builds the scraping backend and connects feeds. Phase 2 adds AI-powered enrichment (summarization, contact extraction, ATS scoring, personalization). Phase 3 completes with trend predictions, semantic search, and notifications.

## Phases

- [ ] **Phase 1: Foundation & Backend** - Scraping infrastructure, database, job/news feeds, basic trends
- [ ] **Phase 2: Intelligence & Enrichment** - LLM integration, contact extraction, ATS scoring, personalization
- [ ] **Phase 3: Advanced & Polish** - Trend predictions, semantic search, notifications, hybrid search

## Phase Details

### Phase 1: Foundation & Backend
**Goal**: Backend scrapes HN and serves real data to frontend
**Depends on**: Nothing (first phase)
**Requirements**: DB-01 to DB-10, SCRP-01 to SCRP-08, INFR-01 to INFR-10, JOB-01 to JOB-07, NEWS-01 to NEWS-04, TRND-01 to TRND-08, FRESH-01 to FRESH-06, NOTF-01
**Success Criteria** (what must be TRUE):
  1. User visits Job Radar and sees live HN Who Is Hiring jobs (not mock data)
  2. User filters job feed by role (AI/ML, Frontend, Backend, Fullstack) and remote status
  3. User visits Feed and sees live HN Ask HN / Show HN / Top Stories content
  4. User visits Trends and sees real keyword frequency bars (booming/declining)
  5. Badge counter shows new jobs/news items between scraper runs
  6. Backend health check passes and CORS allows frontend access
**Plans**: 4 plans

Plans:
- [x] 01-01: Database & scraper foundation (DB + SCRP) — 3 tasks, Wave 1, independent
- [x] 01-02: Job feed & news feed APIs (JOB + NEWS) — 3 tasks, Wave 2, depends on 01-01
- [x] 01-03: Trends & freshness cycle (TRND + FRESH) — 3 tasks, Wave 3, depends on 01-02
- [x] 01-04: Infrastructure & notifications scaffold (INFR + NOTF-01) — 3 tasks, Wave 1, independent

### Phase 2: Intelligence & Enrichment
**Goal**: AI-powered quality and personalization layer
**Depends on**: Phase 1
**Requirements**: LLM-01 to LLM-11, QUAL-01 to QUAL-12, RESM-01 to RESM-12, PERS-01 to PERS-08, RAG-01 to RAG-09
**Success Criteria** (what must be TRUE):
  1. User sees AI-written summaries on news cards (2-3 sentences, job market focused)
  2. Job cards show email/apply links with ghost job badge when missing
  3. User uploads resume and receives ATS score (0-100) with critical fixes
  4. Job/news cards show match percentage based on user profile
  5. User sees personalized digest with top 5 matched news items
  6. User sees keyword suggestions based on resume + trending market
**Plans**: 3 plans

Plans:
- [ ] 02-01: LLM integration & news summarization (LLM + NEWS enhancement)
- [ ] 02-02: Contact extraction & ATS scoring (QUAL + RESM)
- [ ] 02-03: User profiles & personalization (PERS + RAG-01 to RAG-09)

### Phase 3: Advanced & Polish
**Goal**: Trend predictions, hybrid search, and notification matching
**Depends on**: Phase 2
**Requirements**: TRND-09 to TRND-11, RAG-10, NOTF-02 to NOTF-05
**Success Criteria** (what must be TRUE):
  1. User sees trend predictions with direction and confidence when 8+ weeks of data exists
  2. User receives job match alerts when new jobs match their profile
  3. User sees hybrid search results combining vector similarity with keyword matching
  4. Rate limit countdown timer visible when user exceeds daily LLM quota
**Plans**: 1 plan

Plans:
- [ ] 03-01: Predictions, notifications, and hybrid search

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Backend | 3/4 | In Progress|  |
| 2. Intelligence & Enrichment | 0/3 | Not started | - |
| 3. Advanced & Polish | 0/1 | Not started | - |

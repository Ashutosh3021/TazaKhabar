### → NOT COMPLETED
---

- ⌚ 16. Make job feed filters work with real data — Remote Only, Startup Only etc (partially done)
- [ ] 20. Build headline and heading maker for Feed screen using LLM
- [ ] 24. Build and train scikit-learn trend prediction model on accumulated data
- [ ] 25. Role boom and decline predictor output formatter for frontend charts
- [ ] 51. Deploy Next.js frontend to Vercel
- [ ] 52. Set up Supabase project and migrate schema from SQLite
- [ ] 53. Supabase Auth — Google, GitHub and Email login
- [ ] 54. Auth middleware on protected Next.js routes
- [ ] 55. Resume file storage moved to Supabase Storage bucket
- [ ] 56. User profile persistence moved to Supabase
- [ ] 57. Rate limit tracking moved to Supabase
- [ ] 58. Activate email notification system with Supabase
- [ ] 59. SQLite fully replaced and removed
- [ ] 60. Stripe setup and Pro feature gate logic
- [ ] 61. Stripe webhook handler
- [ ] 62. Pro upgrade prompt and payment flow in frontend
- [ ] 63. Final polish and removal of any remaining mock data
- [ ] 64. Full production testing and go live

---

### → COMPLETED (Phase 2)
---

- ✅ 17. Connect Gemini 1.5 Flash API
- ✅ 18. Build news summarization pipeline
- ✅ 19. Build trend narration pipeline — Observation block on Trends screen
- ✅ 26. Set up PyMuPDF for PDF resume parsing
- ✅ 27. Build resume text extraction and cleaning pipeline
- ✅ 28. Feed extracted resume text to Gemini for ATS scoring
- ✅ 29. Build keyword extraction from resume
- ✅ 30. Build suggested additions generator based on user role and market data
- ✅ 31. Daily token limit tracker — per user request counter
- ✅ 32. Rate limit timer — "Try again in X minutes" countdown on frontend
- ✅ 33. Build user profile storage locally
- ✅ 34. Build keyword matching between user profile and scraped jobs and news
- ✅ 35. Build content ranking and relevance scoring per user
- ✅ 36. Build personalized digest generation per user profile
- ✅ 37. Add Vector DB setup using SQLite locally for now
- ✅ 38. Build embedding pipeline — convert jobs, news and user profiles to vectors
- ✅ 39. Build RAG pipeline — semantic search for personalized digest and job matching
- ✅ 40. Replace mock digest data with real personalized data
- ✅ 41. Replace mock profile and ATS data with real data
- ✅ 42. Build email notification system code in parallel — dormant until Supabase
- ✅ 43. Add loading skeletons on all data screens
- ✅ 44. Add error states on all data screens
- ✅ 45. Add empty states when no data matches filters
- ✅ 46. Full end to end testing locally
- ✅ 47. Environment variables setup
- ✅ 48. Error logging setup
- ✅ 49. Basic API security and rate limiting on endpoints
- ✅ 50. Deploy FastAPI backend to Railway

---

### → COMPLETED (Phase 1)
---

- ✅ 1. Set up FastAPI project and folder structure
- ✅ 2. Set up local SQLite database with schema
- ✅ 3. Build HN scraper — Who Is Hiring thread
- ✅ 4. Build HN scraper — Ask HN stories
- ✅ 5. Build HN scraper — Show HN stories
- ✅ 6. Build HN scraper — Top Stories
- ✅ 7. Build the Report 1 and Report 2 scraper architecture with comparison logic
- ✅ 8. Auto schedule the scraper to run every 1 to 2 hours using APScheduler
- ✅ 9. Extract emails and apply links from scraped data using regex
- ✅ 10. Ghost job detection logic — flag jobs with no email and no apply link
- ✅ 11. Duplicate job detection logic — same company same role within active deadline window
- ✅ 12. Deadline extraction and unknown deadline handling
- ✅ 13. Fresh data badge counter logic — track what is new since last user visit
- ✅ 14. Connect FastAPI to Next.js frontend with CORS setup
- ✅ 15. Replace mock job feed data with real scraped data
- ✅ 16. Make job feed filters work with real data — Remote Only, Startup Only etc
- ✅ 21. Build keyword frequency counter across all scraped data
- ✅ 22. Build week over week percentage change calculator for trend charts
- ✅ 23. Replace mock trend graph data with real data

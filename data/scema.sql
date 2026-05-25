-- Supabase PostgreSQL schema for TazaKhabar
-- Uses pgcrypto for UUID generation and pgvector for embeddings.

create extension if not exists "pgcrypto";
create extension if not exists "vector";

-- Jobs scraped from Hacker News Who Is Hiring
create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  hn_item_id integer unique,
  title text not null,
  company text not null,
  location text not null default 'N/A',
  tags jsonb not null default '[]',
  email_contact text,
  apply_link text,
  is_ghost_job boolean not null default false,
  deadline text,
  posted_at timestamptz not null,
  scraped_at timestamptz not null default now(),
  report_version text not null default '2',
  cleaned_title text,
  cleaned_company text,
  role text,
  description text,
  processed boolean not null default false
);

create index if not exists idx_jobs_report_version on jobs(report_version);
create index if not exists idx_jobs_scraped_at on jobs(scraped_at);
create index if not exists idx_jobs_hn_item_id on jobs(hn_item_id);

-- News items from Ask HN, Show HN, and Top Stories
create table if not exists news (
  id uuid primary key default gen_random_uuid(),
  hn_item_id integer unique not null,
  type text not null,
  title text not null,
  url text,
  score integer not null default 0,
  comment_count integer not null default 0,
  summary text,
  summarized boolean not null default false,
  summarized_at timestamptz,
  scraped_at timestamptz not null default now(),
  report_version text not null default '2'
);

create index if not exists idx_news_type on news(type);
create index if not exists idx_news_report_version on news(report_version);
create index if not exists idx_news_scraped_at on news(scraped_at);

-- Weekly keyword trend tracking
create table if not exists trends (
  id uuid primary key default gen_random_uuid(),
  keyword text not null,
  count integer not null default 0,
  week_start timestamptz not null,
  week_end timestamptz not null,
  percentage_change double precision not null default 0.0
);

create unique index if not exists uq_trends_keyword_week on trends(keyword, week_start);
create index if not exists idx_trends_keyword on trends(keyword);
create index if not exists idx_trends_week_start on trends(week_start);

-- User profiles and resume intelligence
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  name text not null default 'Anonymous',
  email text,
  roles jsonb not null default '[]',
  experience_level text not null default 'I',
  resume_path text,
  resume_text text,
  ats_score integer,
  ats_critical_issues jsonb not null default '[]',
  ats_missing_keywords jsonb not null default '[]',
  ats_suggested_additions jsonb not null default '[]',
  last_analysis_at timestamptz,
  preferences jsonb not null default '{}' ,
  created_at timestamptz not null default now()
);

create index if not exists idx_users_email on users(email);

-- Daily rate limiting tracking
create table if not exists rate_limits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete set null,
  date date not null default current_date,
  request_count integer not null default 0,
  last_request_at timestamptz not null default now()
);

create unique index if not exists uq_rate_limits_user_date on rate_limits(user_id, date);
create index if not exists idx_rate_limits_user on rate_limits(user_id);

-- Scraper run reports and freshness metadata
create table if not exists reports (
  id uuid primary key default gen_random_uuid(),
  version text not null,
  run_at timestamptz not null default now(),
  items_collected integer not null default 0,
  new_items integer not null default 0,
  status text not null default 'running'
);

create index if not exists idx_reports_version on reports(version);
create index if not exists idx_reports_run_at on reports(run_at);

-- LLM-generated market observation text
create table if not exists observations (
  id uuid primary key default gen_random_uuid(),
  week_start timestamptz not null,
  text text not null,
  generated_at timestamptz not null default now()
);

create unique index if not exists uq_observations_week_start on observations(week_start);

-- Vector embeddings for jobs, news, user profiles
create table if not exists embeddings (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null,
  item_type text not null,
  embedding vector(384) not null,
  created_at timestamptz not null default now()
);

create unique index if not exists uq_embeddings_item on embeddings(item_id, item_type);
create index if not exists idx_embeddings_item_type on embeddings(item_type);

-- Notification queue for job-match alerts
create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  job_id uuid references jobs(id) on delete cascade,
  match_score integer not null default 0,
  status text not null default 'queued',
  created_at timestamptz not null default now(),
  sent_at timestamptz
);

create index if not exists idx_notifications_user on notifications(user_id);
create index if not exists idx_notifications_status on notifications(status);
create index if not exists idx_notifications_job on notifications(job_id);
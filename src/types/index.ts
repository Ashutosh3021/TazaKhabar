export type LocationType = "Remote" | "Hybrid" | "On-site";
export type HiringStatus = "HIRING_ACTIVE" | "SLOW_HIRING";

export interface Job {
  id: string;
  title: string;
  role: string; // matches Setup Step 1 role chips
  company: string;
  location: string;
  locationType: LocationType;
  companySize: string;
  salary: string;
  fundingStage: string;
  deadline?: string | null; // e.g. "25 DEC" or null
  skills: string[];
  postedDays: number;
  hiringStatus: HiringStatus;
  saved: boolean;
  applied?: boolean;
  experienceTier: "I" | "II" | "III" | "IV";
  emailAvailable?: boolean;
  applyAvailable?: boolean;
  is_ghost_job?: boolean; // QUAL-07: true if likely ghost job
  description?: string | null; // Job description from CSV
}

export interface Trend {
  skill: string;
  percentage: number; // 0-100
  weeklyChange: number; // +/- percentage points
}

export interface Signal {
  date: string; // e.g. "2026-03-14"
  headline: string;
  category: "HIRING" | "LAYOFF" | "FUNDING" | "SKILLS";
  source: string;
}

export interface DigestItem {
  id: string;
  headline: string;
  source: string;
  summary: string;
  category: "ALL" | "HIRING" | "LAYOFFS" | "FUNDING" | "SKILLS";
  readTime: string;
  featured?: boolean;
  match_percentage?: number;  // RAG similarity score 0-100
}

export interface UserProfile {
  roles: string[];
  experienceLevel: string; // I, II, III, IV
  email: string;
}

export interface ActiveFilters {
  roles: string[];
  location: LocationType | "";
  companySize: string[];
}


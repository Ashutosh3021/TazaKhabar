"use client";

import React, { createContext, useContext } from "react";
import type { ActiveFilters, UserProfile } from "@/types";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { jobs as mockJobs } from "@/lib/mockData"; // DEPRECATED — used only for default saved jobs fallback
import { fetchJobs, fetchNews } from "@/lib/api";

type TazaContextValue = {
  userProfile: UserProfile;
  setUserProfile: (profile: UserProfile) => void;

  savedJobs: string[];
  toggleSavedJob: (jobId: string) => void;
  setSavedJobs: (jobIds: string[]) => void;

  activeFilters: ActiveFilters;
  setActiveFilters: (next: ActiveFilters) => void;

  resetAll: () => void;

  // scrape/refresh state
  feedNewCount: number;
  radarNewCount: number;
  feedVersion: number;
  radarVersion: number;
  isFetchingFeed: boolean;
  isFetchingRadar: boolean;
  refreshFeed: () => void;
  refreshRadar: () => void;

  // resume intelligence gating
  resumeUploaded: boolean;
  setResumeUploaded: (v: boolean) => void;
};

const DEFAULT_PROFILE: UserProfile = {
  roles: [],
  experienceLevel: "",
  email: "",
};

const DEFAULT_SAVED_JOBS = mockJobs.filter((j) => j.saved).map((j) => j.id);

const DEFAULT_FILTERS: ActiveFilters = {
  roles: [],
  location: "",
  companySize: [],
};

const DEFAULT_SCRAPE = {
  feedNewCount: 12,
  radarNewCount: 12,
  feedVersion: 0,
  radarVersion: 0,
};

const TazaContext = createContext<TazaContextValue | null>(null);

export function TazaProvider({ children }: { children: React.ReactNode }) {
  const userStorage = useLocalStorage<UserProfile>(
    "tazakhabar:userProfile",
    DEFAULT_PROFILE,
  );
  const savedStorage = useLocalStorage<string[]>(
    "tazakhabar:savedJobs",
    DEFAULT_SAVED_JOBS,
  );
  const filtersStorage = useLocalStorage<ActiveFilters>(
    "tazakhabar:activeFilters",
    DEFAULT_FILTERS,
  );

  const scrapeStorage = useLocalStorage<{
    feedNewCount: number;
    radarNewCount: number;
    feedVersion: number;
    radarVersion: number;
  }>("tazakhabar:scrapeState", DEFAULT_SCRAPE);

  const [isFetchingFeed, setIsFetchingFeed] = React.useState(false);
  const [isFetchingRadar, setIsFetchingRadar] = React.useState(false);

  const refreshFeed = () => {
    if (isFetchingFeed) return;
    setIsFetchingFeed(true);
    scrapeStorage.setValue({
      ...scrapeStorage.value,
      feedNewCount: 0,
      feedVersion: scrapeStorage.value.feedVersion + 1,
    });
    // Loading state clears after fetch completes (pages call refreshFeed then fetchNews)
    window.setTimeout(() => setIsFetchingFeed(false), 2000);
  };

  const refreshRadar = () => {
    if (isFetchingRadar) return;
    setIsFetchingRadar(true);
    scrapeStorage.setValue({
      ...scrapeStorage.value,
      radarNewCount: 0,
      radarVersion: scrapeStorage.value.radarVersion + 1,
    });
    // Loading state clears after fetch completes (pages call refreshRadar then fetchJobs)
    window.setTimeout(() => setIsFetchingRadar(false), 2000);
  };

  const resumeUploadedStorage = useLocalStorage<boolean>(
    "tazakhabar:resumeUploaded",
    false,
  );

  const value: TazaContextValue = {
    userProfile: userStorage.value,
    setUserProfile: userStorage.setValue,

    savedJobs: savedStorage.value,
    toggleSavedJob: (jobId) => {
      const has = savedStorage.value.includes(jobId);
      savedStorage.setValue(has ? savedStorage.value.filter((id) => id !== jobId) : [...savedStorage.value, jobId]);
    },
    setSavedJobs: savedStorage.setValue,

    activeFilters: filtersStorage.value,
    setActiveFilters: filtersStorage.setValue,

    resetAll: () => {
      userStorage.setValue(DEFAULT_PROFILE);
      savedStorage.setValue([]);
      filtersStorage.setValue(DEFAULT_FILTERS);
      resumeUploadedStorage.setValue(false);
      scrapeStorage.setValue(DEFAULT_SCRAPE);
      try {
        window.localStorage.removeItem("tazakhabar:userProfile");
        window.localStorage.removeItem("tazakhabar:savedJobs");
        window.localStorage.removeItem("tazakhabar:activeFilters");
        window.localStorage.removeItem("tazakhabar:resumeUploaded");
        window.localStorage.removeItem("tazakhabar:scrapeState");
      } catch {
        // ignore
      }
    },

    // scrape + refresh
    feedNewCount: scrapeStorage.value.feedNewCount,
    radarNewCount: scrapeStorage.value.radarNewCount,
    feedVersion: scrapeStorage.value.feedVersion,
    radarVersion: scrapeStorage.value.radarVersion,
    isFetchingFeed,
    isFetchingRadar,
    refreshFeed,
    refreshRadar,

    // resume
    resumeUploaded: resumeUploadedStorage.value,
    setResumeUploaded: resumeUploadedStorage.setValue,
  };

  return <TazaContext.Provider value={value}>{children}</TazaContext.Provider>;
}

export function useTaza() {
  const ctx = useContext(TazaContext);
  if (!ctx) throw new Error("useTaza must be used within TazaProvider");
  return ctx;
}


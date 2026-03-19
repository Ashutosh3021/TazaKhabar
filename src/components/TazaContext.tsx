"use client";

import React, { createContext, useContext } from "react";
import type { ActiveFilters, UserProfile } from "@/types";
import { useLocalStorage } from "@/lib/useLocalStorage";
import { jobs as mockJobs } from "@/lib/mockData";

type TazaContextValue = {
  userProfile: UserProfile;
  setUserProfile: (profile: UserProfile) => void;

  savedJobs: string[];
  toggleSavedJob: (jobId: string) => void;
  setSavedJobs: (jobIds: string[]) => void;

  activeFilters: ActiveFilters;
  setActiveFilters: (next: ActiveFilters) => void;

  resetAll: () => void;
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
      try {
        window.localStorage.removeItem("tazakhabar:userProfile");
        window.localStorage.removeItem("tazakhabar:savedJobs");
        window.localStorage.removeItem("tazakhabar:activeFilters");
      } catch {
        // ignore
      }
    },
  };

  return <TazaContext.Provider value={value}>{children}</TazaContext.Provider>;
}

export function useTaza() {
  const ctx = useContext(TazaContext);
  if (!ctx) throw new Error("useTaza must be used within TazaProvider");
  return ctx;
}


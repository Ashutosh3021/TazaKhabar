/**
 * useSupabaseHealth Hook
 * 
 * Automatically checks Supabase connection on component mount
 * and logs the status to the browser console
 */

import { useEffect } from 'react';
import { checkSupabaseAndLog, checkSystemHealthAndLog } from './healthCheck';

/**
 * Hook to automatically check Supabase health on component mount
 * @param checkType - 'supabase' or 'system' (default: 'supabase')
 * @param delay - Delay in ms before checking (default: 1000)
 */
export function useHealthCheck(checkType: 'supabase' | 'system' = 'supabase', delay: number = 1000) {
  useEffect(() => {
    const timer = setTimeout(() => {
      if (checkType === 'system') {
        checkSystemHealthAndLog();
      } else {
        checkSupabaseAndLog();
      }
    }, delay);

    return () => clearTimeout(timer);
  }, [checkType, delay]);
}

/**
 * Hook to check Supabase health specifically
 * @param delay - Delay in ms before checking (default: 1000)
 */
export function useSupabaseHealthCheck(delay: number = 1000) {
  return useHealthCheck('supabase', delay);
}

/**
 * Hook to check full system health
 * @param delay - Delay in ms before checking (default: 1000)
 */
export function useSystemHealthCheck(delay: number = 1000) {
  return useHealthCheck('system', delay);
}

export default useSupabaseHealthCheck;

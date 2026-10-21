/**
 * usePyronitesHealth Hook
 *
 * Automatically checks the Pyronites connection on component mount
 * and logs the status to the browser console.
 */

import { useEffect } from 'react';
import { checkPyronitesAndLog, checkSystemHealthAndLog } from './healthCheck';

/**
 * Hook to automatically check backend health on component mount.
 * @param checkType - 'pyronites' or 'system' (default: 'pyronites')
 * @param delay - Delay in ms before checking (default: 1000)
 */
export function useHealthCheck(checkType: 'pyronites' | 'system' = 'pyronites', delay: number = 1000) {
  useEffect(() => {
    const timer = setTimeout(() => {
      if (checkType === 'system') {
        checkSystemHealthAndLog();
      } else {
        checkPyronitesAndLog();
      }
    }, delay);

    return () => clearTimeout(timer);
  }, [checkType, delay]);
}

/**
 * Hook to check the Pyronites connection specifically.
 */
export function usePyronitesHealthCheck(delay: number = 1000) {
  return useHealthCheck('pyronites', delay);
}

/**
 * Hook to check full system health.
 */
export function useSystemHealthCheck(delay: number = 1000) {
  return useHealthCheck('system', delay);
}

export default usePyronitesHealthCheck;

/**
 * Supabase Health Check Utility
 * 
 * Fetches and logs Supabase connection status to the browser console
 * Call this on page load to verify Supabase connectivity
 */

export interface SupabaseHealthStatus {
  storage: {
    configured: boolean;
    connected: boolean;
    error: string | null;
  };
  email: {
    configured: boolean;
    connected: boolean;
    error: string | null;
  };
  overall_status: 'connected' | 'partial' | 'disconnected' | 'not_configured' | 'error';
  timestamp: string;
}

export interface SystemHealthStatus {
  status: string;
  supabase: SupabaseHealthStatus;
  database: {
    configured: boolean;
    url_type: string;
  };
  timestamp: string;
}

/**
 * Get API base URL (same as in api.ts)
 */
function getApiBase(): string {
  const fromEnv = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:8000";
  }
  // Fallback for development without env var
  return "http://localhost:8000";
}

/**
 * Fetch Supabase health status from the backend
 */
export async function fetchSupabaseHealth(): Promise<SupabaseHealthStatus | null> {
  try {
    const apiBase = getApiBase();
    const url = `${apiBase}/health/supabase`;
    console.debug('[TazaKhabar] Fetching Supabase health from:', url);
    const response = await fetch(url);
    if (!response.ok) {
      const error = `Health check failed: ${response.status} ${response.statusText}. URL: ${url}`;
      console.error('[TazaKhabar]', error);
      console.warn('[TazaKhabar] Make sure NEXT_PUBLIC_API_URL is set correctly in Vercel (should be your Railway backend URL)');
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('[TazaKhabar] Failed to fetch Supabase health:', error);
    console.warn('[TazaKhabar] Make sure backend is running and NEXT_PUBLIC_API_URL is configured');
    return null;
  }
}

/**
 * Fetch detailed system health status from the backend
 */
export async function fetchSystemHealth(): Promise<SystemHealthStatus | null> {
  try {
    const apiBase = getApiBase();
    const url = `${apiBase}/health/detailed`;
    console.debug('[TazaKhabar] Fetching system health from:', url);
    const response = await fetch(url);
    if (!response.ok) {
      const error = `System health check failed: ${response.status} ${response.statusText}. URL: ${url}`;
      console.error('[TazaKhabar]', error);
      console.warn('[TazaKhabar] Make sure NEXT_PUBLIC_API_URL is set correctly in Vercel');
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('[TazaKhabar] Failed to fetch system health:', error);
    console.warn('[TazaKhabar] Make sure backend is running and NEXT_PUBLIC_API_URL is configured');
    return null;
  }
}

/**
 * Format and log Supabase health status to console with colors
 */
export function logSupabaseHealth(health: SupabaseHealthStatus): void {
  const timestamp = new Date(health.timestamp).toLocaleTimeString();
  
  // Color coding
  const colors = {
    connected: 'color: #22c55e; font-weight: bold;', // green
    partial: 'color: #eab308; font-weight: bold;',    // yellow
    disconnected: 'color: #ef4444; font-weight: bold;', // red
    not_configured: 'color: #f59e0b; font-weight: bold;', // amber
    error: 'color: #ef4444; font-weight: bold;', // red
  };

  const statusColor = colors[health.overall_status] || colors.error;
  const statusEmoji = {
    connected: '🟢',
    partial: '🟡',
    disconnected: '🔴',
    not_configured: '⚠️',
    error: '❌',
  }[health.overall_status] || '❓';

  console.log(
    `%c${statusEmoji} TazaKhabar Supabase Status [${timestamp}]`,
    statusColor
  );

  // Storage status
  const storageEmoji = health.storage.connected ? '✓' : '✗';
  const storageColor = health.storage.connected ? 'color: #22c55e;' : 'color: #ef4444;';
  console.log(
    `%c  ${storageEmoji} Storage: ${health.storage.configured ? (health.storage.connected ? 'Connected' : `Failed - ${health.storage.error}`) : 'Not configured'}`,
    storageColor
  );

  // Email status
  const emailEmoji = health.email.connected ? '✓' : '✗';
  const emailColor = health.email.connected ? 'color: #22c55e;' : 'color: #ef4444;';
  console.log(
    `%c  ${emailEmoji} Email: ${health.email.configured ? (health.email.connected ? 'Connected' : `Failed - ${health.email.error}`) : 'Not configured'}`,
    emailColor
  );

  // Overall status
  console.log(
    `%c  Overall: ${health.overall_status.toUpperCase()}`,
    statusColor
  );
}

/**
 * Format and log system health status to console
 */
export function logSystemHealth(health: SystemHealthStatus): void {
  const timestamp = new Date(health.timestamp).toLocaleTimeString();
  const healthEmoji = health.status === 'healthy' ? '✓' : '⚠';
  const healthColor = health.status === 'healthy' ? 'color: #22c55e; font-weight: bold;' : 'color: #f59e0b; font-weight: bold;';

  console.log(
    `%c${healthEmoji} TazaKhabar System Health [${timestamp}]`,
    healthColor
  );

  console.log(`%c  Status: ${health.status.toUpperCase()}`, healthColor);
  
  // Supabase info
  const supabaseEmoji = health.supabase.overall_status === 'connected' ? '✓' : '✗';
  const supabaseColor = health.supabase.overall_status === 'connected' ? 'color: #22c55e;' : 'color: #ef4444;';
  console.log(
    `%c  Supabase: ${supabaseEmoji} ${health.supabase.overall_status.toUpperCase()}`,
    supabaseColor
  );

  // Database info
  const dbColor = 'color: #3b82f6;';
  console.log(
    `%c  Database: ${health.database.url_type.toUpperCase()}`,
    dbColor
  );
}

/**
 * Check Supabase health and log to console (all-in-one function)
 */
export async function checkSupabaseAndLog(): Promise<void> {
  console.log('%c🔍 Checking TazaKhabar Supabase connection...', 'color: #6366f1; font-weight: bold;');
  const health = await fetchSupabaseHealth();
  if (health) {
    logSupabaseHealth(health);
  }
}

/**
 * Check system health and log to console (all-in-one function)
 */
export async function checkSystemHealthAndLog(): Promise<void> {
  console.log('%c🔍 Checking TazaKhabar system health...', 'color: #6366f1; font-weight: bold;');
  const health = await fetchSystemHealth();
  if (health) {
    logSystemHealth(health);
    
    // Also log Supabase details
    console.log('%c--- Supabase Details ---', 'color: #8b5cf6; font-weight: bold;');
    logSupabaseHealth(health.supabase);
  }
}

/**
 * Display current API configuration for debugging
 */
export function showApiConfig(): void {
  const apiBase = getApiBase();
  const isProduction = process.env.NODE_ENV === 'production';
  const hasEnvVar = !!process.env.NEXT_PUBLIC_API_URL;

  console.group('%c🔧 TazaKhabar API Configuration', 'color: #f59e0b; font-weight: bold; font-size: 14px;');
  
  console.log('%cEnvironment:', 'font-weight: bold;');
  console.log(`  NODE_ENV: ${process.env.NODE_ENV}`);
  console.log(`  NEXT_PUBLIC_API_URL: ${hasEnvVar ? process.env.NEXT_PUBLIC_API_URL : '(NOT SET)'}`);
  
  console.log('%cResolved Configuration:', 'font-weight: bold;');
  const configColor = hasEnvVar ? 'color: #22c55e;' : (isProduction ? 'color: #ef4444;' : 'color: #eab308;');
  console.log(`%c  API Base URL: ${apiBase}`, configColor);
  console.log(`  Status: ${hasEnvVar ? '✓ Set' : (isProduction ? '✗ NOT SET (will fail in production)' : '⚠️ Using local fallback')}`);
  
  console.log('%cTesting Connection:', 'font-weight: bold;');
  console.log(`  Try calling: tazaCheckSupabase()`);
  console.log(`  Or manually: fetch('${apiBase}/health/supabase').then(r => console.log(r.status, r.url))`);
  
  if (!hasEnvVar && isProduction) {
    console.warn(
      '%c⚠️ WARNING: NEXT_PUBLIC_API_URL not set in production!\n' +
      'The health check will fail. Set this environment variable in Vercel:\n' +
      '  NEXT_PUBLIC_API_URL = https://your-railway-backend.up.railway.app',
      'color: #ef4444; font-weight: bold; font-size: 12px;'
    );
  }
  
  console.groupEnd();
}

/**
 * Add a global function to check health from browser console
 * Usage: window.tazaCheckHealth() or window.tazaCheckSupabase()
 */
if (typeof window !== 'undefined') {
  (window as any).tazaCheckSupabase = checkSupabaseAndLog;
  (window as any).tazaCheckHealth = checkSystemHealthAndLog;
  (window as any).tazaShowConfig = showApiConfig;
  
  console.log(
    '%c💡 TazaKhabar Health Commands Available:',
    'color: #10b981; font-weight: bold;'
  );
  console.log('   👉 Type "tazaCheckSupabase()" to check Supabase status');
  console.log('   👉 Type "tazaCheckHealth()" to check full system health');
  console.log('   👉 Type "tazaShowConfig()" to show API configuration');
}

export default {
  fetchSupabaseHealth,
  fetchSystemHealth,
  logSupabaseHealth,
  logSystemHealth,
  checkSupabaseAndLog,
  checkSystemHealthAndLog,
  showApiConfig,
};

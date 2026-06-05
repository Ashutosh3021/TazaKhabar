#!/usr/bin/env python3
"""
TazaKhabar Supabase Health Check Diagnostic Tool

Usage:
    python supabase_diagnostic.py          # Run all checks
    python supabase_diagnostic.py --quick  # Quick checks only
    python supabase_diagnostic.py --env    # Show .env configuration
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any
import httpx

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(text: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{Colors.RESET}\n")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

def load_env_file(env_path: str = None) -> Dict[str, str]:
    """Load environment variables from .env file"""
    if env_path is None:
        # Try common locations
        candidates = [
            Path(__file__).parent / 'backend' / '.env',
            Path(__file__).parent / '.env',
            Path.cwd() / 'backend' / '.env',
            Path.cwd() / '.env',
        ]
        
        for path in candidates:
            if path.exists():
                env_path = path
                break
        
        if env_path is None:
            return {}
    
    env_path = Path(env_path)
    if not env_path.exists():
        return {}
    
    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars

def check_env_configuration(env_vars: Dict[str, str]) -> bool:
    """Check if required environment variables are set"""
    print_header("Environment Configuration Check")
    
    required = [
        'SUPABASE_URL',
        'SUPABASE_SERVICE_ROLE_KEY',
        'SUPABASE_STORAGE_BUCKET',
    ]
    
    all_good = True
    for var in required:
        if var in env_vars and env_vars[var]:
            value = env_vars[var]
            # Mask sensitive values
            if 'KEY' in var or 'PASSWORD' in var:
                display_value = value[:20] + '...' if len(value) > 20 else value
            else:
                display_value = value
            print_success(f"{var} = {display_value}")
        else:
            print_error(f"{var} is missing or empty")
            all_good = False
    
    # Check optional email config
    email_vars = ['EMAIL_SMTP_HOST', 'EMAIL_SMTP_PORT', 'EMAIL_SMTP_USER', 
                  'EMAIL_SMTP_PASSWORD', 'SUPABASE_EMAIL_FROM']
    email_configured = all(env_vars.get(var) for var in email_vars)
    
    if email_configured:
        print_success("Email service is configured")
    else:
        print_warning("Email service is NOT configured (optional)")
    
    return all_good

async def test_supabase_storage_bucket(env_vars: Dict[str, str]) -> bool:
    """Test Supabase storage bucket connectivity"""
    print_header("Supabase Storage Bucket Test")
    
    supabase_url = env_vars.get('SUPABASE_URL', '').rstrip('/')
    service_role_key = env_vars.get('SUPABASE_SERVICE_ROLE_KEY', '')
    storage_bucket = env_vars.get('SUPABASE_STORAGE_BUCKET', '')
    
    if not all([supabase_url, service_role_key, storage_bucket]):
        print_error("Missing required configuration (URL, Key, or Bucket)")
        return False
    
    print_info(f"Testing bucket: {storage_bucket}")
    print_info(f"Supabase URL: {supabase_url}")
    
    # Test 1: List buckets endpoint
    print("\n[1/2] Testing bucket list endpoint...")
    url = f"{supabase_url}/storage/v1/buckets"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
        
        if response.status_code == 200:
            print_success(f"Bucket list endpoint accessible (HTTP {response.status_code})")
            buckets = response.json()
            bucket_names = [b.get('name', 'unknown') for b in buckets]
            print_info(f"Buckets found: {', '.join(bucket_names)}")
            
            if storage_bucket in bucket_names:
                print_success(f"Bucket '{storage_bucket}' EXISTS")
            else:
                print_error(f"Bucket '{storage_bucket}' NOT FOUND")
                print_warning(f"Available buckets: {', '.join(bucket_names)}")
        else:
            print_error(f"Bucket list failed (HTTP {response.status_code})")
            print_warning(f"Response: {response.text[:200]}")
    
    except httpx.ConnectError as e:
        print_error(f"Connection error: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        return False
    
    # Test 2: Direct bucket HEAD request
    print("\n[2/2] Testing direct bucket HEAD request...")
    url = f"{supabase_url}/storage/v1/buckets/{storage_bucket}"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.head(url, headers=headers)
        
        if response.status_code in (200, 204):
            print_success(f"Bucket accessible via HEAD request (HTTP {response.status_code})")
            return True
        elif response.status_code == 404:
            print_error(f"Bucket not found (HTTP 404)")
            print_warning("The bucket may not exist or the URL is incorrect")
            return False
        elif response.status_code in (401, 403):
            print_error(f"Authentication failed (HTTP {response.status_code})")
            print_warning("Service role key may be invalid or have insufficient permissions")
            return False
        else:
            print_error(f"Unexpected status code: {response.status_code}")
            return False
    
    except Exception as e:
        print_error(f"HEAD request failed: {str(e)}")
        return False

async def test_backend_health_endpoint(backend_url: str) -> bool:
    """Test backend health endpoint"""
    print_header("Backend Health Endpoint Test")
    
    if not backend_url:
        print_warning("Backend URL not specified, skipping")
        return None
    
    url = f"{backend_url.rstrip('/')}/health/supabase"
    print_info(f"Testing: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
        
        if response.status_code == 200:
            print_success(f"Endpoint accessible (HTTP 200)")
            data = response.json()
            print("\nResponse:")
            print(json.dumps(data, indent=2))
            
            storage_status = data.get('storage', {})
            if storage_status.get('connected'):
                print_success("Storage: Connected")
            else:
                error = storage_status.get('error', 'Unknown error')
                print_error(f"Storage: Disconnected - {error}")
            
            return storage_status.get('connected', False)
        else:
            print_error(f"Endpoint returned HTTP {response.status_code}")
            return False
    
    except httpx.ConnectError:
        print_error(f"Cannot connect to backend at {backend_url}")
        print_warning("Make sure the backend is running")
        return None
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None

async def test_email_configuration(env_vars: Dict[str, str]) -> bool:
    """Test email SMTP configuration"""
    print_header("Email Configuration Check")
    
    smtp_host = env_vars.get('EMAIL_SMTP_HOST', '')
    smtp_user = env_vars.get('EMAIL_SMTP_USER', '')
    smtp_password = env_vars.get('EMAIL_SMTP_PASSWORD', '')
    
    if not all([smtp_host, smtp_user, smtp_password]):
        print_warning("Email not configured (all SMTP fields empty)")
        return None
    
    print_info(f"SMTP Host: {smtp_host}")
    print_info(f"SMTP User: {smtp_user}")
    
    try:
        import smtplib
        import ssl
        
        smtp_port = int(env_vars.get('EMAIL_SMTP_PORT', '587'))
        use_tls = env_vars.get('EMAIL_SMTP_USE_TLS', 'true').lower() == 'true'
        
        context = ssl.create_default_context()
        
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls(context=context)
            smtp.login(smtp_user, smtp_password)
        
        print_success("SMTP connection successful")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print_error("SMTP authentication failed (invalid credentials)")
        return False
    except smtplib.SMTPException as e:
        print_error(f"SMTP error: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def show_env_configuration(env_vars: Dict[str, str]):
    """Display current .env configuration"""
    print_header("Current .env Configuration")
    
    important_vars = [
        ('SUPABASE_URL', 'Supabase Project URL'),
        ('SUPABASE_SERVICE_ROLE_KEY', 'Service Role Key'),
        ('SUPABASE_STORAGE_BUCKET', 'Storage Bucket Name'),
        ('SUPABASE_EMAIL_FROM', 'Email From Address'),
        ('EMAIL_SMTP_HOST', 'SMTP Host'),
        ('EMAIL_SMTP_PORT', 'SMTP Port'),
        ('EMAIL_SMTP_USER', 'SMTP User'),
        ('EMAIL_SMTP_USE_TLS', 'Use TLS'),
        ('NEXT_PUBLIC_API_URL', 'Frontend API URL'),
    ]
    
    for var, description in important_vars:
        value = env_vars.get(var, '<NOT SET>')
        
        # Mask sensitive values
        if 'KEY' in var or 'PASSWORD' in var:
            if value != '<NOT SET>' and len(value) > 20:
                display_value = value[:20] + '... (masked)'
            else:
                display_value = value
        else:
            display_value = value
        
        status = "✓" if value != '<NOT SET>' else "✗"
        print(f"{status} {description:.<40} {display_value}")

async def main():
    """Run all diagnostics"""
    args = sys.argv[1:]
    
    print(f"\n{Colors.BOLD}TazaKhabar Supabase Health Check Diagnostic{Colors.RESET}")
    print(f"Started at: {__import__('datetime').datetime.now().isoformat()}\n")
    
    # Load environment
    env_vars = load_env_file()
    if not env_vars:
        print_warning("Could not load .env file - using system environment variables")
        env_vars = dict(os.environ)
    
    # Show configuration if requested
    if '--env' in args:
        show_env_configuration(env_vars)
        return
    
    # Run checks
    results = {
        'env_config': False,
        'storage_bucket': False,
        'backend_health': None,
        'email_config': None,
    }
    
    try:
        # 1. Check environment configuration
        results['env_config'] = check_env_configuration(env_vars)
        
        if not '--quick' in args:
            # 2. Test Supabase storage bucket
            results['storage_bucket'] = await test_supabase_storage_bucket(env_vars)
            
            # 3. Test backend health endpoint (if URL provided)
            backend_url = os.getenv('TAZA_API_URL') or env_vars.get('NEXT_PUBLIC_API_URL') or 'http://localhost:8000'
            if '--skip-backend' not in args:
                results['backend_health'] = await test_backend_health_endpoint(backend_url)
            
            # 4. Test email configuration
            results['email_config'] = await test_email_configuration(env_vars)
        
        # Print summary
        print_header("Diagnostic Summary")
        print(json.dumps(results, indent=2, default=str))
        
        # Overall status
        print_header("Overall Status")
        
        if results['env_config'] and results['storage_bucket']:
            print_success("All critical systems are configured and connected!")
            sys.exit(0)
        elif results['env_config'] and not results['storage_bucket']:
            print_error("Environment is configured but storage bucket is not accessible")
            print_warning("See SUPABASE_FIX_GUIDE.md Step 2 for bucket creation")
            sys.exit(1)
        else:
            print_error("Environment configuration is incomplete")
            print_warning("See SUPABASE_FIX_GUIDE.md for setup instructions")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print_warning("Diagnostic cancelled")
        sys.exit(130)
    except Exception as e:
        print_error(f"Diagnostic failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())

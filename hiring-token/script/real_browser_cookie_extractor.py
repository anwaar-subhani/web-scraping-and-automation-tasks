#!/usr/bin/env python3
"""
Real Browser Cookie Extractor with Proxy Support
Uses Playwright to open YOPmail in real browser through proxies to get fresh cookies
"""

import json
import time
import random
import os
from playwright.sync_api import sync_playwright

def load_proxies(proxies_file: str = "proxies.txt"):
    """Load proxies from file"""
    proxies = []
    try:
        if os.path.exists(proxies_file):
            with open(proxies_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 4:
                            proxy = {
                                'host': parts[0],
                                'port': int(parts[1]),
                                'username': parts[2],
                                'password': parts[3]
                            }
                            proxies.append(proxy)
            print(f"📡 Loaded {len(proxies)} proxies")
        else:
            print(f"⚠️ Proxies file not found: {proxies_file}")
    except Exception as e:
        print(f"❌ Error loading proxies: {e}")
    return proxies

def get_fresh_cookies_with_proxy(proxy=None):
    """Get fresh cookies using real browser with optional proxy"""
    print("🚀 Starting fresh cookie extraction with real browser...")
    
    try:
        with sync_playwright() as p:
            # Browser launch args
            launch_args = [
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-automation',
                '--disable-infobars',
                '--disable-dev-tools',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps',
                '--disable-popup-blocking',
                '--disable-translate',
                '--disable-background-networking',
                '--disable-sync',
                '--metrics-recording-only',
                '--no-report-upload',
                '--disable-logging',
                '--disable-gpu-logging',
                '--silent',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            
            # Launch browser
            browser = p.chromium.launch(headless=False, args=launch_args)
            
            # Context options
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'locale': 'en-US',
                'timezone_id': 'America/New_York',
                'permissions': ['geolocation'],
                'extra_http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                },
                'java_script_enabled': True,
                'bypass_csp': True,
                'ignore_https_errors': True,
            }
            
            # Add proxy if provided
            if proxy:
                proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
                context_options['proxy'] = {
                    'server': proxy_url
                }
                print(f"🌐 Using proxy: {proxy['host']}:{proxy['port']}")
            else:
                print("🌐 Using direct connection (no proxy)")
            
            # Create context
            context = browser.new_context(**context_options)
            
            # Add stealth scripts
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                window.chrome = { runtime: {} };
                Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
                Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
                Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
                Object.defineProperty(screen, 'height', { get: () => 1080 });
                Object.defineProperty(screen, 'width', { get: () => 1920 });
                Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', { value: function(){ return { timeZone: 'America/New_York' }; } });
            """)
            
            page = context.new_page()
            
            # Try to visit YOPmail
            print("🌐 Visiting YOPmail...")
            try:
                # First try main page
                page.goto("https://yopmail.com/", wait_until='networkidle', timeout=30000)
                print("✅ Main page loaded successfully")
                time.sleep(3)
                
                # Then try English version
                page.goto("https://yopmail.com/en/", wait_until='networkidle', timeout=30000)
                print("✅ English page loaded successfully")
                time.sleep(3)
                
            except Exception as e:
                print(f"⚠️ Page load failed: {e}")
                # Try with different approach
                try:
                    page.goto("https://yopmail.com/en/", wait_until='domcontentloaded', timeout=30000)
                    print("✅ English page loaded (alternative method)")
                    time.sleep(5)
                except Exception as e2:
                    print(f"❌ All page load attempts failed: {e2}")
                    browser.close()
                    return None
            
            # Extract cookies
            print("🍪 Extracting cookies...")
            cookies = context.cookies()
            
            # Filter YOPmail cookies
            yopmail_cookies = {}
            print(f"🍪 Total cookies found: {len(cookies)}")
            for cookie in cookies:
                print(f"   Cookie: {cookie['name']} = {cookie['value'][:30]}... (domain: {cookie.get('domain', 'N/A')})")
                if 'yopmail.com' in cookie.get('domain', ''):
                    yopmail_cookies[cookie['name']] = cookie['value']
                    print(f"   ✅ YOPmail cookie: {cookie['name']} = {cookie['value'][:50]}...")
            
            if yopmail_cookies:
                print(f"✅ Successfully extracted {len(yopmail_cookies)} cookies")
                
                # Save cookies to file
                cookie_data = {
                    'cookies': yopmail_cookies,
                    'timestamp': time.time(),
                    'source': 'real_browser_with_proxy' if proxy else 'real_browser_direct',
                    'proxy': f"{proxy['host']}:{proxy['port']}" if proxy else 'direct'
                }
                
                filename = f'fresh_cookies_{int(time.time())}.json'
                with open(filename, 'w') as f:
                    json.dump(cookie_data, f, indent=2)
                
                print(f"💾 Saved fresh cookies to '{filename}'")
                
                # Test cookies with requests
                test_cookies_with_requests(yopmail_cookies)
                
                browser.close()
                return yopmail_cookies
            else:
                print("❌ No YOPmail cookies found")
                browser.close()
                return None
                
    except Exception as e:
        print(f"❌ Error getting fresh cookies: {e}")
        return None

def test_cookies_with_requests(cookies):
    """Test the extracted cookies with requests library"""
    import requests
    
    try:
        session = requests.Session()
        
        # Set cookies
        for name, value in cookies.items():
            session.cookies.set(name, value, domain='.yopmail.com')
        
        # Test with a simple request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = session.get("https://yopmail.com/en/", headers=headers, timeout=15)
        
        if response.status_code == 200:
            print("✅ Cookies work with requests library!")
            print(f"   Response length: {len(response.text)} characters")
        else:
            print(f"❌ Cookies test failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing cookies: {e}")

def try_multiple_proxies():
    """Always use direct connection for cookie extraction"""
    print("🌐 Using direct connection for cookie extraction...")
    return get_fresh_cookies_with_proxy()

def main():
    """Main function"""
    print("🧪 Real Browser Cookie Extractor (Direct Connection)")
    print("=" * 60)
    
    print("Extracting fresh cookies using direct connection...")
    cookies = get_fresh_cookies_with_proxy()
    
    if cookies:
        print("\n🎉 SUCCESS: Fresh cookies extracted!")
        print("Cookies that can be used:")
        for name, value in cookies.items():
            print(f"  {name}: {value[:30]}...")
    else:
        print("\n❌ FAILED: Could not extract fresh cookies")

if __name__ == "__main__":
    main()


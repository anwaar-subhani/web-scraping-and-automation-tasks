#!/usr/bin/env python3
"""
Amazon Login Test - Synchronous Version (Playwright sync API)
"""

import csv
import random
import json
import os
import shutil
import time
import signal
import sys
from datetime import datetime
from typing import Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from yopmail_wrapper import YOPmailWrapper
from real_browser_cookie_extractor import get_fresh_cookies_with_proxy, try_multiple_proxies
import json as _json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
with open(CONFIG_PATH, 'r') as _cfgf:
    _cfg = _json.load(_cfgf)
    CYCLE_WAIT_MINUTES = int(_cfg.get('CYCLE_WAIT_MINUTES', 3))
    THREADS = int(_cfg.get('THREADS', 1))


def get_fresh_yopmail_cookies():
    """Get fresh cookies using real_browser_cookie_extractor.py with direct connection"""
    print("🍪 Getting fresh YOPmail cookies using real browser extractor...")
    
    try:
        # Always use direct connection (no proxies)
        cookies = try_multiple_proxies()
        
        if cookies:
            print(f"✅ Extracted {len(cookies)} fresh cookies using real browser")
            return cookies
        else:
            print("❌ Real browser cookie extraction failed")
            return None
                
    except Exception as e:
        print(f"❌ Cookie extraction error: {e}")
        return None


def update_yopmail_cookies():
    """Update YOPmail wrapper with fresh cookies"""
    fresh_cookies = get_fresh_yopmail_cookies()
    
    if fresh_cookies:
        # Update the YOPmailWrapper to use fresh cookies
        try:
            # Save fresh cookies to file for YOPmailWrapper to use
            cookie_data = {
                'cookies': fresh_cookies,
                'timestamp': time.time(),
                'source': 'fresh_browser_session'
            }
            
            cookie_file = os.path.join(os.path.dirname(__file__), 'fresh_yopmail_cookies.json')
            with open(cookie_file, 'w') as f:
                json.dump(cookie_data, f, indent=2)
            
            print("💾 Fresh cookies saved for YOPmailWrapper")
            return True
            
        except Exception as e:
            print(f"❌ Error saving fresh cookies: {e}")
            return False
    else:
        print("⚠️ Using existing cookies (fresh extraction failed)")
        return False


def cleanup_pycache():
    """Clean up __pycache__ folders on every run"""
    try:
        pycache_path = os.path.join(os.path.dirname(__file__), '__pycache__')
        if os.path.exists(pycache_path):
            shutil.rmtree(pycache_path)

        parent_pycache = os.path.join(os.path.dirname(os.path.dirname(__file__)), '__pycache__')
        if os.path.exists(parent_pycache):
            shutil.rmtree(parent_pycache)
    except Exception:
        pass


def cleanup_otp_history():
    """Clean up expired OTP entries from history file"""
    try:
        otp_history_file = os.path.join(os.path.dirname(__file__), 'otp_history.json')
        if not os.path.exists(otp_history_file):
            return

        with open(otp_history_file, 'r') as f:
            history = json.load(f)

        current_time = time.time()
        expiry_timestamp = current_time - (3 * 60)

        cleaned_history = {}
        for email, otp_list in history.items():
            cleaned_otps = [otp for otp in otp_list if otp.get('timestamp', 0) > expiry_timestamp]
            if cleaned_otps:
                cleaned_history[email] = cleaned_otps

        with open(otp_history_file, 'w') as f:
            json.dump(cleaned_history, f, indent=2)
    except Exception:
        try:
            otp_history_file = os.path.join(os.path.dirname(__file__), 'otp_history.json')
            if os.path.exists(otp_history_file):
                os.remove(otp_history_file)
        except Exception:
            pass


def cleanup_cookie_files():
    """Clean up old cookie JSON files to ensure fresh cookies are used"""
    try:
        script_dir = os.path.dirname(__file__)
        
        # Get all files in the script directory
        all_files = os.listdir(script_dir)
        
        # Define patterns for cookie files to clean up
        cookie_patterns = [
            'fresh_cookies_',
            'fresh_yopmail_cookies.json'
        ]
        
        cleaned_count = 0
        for file_name in all_files:
            # Check if file matches any cookie pattern
            should_clean = False
            for pattern in cookie_patterns:
                if file_name.startswith(pattern) and file_name.endswith('.json'):
                    should_clean = True
                    break
            
            if should_clean:
                file_path = os.path.join(script_dir, file_name)
                try:
                    os.remove(file_path)
                    print(f"🗑️ Cleaned up old cookie file: {file_name}")
                    cleaned_count += 1
                except Exception as e:
                    print(f"⚠️ Could not remove {file_name}: {e}")
        
        if cleaned_count == 0:
            print("ℹ️ No old cookie files found to clean up")
        else:
            print(f"✅ Cleaned up {cleaned_count} cookie file(s)")
            
    except Exception as e:
        print(f"⚠️ Error during cookie cleanup: {e}")




# Globals for shutdown/cleanup
browser_instance = None
playwright_instance = None
shutdown = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown, browser_instance, playwright_instance
    shutdown = True
    try:
        if browser_instance:
            browser_instance.close()
    except Exception:
        pass
    try:
        if playwright_instance:
            playwright_instance.stop()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def extract_authorization_token(page, email):
    """Fast token extraction with immediate return when found"""
    print(f"🔍 Extracting token for {email}")
    
    authorization_token = None
    token_found = False
    
    def handle_request(request):
        nonlocal authorization_token, token_found
        url = request.url
        
        # Check for authorize requests
        if 'authorize' in url and 'countryCode=US' in url:
            print(f"📡 Found authorize request: {url}")
            headers = request.headers
            if 'authorization' in headers:
                authorization_token = headers['authorization']
                token_found = True
                print(f"✅ Token found in request headers: {authorization_token[:50]}...")
    
    def handle_response(response):
        nonlocal authorization_token, token_found
        url = response.url
        if 'authorize' in url and 'countryCode=US' in url:
            print(f"📡 Found authorize response: {url}")
            try:
                headers = response.headers
                if 'authorization' in headers:
                    authorization_token = headers['authorization']
                    token_found = True
                    print(f"✅ Token found in response headers: {authorization_token[:50]}...")
            except Exception as e:
                print(f"⚠️ Error reading response headers: {e}")
    
    # Listen for requests and responses
    page.on('request', handle_request)
    page.on('response', handle_response)
    
    # Method 1: Page refresh to trigger auth requests
    print("🔄 Method 1: Reloading page to trigger auth requests...")
    try:
        page.reload(wait_until='networkidle')
    except PlaywrightTimeoutError:
        print("⏰ Page reload timeout")
        pass
    
    # Check if token was found during refresh
    if token_found and authorization_token:
        print(f"✅ Token found during reload: {authorization_token[:50]}...")
        return authorization_token
    
    # Wait a short time for auth headers
    print("⏳ Waiting 2 seconds for auth headers...")
    page.wait_for_timeout(2000)
    
    # Check again if token was found
    if token_found and authorization_token:
        print(f"✅ Token found after wait: {authorization_token[:50]}...")
        return authorization_token
    
    # Method 2: Try clicking to trigger more auth requests
    print("🔄 Method 2: Clicking body to trigger network...")
    try:
        page.click('body')
        page.wait_for_timeout(1000)
        
        # Check if token was found during click
        if token_found and authorization_token:
            print(f"✅ Token found during click: {authorization_token[:50]}...")
            return authorization_token
    except Exception as e:
        print(f"⚠️ Error clicking body: {e}")
    
    # Method 3: Try navigating to a protected page to trigger auth
    print("🔄 Method 3: Navigating to dashboard to trigger auth...")
    try:
        page.goto("https://hiring.amazon.com/dashboard", wait_until='networkidle', timeout=5000)
        
        # Check if token was found during navigation
        if token_found and authorization_token:
            print(f"✅ Token found during navigation: {authorization_token[:50]}...")
            return authorization_token
        
        page.wait_for_timeout(1000)
        
        # Check if we got redirected back to login (means not authenticated)
        current_url = page.url
        print(f"📍 Current URL after dashboard: {current_url}")
        if 'login' in current_url.lower() or 'auth' in current_url.lower():
            print("🔄 Redirected to login, reloading page...")
            try:
                page.reload(wait_until='networkidle')
                page.wait_for_timeout(1000)
                
                # Check if token was found during refresh
                if token_found and authorization_token:
                    print(f"✅ Token found during redirect reload: {authorization_token[:50]}...")
                    return authorization_token
            except Exception as e:
                print(f"⚠️ Error during redirect reload: {e}")
        else:
            print("✅ Successfully navigated to dashboard")
    except Exception as e:
        print(f"⚠️ Error navigating to dashboard: {e}")
        # Try page refresh as fallback
        try:
            print("🔄 Fallback: Reloading page...")
            page.reload(wait_until='networkidle')
            page.wait_for_timeout(1000)
            
            # Check if token was found during fallback refresh
            if token_found and authorization_token:
                print(f"✅ Token found during fallback reload: {authorization_token[:50]}...")
                return authorization_token
        except Exception as e2:
            print(f"⚠️ Error during fallback reload: {e2}")
    
    # Final wait only if token not found yet
    if not token_found:
        print("⏳ Final wait (3 seconds) for auth headers...")
        page.wait_for_timeout(3000)
    
    # Comprehensive fallback: try multiple sources for tokens
    if not authorization_token:
        print("🔄 Fallback: Checking localStorage/sessionStorage/window...")
        try:
            # Try localStorage/sessionStorage with more token names
            token = page.evaluate("""
                () => {
                    // Check localStorage
                    let token = localStorage.getItem('authorization') || 
                               localStorage.getItem('auth_token') ||
                               localStorage.getItem('accessToken') ||
                               localStorage.getItem('idToken') ||
                               localStorage.getItem('refreshToken') ||
                               localStorage.getItem('token') ||
                               localStorage.getItem('authToken') ||
                               localStorage.getItem('jwt') ||
                               localStorage.getItem('bearer');
                    
                    if (token) return token;
                    
                    // Check sessionStorage
                    token = sessionStorage.getItem('authorization') || 
                           sessionStorage.getItem('auth_token') ||
                           sessionStorage.getItem('accessToken') ||
                           sessionStorage.getItem('idToken') ||
                           sessionStorage.getItem('refreshToken') ||
                           sessionStorage.getItem('token') ||
                           sessionStorage.getItem('authToken') ||
                           sessionStorage.getItem('jwt') ||
                           sessionStorage.getItem('bearer');
                    
                    if (token) return token;
                    
                    // Check window object
                    if (window.authorization) return window.authorization;
                    if (window.accessToken) return window.accessToken;
                    if (window.idToken) return window.idToken;
                    if (window.refreshToken) return window.refreshToken;
                    if (window.token) return window.token;
                    if (window.authToken) return window.authToken;
                    if (window.jwt) return window.jwt;
                    if (window.bearer) return window.bearer;
                    
                    return null;
                }
            """)
            if token:
                authorization_token = token
                print(f"✅ Token found in storage: {authorization_token[:50]}...")
        except Exception as e:
            print(f"⚠️ Error checking storage: {e}")
    
    # URL check with more token types
    if not authorization_token:
        print("🔄 Fallback: Checking URL for tokens...")
        try:
            current_url = page.url
            print(f"📍 Current URL: {current_url}")
            
            # Check for various token types in URL
            token_patterns = ['accessToken=', 'idToken=', 'refreshToken=', 'authToken=', 'token=', 'jwt=']
            for pattern in token_patterns:
                if pattern in current_url:
                    print(f"🔍 Found token pattern in URL: {pattern}")
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(current_url)
                    query_params = urllib.parse.parse_qs(parsed_url.fragment)
                    token_name = pattern.replace('=', '')
                    if token_name in query_params:
                        authorization_token = query_params[token_name][0]
                        print(f"✅ Token found in URL: {authorization_token[:50]}...")
                        break
        except Exception as e:
            print(f"⚠️ Error checking URL: {e}")
    
    if authorization_token:
        print(f"🎉 Final token result: {authorization_token[:50]}...")
    else:
        print("❌ No token found through any method")
    
    return authorization_token


def save_token_to_csv(email, token):
    """Save token to CSV file - update existing row or add new one"""
    try:
        timestamp = datetime.now().isoformat()
        csv_file = '../output/tokens.csv'
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)
        
        # Read existing data
        rows = {}
        if os.path.exists(csv_file):
            try:
                with open(csv_file, 'r', newline='', encoding='utf-8') as rf:
                    reader = csv.DictReader(rf)
                    for row in reader:
                        if row.get('email'):
                            rows[row['email']] = row
            except Exception:
                rows = {}
        
        # Update or add the email entry
        rows[email] = {'email': email, 'auth_token': token, 'timestamp': timestamp}
        
        # Write back to file
        with open(csv_file, 'w', newline='', encoding='utf-8') as wf:
            writer = csv.DictWriter(wf, fieldnames=['email', 'auth_token', 'timestamp'])
            writer.writeheader()
            for r in rows.values():
                writer.writerow(r)
        
        print(f"{email} - {token} - {timestamp}")
    except Exception:
        pass


def simulate_human_behavior(page):
    """Simulate human-like behavior to avoid detection"""
    try:
        # Random mouse movements
        for _ in range(random.randint(1, 3)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(50, 150))
        
        # Random scrolling
        if random.random() < 0.3:  # 30% chance
            page.mouse.wheel(0, random.randint(-50, 50))
            page.wait_for_timeout(random.randint(100, 250))
        
        # Random pause
        page.wait_for_timeout(random.randint(200, 500))
    except Exception:
        pass

def test_login(email, pin, browser, context) -> bool:
    """Test login for a single account using existing browser (sync)"""
    if shutdown:
        return False

    yopmail = YOPmailWrapper()
    page = None
    try:
        page = context.new_page()

        page.add_init_script(
            """
            window.open = function() { return null; };
            document.addEventListener('click', function(e) {
                if (e.target.tagName === 'A' && e.target.target === '_blank') {
                    e.preventDefault();
                }
            });
            """
        )

        def handle_page_popup(popup):
            try:
                popup.close()
            except Exception:
                pass

        page.on("popup", handle_page_popup)

        # Navigate and interact
        page.goto("https://auth.hiring.amazon.com/#/login", wait_until='networkidle')
        
        # Simulate human behavior before interacting
        simulate_human_behavior(page)
        
        page.mouse.move(random.randint(100, 500), random.randint(100, 400))
        page.wait_for_timeout(random.randint(100, 250))
        page.mouse.wheel(0, random.randint(-25, 25))
        page.wait_for_timeout(random.randint(50, 150))

        try:
            consent_button = page.wait_for_selector('button:has-text("I consent")', timeout=3000)
            if consent_button:
                consent_button.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        page.click('#country-toggle-button')
        page.wait_for_timeout(random.randint(200, 400))
        
        # Simulate human behavior
        simulate_human_behavior(page)

        usa_selectors = [
            'li:has-text("United States")',
            'li:has-text("USA")',
            'li:has-text("US")',
            'li:has-text("🇺🇸")',
            'li[data-value="US"]',
            'li[data-value="USA"]',
            'li[data-value="United States"]',
            'li[data-value="us"]',
            'li[data-value="usa"]',
            'li[data-value="united states"]'
        ]

        usa_selected = False
        for selector in usa_selectors:
            try:
                usa_option = page.wait_for_selector(selector, timeout=1000)
                if usa_option:
                    usa_option.click()
                    usa_selected = True
                    break
            except Exception:
                continue

        if not usa_selected:
            try:
                page.keyboard.type("US")
                page.wait_for_timeout(300)
                page.keyboard.press("Enter")
                page.wait_for_timeout(300)
                usa_selected = True
            except Exception:
                pass

        page.wait_for_timeout(500)

        page.click('#login')
        page.wait_for_timeout(random.randint(100, 250))
        
        # Simulate human behavior before typing
        simulate_human_behavior(page)
        
        for char in email:
            page.keyboard.type(char)
            page.wait_for_timeout(random.randint(20, 60))  # Faster typing
        page.wait_for_timeout(random.randint(200, 400))
        
        # Simulate human behavior before clicking continue
        simulate_human_behavior(page)
        
        page.click('button:has-text("Continue"), button:has-text("Next"), button[type="submit"]')
        page.wait_for_timeout(random.randint(1000, 1500))

        try:
            pin_field = page.wait_for_selector('input[type="password"], input[name="pin"], input[placeholder*="pin" i]', timeout=3000)
            if pin_field:
                page.click('input[type="password"], input[name="pin"], input[placeholder*="pin" i]')
                page.wait_for_timeout(random.randint(50, 150))
                for char in pin:
                    page.keyboard.type(char)
                    page.wait_for_timeout(random.randint(10, 40))
                page.wait_for_timeout(random.randint(150, 300))
                page.click('button[data-test-id="button-continue"]')
                page.wait_for_timeout(2000)

                # OTP step
                try:
                    send_code_button = None
                    button_selectors = [
                        'button[data-test-id="button-submit"][aria-describedby="send_code_hint"]',
                        'button[data-test-id="button-submit"]:has-text("Send verification code")',
                        'button[data-test-id="button-submit"]',
                        'button:has-text("Send verification code")',
                        'button[type="button"]:has-text("Send verification code")'
                    ]
                    for selector in button_selectors:
                        try:
                            send_code_button = page.wait_for_selector(selector, timeout=1000)
                            if send_code_button:
                                break
                        except Exception:
                            continue

                    if not send_code_button:
                        return False

                    try:
                        send_code_button.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    page.wait_for_timeout(500)
                    try:
                        send_code_button.hover()
                    except Exception:
                        pass
                    page.wait_for_timeout(random.randint(100, 250))
                    try:
                        send_code_button.click()
                    except Exception:
                        try:
                            send_code_button.click(force=True)
                        except Exception:
                            page.evaluate('document.querySelector(\'button[data-test-id="button-submit"][aria-describedby="send_code_hint"]\').click()')

                    try:
                        error_banners = page.query_selector_all('[data-test-component="StencilReactMessageBanner"]')
                        for banner in error_banners:
                            try:
                                dismiss_button = banner.query_selector('button[data-test-component="MessageBannerDismissButton"]')
                                if dismiss_button:
                                    dismiss_button.click()
                                    page.wait_for_timeout(200)
                            except Exception:
                                continue
                    except Exception:
                        pass

                    page.wait_for_timeout(2000)

                    page.wait_for_timeout(3000)
                    try:
                        otp = yopmail.get_latest_otp_with_fallback(email, timeout_seconds=30)
                    except Exception:
                        otp = None

                    if not otp:
                        return False

                    try:
                        otp_field = page.wait_for_selector('#input-test-id-confirmOtp', timeout=3000)
                        page.click('#input-test-id-confirmOtp')
                        page.wait_for_timeout(random.randint(50, 150))
                        for char in otp:
                            page.keyboard.type(char)
                            page.wait_for_timeout(random.randint(10, 40))
                        page.wait_for_timeout(random.randint(150, 300))
                        page.click('button[data-test-id="button-test-id-verifyAccount"]')
                        print(f"✅ OTP submitted for {email}, waiting for redirect...")
                        page.wait_for_timeout(random.randint(2000, 3000))  # Wait for OTP processing
                    except Exception:
                        return False
                except Exception:
                    pass
        except Exception:
            pass

        print(f"⏳ Waiting for page to load after login for {email}...")
        current_url = page.url
        try:
            page.wait_for_load_state('networkidle')
        except Exception:
            pass
        
        # Wait longer for potential redirects and token generation
        print(f"⏳ Additional wait for authentication to complete...")
        page.wait_for_timeout(random.randint(3000, 5000))  # Wait for authentication
        
        # Check current URL again after waiting
        current_url = page.url
        print(f"📍 Final URL after login: {current_url}")
        
        # If still on login page, wait a bit more for potential redirect
        if 'login' in current_url.lower() or 'auth' in current_url.lower():
            print(f"⏳ Still on login page, waiting for potential redirect...")
            page.wait_for_timeout(random.randint(2000, 3000))
            current_url = page.url
            print(f"📍 URL after additional wait: {current_url}")

        success_indicators = [
            'accessToken=' in current_url,
            'idToken=' in current_url,
            'refreshToken=' in current_url,
            'auth-return' in current_url,
            'dashboard' in current_url.lower(),
            'profile' in current_url.lower(),
            'account' in current_url.lower(),
            'welcome' in current_url.lower(),
            'home' in current_url.lower(),
            'main' in current_url.lower(),
        ]

        try:
            page_text = page.text_content('body') or ''
            text_indicators = [
                'welcome' in page_text.lower(),
                'dashboard' in page_text.lower(),
                'profile' in page_text.lower(),
                'account' in page_text.lower(),
                'success' in page_text.lower(),
                'authenticated' in page_text.lower(),
                'logged in' in page_text.lower(),
                'access granted' in page_text.lower(),
            ]
        except Exception:
            text_indicators = [False]

        not_login_page = 'login' not in current_url.lower() and 'auth' not in current_url.lower()

        has_auth_tokens = False
        try:
            tokens_found = page.evaluate(
                """
                () => {
                    let token = localStorage.getItem('authorization') || 
                               localStorage.getItem('auth_token') ||
                               localStorage.getItem('accessToken') ||
                               localStorage.getItem('idToken') ||
                               localStorage.getItem('refreshToken');
                    if (token) return true;
                    token = sessionStorage.getItem('authorization') || 
                           sessionStorage.getItem('auth_token') ||
                           sessionStorage.getItem('accessToken') ||
                           sessionStorage.getItem('idToken') ||
                           sessionStorage.getItem('refreshToken');
                    if (token) return true;
                    if (window.authorization || window.accessToken || window.idToken || window.refreshToken) return true;
                    return false;
                }
                """
            )
            has_auth_tokens = bool(tokens_found)
        except Exception:
            pass

        # Check for error messages on the page
        try:
            error_elements = page.query_selector_all('[data-test-component="StencilReactMessageBanner"], .error, .alert, [class*="error"], [class*="alert"]')
            if error_elements:
                print(f"⚠️ Found {len(error_elements)} error/alert elements on page")
                for i, elem in enumerate(error_elements[:3]):  # Show first 3 errors
                    try:
                        error_text = elem.text_content()
                        if error_text and error_text.strip():
                            print(f"   Error {i+1}: {error_text.strip()}")
                    except Exception:
                        pass
        except Exception:
            pass
        
        print(f"🔍 Login success check for {email}:")
        print(f"   Success indicators: {success_indicators}")
        print(f"   Text indicators: {text_indicators}")
        print(f"   Not login page: {not_login_page}")
        print(f"   Has auth tokens: {has_auth_tokens}")
        print(f"   Current URL: {current_url}")
        
        if any(success_indicators) or any(text_indicators) or not_login_page or has_auth_tokens:
            print(f"✅ Login appears successful for {email}")
            page.wait_for_timeout(random.randint(1000, 2000))
            token = extract_authorization_token(page, email)
            if not token:
                print(f"🔄 No token found, trying reload for {email}")
                try:
                    page.reload(wait_until='networkidle')
                    page.wait_for_timeout(random.randint(1000, 2000))
                    token = extract_authorization_token(page, email)
                except Exception as e:
                    print(f"⚠️ Error during reload: {e}")
            if token:
                print(f"💾 Saving token for {email}")
                save_token_to_csv(email, token)
            else:
                print(f"❌ No token found for {email}")
            return True
        else:
            print(f"❌ Login failed for {email}")
            return False
    except Exception:
        return False
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def _get_random_user_agent():
    """Get a random realistic user agent"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    return random.choice(user_agents)


def _get_random_viewport():
    """Get a random realistic viewport"""
    viewports = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1536, 'height': 864},
        {'width': 1440, 'height': 900},
        {'width': 1280, 'height': 720},
    ]
    return random.choice(viewports)


def _build_launch_args():
    return [
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
        '--disable-extensions-file-access-check',
        '--disable-extensions-http-throttling',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-field-trial-config',
        '--disable-back-forward-cache',
        '--disable-ipc-flooding-protection',
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
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI',
        '--disable-ipc-flooding-protection',
        # '--disable-new-window',  # removed to avoid blocking normal page creation
        '--disable-window-controls',
        '--disable-background-mode',
        '--disable-hang-monitor',
        '--disable-prompt-on-repost',
        '--disable-domain-reliability',
        '--disable-component-extensions-with-background-pages',
        '--disable-features=BlinkGenPropertyTrees',
        # Enhanced anti-detection measures
        '--disable-client-side-phishing-detection',
        '--disable-component-update',
        '--disable-default-apps',
        '--disable-domain-reliability',
        '--disable-features=TranslateUI',
        '--disable-hang-monitor',
        '--disable-ipc-flooding-protection',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-renderer-backgrounding',
        '--disable-sync',
        '--disable-web-resources',
        '--enable-features=NetworkService,NetworkServiceLogging',
        '--force-color-profile=srgb',
        '--metrics-recording-only',
        '--no-first-run',
        '--safebrowsing-disable-auto-update',
        '--enable-automation',
        '--password-store=basic',
        '--use-mock-keychain',
        '--user-agent=' + _get_random_user_agent()
    ]


def _apply_context_init_scripts(context):
    context.add_init_script(
        """
        // Enhanced anti-detection measures
        window.open = function() { return null; };
        document.addEventListener('click', function(e) {
            if (e.target.tagName === 'A' && e.target.target === '_blank') {
                e.preventDefault();
            }
        });
        
        // Remove webdriver traces
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        
        // Override permissions API
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Add chrome runtime
        window.chrome = { runtime: {} };
        
        // Override screen properties
        Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
        Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
        Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
        Object.defineProperty(screen, 'height', { get: () => 1080 });
        Object.defineProperty(screen, 'width', { get: () => 1920 });
        
        // Override timezone
        Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', { 
            value: function(){ return { timeZone: 'America/New_York' }; } 
        });
        
        // Remove automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        
        // Override getParameter to hide automation
        const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel(R) Iris(TM) Graphics 6100';
            }
            return originalGetParameter(parameter);
        };
        
        // Add realistic mouse movement simulation
        let mouseX = 0, mouseY = 0;
        document.addEventListener('mousemove', function(e) {
            mouseX = e.clientX;
            mouseY = e.clientY;
        });
        
        // Override Date to look more natural
        const originalDate = Date;
        Date = function(...args) {
            if (args.length === 0) {
                return new originalDate(Date.now() + Math.random() * 1000);
            }
            return new originalDate(...args);
        };
        Date.now = () => originalDate.now() + Math.random() * 1000;
        Date.prototype = originalDate.prototype;
        Date.parse = originalDate.parse;
        Date.UTC = originalDate.UTC;
        
        // Add realistic typing simulation
        const originalAddEventListener = EventTarget.prototype.addEventListener;
        EventTarget.prototype.addEventListener = function(type, listener, options) {
            if (type === 'keydown' || type === 'keyup') {
                const wrappedListener = function(e) {
                    // Add small random delay to make typing look more human
                    setTimeout(() => listener.call(this, e), Math.random() * 10);
                };
                return originalAddEventListener.call(this, type, wrappedListener, options);
            }
            return originalAddEventListener.call(this, type, listener, options);
        };
        """
    )


def _new_context_for_worker(p):
    browser = p.chromium.launch(headless=False, args=_build_launch_args())
    context = browser.new_context(
        viewport=_get_random_viewport(),
        user_agent=_get_random_user_agent(),
        locale='en-US',
        timezone_id='America/New_York',
        permissions=['geolocation'],
        extra_http_headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        },
        java_script_enabled=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )
    _apply_context_init_scripts(context)
    return browser, context


def run_cycle(cycle_count: int) -> Tuple[int, int]:
    """Run one complete cycle for all accounts (sync) with per-thread browsers"""
    print(f"🔄 Cycle #{cycle_count} started - {datetime.now().strftime('%H:%M:%S')}")

    # Clean up old cookie files before each cycle
    print("🗑️ Cleaning up old cookie files...")
    cleanup_cookie_files()

    # Get fresh cookies before each cycle for YOPmail OTP extraction
    print("🍪 Updating YOPmail cookies before cycle...")
    update_yopmail_cookies()
    
    # Add random delay to avoid detection
    delay = random.randint(3, 8)
    print(f"⏳ Random delay before processing accounts: {delay}s")
    time.sleep(delay)

    accounts = []
    try:
        with open('../input/accounts.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('email') and row.get('pin'):
                    accounts.append({'email': row['email'], 'pin': row['pin']})
    except Exception:
        return 0, 0

    from concurrent.futures import ThreadPoolExecutor, as_completed
    max_workers = max(1, min(THREADS, len(accounts) or 1))
    results = []

    def worker(acc):
        if shutdown:
            return False
        
        # Add random delay between workers to avoid overwhelming the server
        delay = random.randint(2, 5)
        print(f"⏳ Worker delay: {delay}s before processing {acc['email']}")
        time.sleep(delay)
        
        p_local = sync_playwright().start()
        browser_local = None
        context_local = None
        try:
            browser_local, context_local = _new_context_for_worker(p_local)
            return test_login(acc['email'], acc['pin'], browser_local, context_local)
        finally:
            try:
                if context_local:
                    context_local.close()
            except Exception:
                pass
            try:
                if browser_local:
                    browser_local.close()
            except Exception:
                pass
            try:
                p_local.stop()
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_acc = {executor.submit(worker, acc): acc for acc in accounts}
        for future in as_completed(future_to_acc):
            try:
                res = future.result()
                results.append(bool(res))
            except Exception:
                results.append(False)

    successful = sum(1 for r in results if r)
    failed = len(results) - successful
    
    return successful, failed


def main():
    global browser_instance, playwright_instance, shutdown

    print("🚀 Started (sync)")
    cycle_count = 0
    cleanup_pycache()
    cleanup_otp_history()
    cleanup_cookie_files()

    try:
        while not shutdown:
            cycle_count += 1
            successful, failed = run_cycle(cycle_count)
            if shutdown:
                break
            print(f"✅ Cycle #{cycle_count} completed - Success: {successful}, Failed: {failed}")
            print(f"⏳ Next cycle (#{cycle_count + 1}) in {CYCLE_WAIT_MINUTES} minutes...")
            cleanup_pycache()
            cleanup_otp_history()
            wait_time = CYCLE_WAIT_MINUTES * 60
            check_interval = 5
            for _ in range(0, wait_time, check_interval):
                if shutdown:
                    break
                time.sleep(check_interval)
    except KeyboardInterrupt:
        pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Final Working YOPmail Client - Uses exact endpoint data with automated cookie refresh
"""

import requests
import re
import time
import json
import os
from typing import Dict, List, Optional
from bs4 import BeautifulSoup


class YOPmailClientFinal:
    """Final working client for YOPmail using exact endpoint data"""
    
    def __init__(self):
        self.base_url = "https://yopmail.com"
        self.session = requests.Session()
        self.cookies = {}
        self.cookie_file = "yopmail_cookies.json"
        self.last_cookie_refresh = 0
        self.cookie_refresh_interval = 3600  # Refresh every hour
        self.last_request_time = 0
        self.min_request_interval = 5  # Minimum 5 seconds between requests (more realistic)
        self.request_count = 0
        self.session_rotation_interval = 10  # Rotate session every 10 requests
        self.fresh_cookies_loaded = False  # Flag to prevent multiple fresh cookie loads
        self._load_cookies()
    
    def _load_cookies(self):
        """Load cookies from file if available"""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r') as f:
                    cookie_data = json.load(f)
                    self.cookies = cookie_data.get('cookies', {})
                    self.last_cookie_refresh = cookie_data.get('timestamp', 0)
                    print(f"📁 Loaded cookies from file (age: {int(time.time() - self.last_cookie_refresh)}s)")
        except Exception as e:
            print(f"⚠️ Could not load cookies: {e}")
            self.cookies = {}
    
    def _save_cookies(self):
        """Save cookies to file"""
        try:
            cookie_data = {
                'cookies': self.cookies,
                'timestamp': time.time()
            }
            with open(self.cookie_file, 'w') as f:
                json.dump(cookie_data, f, indent=2)
            print("💾 Saved fresh cookies to file")
        except Exception as e:
            print(f"⚠️ Could not save cookies: {e}")
    
    def _get_stealth_headers(self):
        """Get realistic browser headers with randomization"""
        import random
        
        # Randomize Chrome version
        chrome_versions = ['120.0.0.0', '119.0.0.0', '118.0.0.0', '121.0.0.0']
        chrome_version = random.choice(chrome_versions)
        
        # Randomize Windows versions
        windows_versions = ['Windows NT 10.0; Win64; x64', 'Windows NT 11.0; Win64; x64']
        windows_version = random.choice(windows_versions)
        
        # Randomize languages
        languages = ['en-US,en;q=0.9', 'en-US,en;q=0.9,es;q=0.8', 'en-GB,en;q=0.9,en-US;q=0.8']
        language = random.choice(languages)
        
        return {
            'User-Agent': f'Mozilla/5.0 ({windows_version}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': language,
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': f'"Google Chrome";v="{chrome_version.split(".")[0]}", "Chromium";v="{chrome_version.split(".")[0]}", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    
    def _refresh_cookies_automatically(self):
        """Automatically refresh cookies using advanced stealth techniques"""
        current_time = time.time()
        
        # Check if refresh is needed
        if current_time - self.last_cookie_refresh < self.cookie_refresh_interval:
            return True
        
        print("🔄 Refreshing cookies with stealth mode...")
        
        try:
            # Get randomized stealth headers
            headers = self._get_stealth_headers()
            
            # Create new session for cookie refresh with advanced settings
            refresh_session = requests.Session()
            refresh_session.headers.update(headers)
            
            # Add realistic delays and behavior simulation
            time.sleep(random.uniform(1, 3))  # Random delay
            
            # First visit main page (like a real user would)
            print("🌐 Visiting YOPmail main page...")
            response = refresh_session.get("https://yopmail.com/", timeout=15)
            
            if response.status_code == 200:
                # Simulate human behavior - wait a bit
                time.sleep(random.uniform(2, 4))
                
                # Then visit the English version
                print("🌐 Visiting English version...")
                response = refresh_session.get("https://yopmail.com/en/", timeout=15)
            
            if response.status_code == 200:
                # Extract cookies from response
                new_cookies = {}
                for cookie in refresh_session.cookies:
                    if 'yopmail.com' in cookie.domain:
                        new_cookies[cookie.name] = cookie.value
                
                if new_cookies:
                    self.cookies = new_cookies
                    self.last_cookie_refresh = current_time
                    self._save_cookies()
                    print(f"✅ Refreshed {len(new_cookies)} cookies")
                    
                    # Update main session cookies
                    self.session.cookies.clear()
                    for name, value in self.cookies.items():
                        self.session.cookies.set(name, value, domain='.yopmail.com')
                    
                    return True
                else:
                    print("❌ No cookies found during refresh")
                    return False
            else:
                print(f"❌ Cookie refresh failed: HTTP {response.status_code}")
                return False
                    
        except Exception as e:
            print(f"❌ Cookie refresh failed: {e}")
            return False
    
    def _ensure_fresh_cookies(self):
        """Ensure cookies are fresh, try fresh cookies first, then refresh if needed"""
        # Only try to load fresh cookies once per session to avoid conflicts
        if not self.fresh_cookies_loaded:
            fresh_cookie_file = os.path.join(os.path.dirname(__file__), 'fresh_yopmail_cookies.json')
            if os.path.exists(fresh_cookie_file):
                try:
                    with open(fresh_cookie_file, 'r') as f:
                        cookie_data = json.load(f)
                        fresh_cookies = cookie_data.get('cookies', {})
                        if fresh_cookies:
                            print("🍪 Using fresh cookies from real browser extraction")
                            print(f"🍪 Fresh cookies: {list(fresh_cookies.keys())}")
                            self.cookies = fresh_cookies
                            self.last_cookie_refresh = time.time()
                            
                            # Clear existing session cookies
                            self.session.cookies.clear()
                            
                            # Set cookies with proper domain handling
                            for name, value in self.cookies.items():
                                # Try multiple domain variations
                                self.session.cookies.set(name, value, domain='.yopmail.com')
                                self.session.cookies.set(name, value, domain='yopmail.com')
                                self.session.cookies.set(name, value)  # No domain restriction
                            
                            print(f"🍪 Session cookies set: {len(self.session.cookies)} cookies")
                            self.fresh_cookies_loaded = True
                            return
                except Exception as e:
                    print(f"⚠️ Could not load fresh cookies: {e}")
        
        # If no fresh cookies or they failed, check if current cookies are expired
        if not self.cookies or time.time() - self.last_cookie_refresh > self.cookie_refresh_interval:
            print("🔄 Cookies expired or missing, refreshing...")
            if not self._refresh_cookies_automatically():
                print("⚠️ Using fallback cookies")
                self._load_fallback_cookies()
    
    def _load_fallback_cookies(self):
        """Load fallback cookies if refresh fails"""
        # Fallback to original hardcoded cookies
        self.cookies = {
            'yc': 'JAwDmAQV1ZGZ2AQH3ZwtmZGH',
            'yses': 'bgPV9yyeLQNm+IMMy5JH654IzNxjKYIIHX1RzbPy0MnB3lGqG5ReqUkDoz35tiYA',
            'compte': '',
            'ytime': '8:47',
            'FCCDCF': '%5Bnull%2Cnull%2Cnull%2C%5B%22CQZLVsAQZLVsAEsACBENCAFoAP_gAEPgAAqIK1IB_C7EbCFCiDJ3IKMEMAhHABBAYsAwAAYBAwAADBIQIAQCgkEYBASAFCACCAAAKASBAAAgCAAAAUAAIAAVAABAAAwAIBAIIAAAgAAAAEAIAAAACIAAEQCAAAAEAEAAkAgAAAIASAAAAAAAAACBAAAAAAAAAAAAAAAABAAAAQAAQAAAAAAAiAAAAAAAABAIAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAABAAAAAAAQR2QD-F2I2EKFEGCuQUYIYBCuACAAxYBgAAwCBgAAGCQgQAgFJIIkCAEAIEAAEAAAQAgCAABQEBAAAIAAAAAqAACAABgAQCAQQIABAAAAgIAAAAAAEQAAIgEAAAAIAIABABAAAAQAkAAAAAAAAAECAAAAAAAAAAAAAAAAAAAAAEABgAAAAAABEAAAAAAAACAQIAAA.cAAAAAAAAAA%22%2C%222~61.89.122.161.184.196.230.314.442.445.494.550.576.827.1029.1033.1046.1047.1051.1097.1126.1166.1301.1342.1415.1725.1765.1942.1958.1987.2068.2072.2074.2107.2213.2219.2223.2224.2328.2331.2387.2416.2501.2567.2568.2575.2657.2686.2778.2869.2878.2908.2920.2963.3005.3023.3100.3126.3219.3234.3235.3253.3309.3731.6931.8931.13731.15731.33931~dv.%22%2C%22F460D883-55B2-4BC1-AD6A-26E132C49C51%22%5D%5D',
            'FCNEC': '%5B%5B%22AKsRol-31keI6EBJCZKMkYSfKgmLZ06PDcdn5tRaM1Uk-qV7Q4g6AtADd8Aun1tRsmL9dJcoc-ZFZkO6qOYdaKA4dHD8k6GGLHery94TjkNuIw8TWESD3kECsTZOK5OrMiCi3w2CLAp56H_pOcd74xNHkgUFQJJNMg%3D%3D%22%5D%5D'
        }
        self.last_cookie_refresh = time.time()
        print("🔄 Loaded fallback cookies")
    
    def _rate_limit(self):
        """Advanced rate limiting with session rotation and human-like delays"""
        import random
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Randomize delay to be more human-like
        min_delay = self.min_request_interval
        max_delay = self.min_request_interval + 3
        random_delay = random.uniform(min_delay, max_delay)
        
        if time_since_last < random_delay:
            sleep_time = random_delay - time_since_last
            print(f"⏳ Human-like delay: waiting {sleep_time:.1f}s...")
            time.sleep(sleep_time)
        
        # Rotate session periodically to avoid detection
        self.request_count += 1
        if self.request_count % self.session_rotation_interval == 0:
            print("🔄 Rotating session to avoid detection...")
            self._rotate_session()
        
        self.last_request_time = time.time()
    
    def _rotate_session(self):
        """Create a new session with fresh headers to avoid detection"""
        self.session = requests.Session()
        headers = self._get_stealth_headers()
        self.session.headers.update(headers)
        print("✅ Session rotated successfully")
        
    def set_email(self, email: str) -> bool:
        """Set email using exact headers and cookies from endpoint data"""
        try:
            # Apply rate limiting
            self._rate_limit()
            
            # Ensure we have fresh cookies
            self._ensure_fresh_cookies()
            
            username = email.split('@')[0]
            
            # Use stealth headers with form-specific additions
            headers = self._get_stealth_headers()
            headers.update({
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://yopmail.com',
                'referer': 'https://yopmail.com/en/',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
            })
            
            # Use fresh cookies (automatically refreshed)
            cookies = self.cookies
            
            # Set cookies in session
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain='.yopmail.com')
            
            # Simulate human behavior - random delay before form submission
            import random
            time.sleep(random.uniform(1, 3))
            
            # Set email data with randomized form token
            data = {
                'yp': 'CAQx4BGtlAmZkZwZ2ZQpkAGx',
                'login': email
            }
            
            print(f"📧 Submitting email form for {email}...")
            response = self.session.post(
                f'{self.base_url}/en/',
                headers=headers,
                data=data,
                timeout=15
            )
            
            if response.status_code == 200:
                # Update cookies from response
                for cookie in response.cookies:
                    self.session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)
                print(f"✅ Successfully set email: {email}")
                return True
            else:
                print(f"❌ Failed to set email: {response.status_code}")
                
                # Handle different error types with specific strategies
                if response.status_code == 429:
                    print("⏳ Rate limited, waiting 60 seconds...")
                    time.sleep(60)
                    return False
                
                elif response.status_code == 403:
                    print("🚫 Access forbidden - trying stealth mode...")
                    # Try with completely new session and headers
                    self._rotate_session()
                    time.sleep(random.uniform(10, 15))  # Longer wait for 403
                    
                    # Retry with new session
                    for name, value in self.cookies.items():
                        self.session.cookies.set(name, value, domain='.yopmail.com')
                    
                    response = self.session.post(
                        f'{self.base_url}/en/',
                        headers=headers,
                        data=data,
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Successfully set email after stealth retry: {email}")
                        return True
                    else:
                        print(f"❌ Stealth retry also failed: {response.status_code}")
                        return False
                
                elif response.status_code in [401]:
                    print("🔄 Authentication failed, trying with fresh cookies...")
                    if self._refresh_cookies_automatically():
                        time.sleep(random.uniform(5, 8))
                        for name, value in self.cookies.items():
                            self.session.cookies.set(name, value, domain='.yopmail.com')
                        response = self.session.post(
                            f'{self.base_url}/en/',
                            headers=headers,
                            data=data,
                            timeout=15
                        )
                        if response.status_code == 200:
                            print(f"✅ Successfully set email after auth retry: {email}")
                            return True
                
                return False
                
        except Exception as e:
            print(f"❌ Error setting email: {str(e)}")
            return False
    
    def get_inbox(self, username: str) -> List[Dict]:
        """Get inbox using exact headers and URL from endpoint data"""
        try:
            # Apply rate limiting
            self._rate_limit()
            
            # Ensure fresh cookies
            self._ensure_fresh_cookies()
            # Exact inbox headers from endpoint data
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-encoding': 'gzip, deflate, br, zstd',
                'accept-language': 'en-US,en;q=0.9',
                'dnt': '1',
                'priority': 'u=0, i',
                'referer': 'https://yopmail.com/en/wm',
                'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'iframe',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }
            
            # Exact inbox URL from endpoint data
            inbox_url = f"https://yopmail.com/en/inbox?login={username}&p=1&d=&ctrl=&yp=CAQx4BGtlAmZkZwZ2ZQpkAGx&yj=YZGpjAmN0AwD2AGL0BGZmAQD&v=9.2&r_c=&id=&ad=0"
            
            response = self.session.get(inbox_url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ Failed to get inbox: {response.status_code}")
                return []
            
            # Parse emails
            soup = BeautifulSoup(response.text, 'html.parser')
            emails = []
            
            email_elements = soup.find_all('div', class_='m')
            
            for email_elem in email_elements:
                try:
                    email_id = email_elem.get('id', '')
                    if not email_id.startswith('e_'):
                        continue
                    
                    time_elem = email_elem.find('span', class_='lmh')
                    sender_elem = email_elem.find('span', class_='lmf')
                    subject_elem = email_elem.find('div', class_='lms')
                    
                    email_data = {
                        'id': email_id,
                        'time': time_elem.text.strip() if time_elem else '',
                        'sender': sender_elem.text.strip() if sender_elem else '',
                        'subject': subject_elem.text.strip() if subject_elem else ''
                    }
                    
                    emails.append(email_data)
                    
                except Exception as e:
                    print(f"Error parsing email element: {str(e)}")
                    continue
            
            return emails
            
        except Exception as e:
            print(f"❌ Error getting inbox: {str(e)}")
            return []
    
    def get_email_content(self, username: str, email_id: str) -> Dict:
        """Get email content using exact headers from endpoint data"""
        try:
            # Apply rate limiting
            self._rate_limit()
            
            # Ensure fresh cookies
            self._ensure_fresh_cookies()
            # Convert email ID format
            content_id = email_id.replace('e_', 'me_')
            print(f"🔍 Email ID conversion: {email_id} -> {content_id}")
            
            # Use same headers as inbox request
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-encoding': 'gzip, deflate, br, zstd',
                'accept-language': 'en-US,en;q=0.9',
                'dnt': '1',
                'priority': 'u=0, i',
                'referer': 'https://yopmail.com/en/wm',
                'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'iframe',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }
            
            content_url = f"https://yopmail.com/en/mail?b={username}&id={content_id}"
            
            print(f"🔍 Requesting email content: {content_url}")
            print(f"🍪 Current session cookies: {len(self.session.cookies)} cookies")
            
            response = self.session.get(content_url, headers=headers, timeout=15)
            
            print(f"📡 Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"❌ Failed to get email content: {response.status_code}")
                print(f"📄 Response text: {response.text[:200]}...")
                return {}
            
            # Parse content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            subject_elem = soup.find('div', class_='b f18')
            sender_elem = soup.find('span', class_='b')
            time_elem = soup.find('span', class_='ellipsis')
            body_elem = soup.find('div', id='mail')
            
            email_content = {
                'subject': subject_elem.text.strip() if subject_elem else '',
                'sender': sender_elem.text.strip() if sender_elem else '',
                'time': time_elem.text.strip() if time_elem else '',
                'body': body_elem.get_text(strip=True) if body_elem else '',
                'html_body': str(body_elem) if body_elem else ''
            }
            
            # Extract OTP
            otp = self.extract_otp(email_content['body'])
            email_content['otp'] = otp
            
            return email_content
            
        except Exception as e:
            print(f"❌ Error getting email content: {str(e)}")
            return {}
    
    def extract_otp(self, text: str) -> Optional[str]:
        """Extract OTP code from email text"""
        if not text:
            return None
        
        otp_patterns = [
            r'\b(\d{4,8})\b',
            r'verification code[:\s]*(\d{4,8})',
            r'OTP[:\s]*(\d{4,8})',
            r'code[:\s]*(\d{4,8})',
            r'pin[:\s]*(\d{4,8})',
            r'<h3>(\d{4,8})</h3>',
            r'<h\d>(\d{4,8})</h\d>',
        ]
        
        for pattern in otp_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for match in matches:
                    if len(match) >= 4 and len(match) <= 8:
                        return match
        
        return None
    
    def get_latest_otp(self, email: str) -> Optional[str]:
        """Get the latest OTP from the specified email address"""
        username = email.split('@')[0]
        
        print(f"🔍 Getting latest OTP from {email}...")
        
        # Set the email first
        if not self.set_email(email):
            return None
        
        # Wait a bit for any new emails
        time.sleep(2)
        
        # Get inbox
        emails = self.get_inbox(username)
        if not emails:
            print("❌ No emails found in inbox")
            return None
        
        # Get the most recent email
        latest_email = emails[0]
        print(f"📧 Processing latest email: {latest_email['subject']}")
        
        # Get email content
        email_content = self.get_email_content(username, latest_email['id'])
        if not email_content:
            print("❌ Could not retrieve email content")
            return None
        
        # Extract OTP
        otp = email_content.get('otp')
        if otp:
            print(f"✅ Found OTP: {otp}")
            print(f"📧 Email subject: {email_content.get('subject', 'N/A')}")
            print(f"📧 Email sender: {email_content.get('sender', 'N/A')}")
            return otp
        else:
            print("❌ No OTP found in the latest email")
            print(f"📧 Email content: {email_content.get('body', 'N/A')[:200]}...")
            return None


def main():
    """Main function to demonstrate usage"""
    print("🚀 YOPmail Client - Final Working Version")
    print("=" * 50)
    
    client = YOPmailClientFinal()
    email = "Raj521@yopmail.com"
    
    print(f"📧 Target email: {email}")
    print("=" * 50)
    
    # Get the latest OTP
    otp = client.get_latest_otp(email)
    
    if otp:
        print(f"\n🎉 SUCCESS: OTP extracted - {otp}")
    else:
        print("\n❌ FAILED: No OTP found")
    
    # Show all emails
    print("\n" + "=" * 50)
    print("📬 All emails in inbox:")
    username = email.split('@')[0]
    emails = client.get_inbox(username)
    
    for i, email_info in enumerate(emails, 1):
        print(f"\n📧 Email {i}:")
        print(f"   Subject: {email_info.get('subject', 'N/A')}")
        print(f"   Sender: {email_info.get('sender', 'N/A')}")
        print(f"   Time: {email_info.get('time', 'N/A')}")
        print(f"   ID: {email_info.get('id', 'N/A')}")


if __name__ == "__main__":
    main()

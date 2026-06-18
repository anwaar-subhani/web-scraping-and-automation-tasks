#!/usr/bin/env python3
"""
YOPmail Wrapper with OTP tracking and timeout functionality
"""

import time
import json
import os
from typing import Optional, List, Dict
from yopmail_client_final import YOPmailClientFinal


class YOPmailWrapper:
    """Wrapper for YOPmail with OTP tracking and timeout functionality"""
    
    def __init__(self, history_file: str = "otp_history.json"):
        self.client = YOPmailClientFinal()
        self.history_file = history_file
        self.otp_history = self._load_history()
        # Don't load fresh cookies initially - use hardcoded ones first
    
    def _load_history(self) -> Dict:
        """Load OTP history from file and clean expired entries"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
                
                # Clean expired OTPs (older than 3 minutes)
                current_time = time.time()
                expiry_timestamp = current_time - (3 * 60)  # 3 minutes ago
                
                cleaned_history = {}
                for email, otp_list in history.items():
                    valid_otps = []
                    for otp_entry in otp_list:
                        if otp_entry.get('timestamp', 0) > expiry_timestamp:
                            valid_otps.append(otp_entry)
                    
                    if valid_otps:
                        cleaned_history[email] = valid_otps
                
                # Save cleaned history if any entries were removed
                if len(cleaned_history) != len(history) or any(len(cleaned_history.get(email, [])) != len(history.get(email, [])) for email in history):
                    with open(self.history_file, 'w') as f:
                        json.dump(cleaned_history, f, indent=2)
                    print("🧹 Cleaned expired OTP entries from history (3+ minutes old)")
                
                return cleaned_history
        except Exception as e:
            print(f"⚠️ Could not load history: {e}")
        return {}
    
    def _load_fresh_cookies(self):
        """Load fresh cookies from file if available - prioritize fresh cookies"""
        try:
            fresh_cookie_file = os.path.join(os.path.dirname(__file__), 'fresh_yopmail_cookies.json')
            if os.path.exists(fresh_cookie_file):
                with open(fresh_cookie_file, 'r') as f:
                    cookie_data = json.load(f)
                    fresh_cookies = cookie_data.get('cookies', {})
                    if fresh_cookies:
                        print(f"🍪 Loaded {len(fresh_cookies)} fresh cookies from real browser")
                        # Update the client's cookies
                        self.client.cookies = fresh_cookies
                        # Update session cookies
                        self.client.session.cookies.clear()
                        for name, value in fresh_cookies.items():
                            self.client.session.cookies.set(name, value, domain='.yopmail.com')
                        return True
        except Exception as e:
            print(f"⚠️ Could not load fresh cookies: {e}")
        return False
    
    def _save_history(self):
        """Save OTP history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.otp_history, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save history: {e}")
    
    def _add_otp_to_history(self, email: str, otp: str, timestamp: float):
        """Add OTP to history"""
        if email not in self.otp_history:
            self.otp_history[email] = []
        
        self.otp_history[email].append({
            'otp': otp,
            'timestamp': timestamp,
            'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        })
        
        # Keep only last 10 OTPs per email
        if len(self.otp_history[email]) > 10:
            self.otp_history[email] = self.otp_history[email][-10:]
        
        self._save_history()
    
    def _is_new_otp(self, email: str, otp: str) -> bool:
        """Check if OTP is new (not in history)"""
        if email not in self.otp_history:
            return True
        
        for entry in self.otp_history[email]:
            if entry['otp'] == otp:
                return False
        return True
    
    def get_latest_otp_with_fallback(self, email: str, timeout_seconds: int = 15) -> Optional[str]:
        """
        Get latest OTP with fresh cookies first, then fallback to hardcoded cookies
        
        Args:
            email (str): Email address to check
            timeout_seconds (int): Maximum time to wait for new OTP
            
        Returns:
            Optional[str]: New OTP if found within timeout, None otherwise
        """
        print(f"🔍 Getting OTP from {email} (timeout: {timeout_seconds}s)...")
        
        # First try with fresh cookies from real browser
        print("🍪 Trying with fresh cookies from real browser...")
        if self._load_fresh_cookies():
            print("🍪 Fresh cookies loaded, attempting OTP extraction...")
            otp = self.get_latest_otp_with_timeout(email, timeout_seconds)
            if otp:
                print("✅ OTP found with fresh cookies!")
                return otp
            else:
                print("❌ Fresh cookies failed to get OTP")
        
        # If fresh cookies failed, try with hardcoded cookies
        print("🔄 Fresh cookies failed, trying hardcoded cookies...")
        otp = self.get_latest_otp_with_timeout(email, timeout_seconds)
        
        if otp:
            print("✅ OTP found with hardcoded cookies!")
            return otp
        
        print("❌ Both fresh and hardcoded cookies failed")
        return None
    
    def get_latest_otp_with_timeout(self, email: str, timeout_seconds: int = 15) -> Optional[str]:
        """
        Get latest OTP with timeout and tracking
        
        Args:
            email (str): Email address to check
            timeout_seconds (int): Maximum time to wait for new OTP
            
        Returns:
            Optional[str]: New OTP if found within timeout, None otherwise
        """
        print(f"🔍 Waiting for new OTP from {email} (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        last_checked_otps = set()
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Get current OTP
                current_otp = self.client.get_latest_otp(email)
                
                if current_otp:
                    # Check if this is a new OTP
                    if current_otp not in last_checked_otps and self._is_new_otp(email, current_otp):
                        # Found new OTP!
                        timestamp = time.time()
                        self._add_otp_to_history(email, current_otp, timestamp)
                        
                        print(f"✅ New OTP found: {current_otp}")
                        print(f"📅 Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}")
                        return current_otp
                    
                    # Track this OTP to avoid checking it again
                    last_checked_otps.add(current_otp)
                
                # Wait 2 seconds before next check
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Error checking for OTP: {e}")
                time.sleep(2)
        
        print(f"⏰ Timeout reached ({timeout_seconds}s) - No new OTP found")
        return None
    
    def get_otp_history(self, email: str) -> List[Dict]:
        """Get OTP history for an email"""
        return self.otp_history.get(email, [])
    
    def clear_otp_history(self, email: str = None):
        """Clear OTP history for an email or all emails"""
        if email:
            if email in self.otp_history:
                del self.otp_history[email]
                print(f"🗑️ Cleared OTP history for {email}")
        else:
            self.otp_history = {}
            print("🗑️ Cleared all OTP history")
        
        self._save_history()
    
    def get_latest_otp_immediate(self, email: str) -> Optional[str]:
        """Get latest OTP immediately without waiting for new ones"""
        return self.client.get_latest_otp(email)
    
    def get_inbox_emails(self, email: str) -> List[Dict]:
        """Get all emails in inbox"""
        username = email.split('@')[0]
        return self.client.get_inbox(username)


def main():
    """Example usage of YOPmail Wrapper"""
    print("🚀 YOPmail Wrapper - Example Usage")
    print("=" * 50)
    
    # Create wrapper instance
    wrapper = YOPmailWrapper()
    email = "Raj521@yopmail.com"
    
    print(f"📧 Target email: {email}")
    print("=" * 50)
    
    # Example 1: Wait for new OTP with timeout
    print("\n1️⃣ Waiting for new OTP (15 second timeout)...")
    new_otp = wrapper.get_latest_otp_with_timeout(email, timeout_seconds=15)
    
    if new_otp:
        print(f"🎉 Success! New OTP: {new_otp}")
    else:
        print("❌ No new OTP found within timeout")
    
    # Example 2: Get immediate OTP (any OTP, new or old)
    print("\n2️⃣ Getting immediate OTP...")
    immediate_otp = wrapper.get_latest_otp_immediate(email)
    if immediate_otp:
        print(f"📧 Current OTP: {immediate_otp}")
    else:
        print("❌ No OTP found")
    
    # Example 3: Show OTP history
    print("\n3️⃣ OTP History:")
    history = wrapper.get_otp_history(email)
    if history:
        for entry in history[-5:]:  # Show last 5
            print(f"   {entry['time_str']}: {entry['otp']}")
    else:
        print("   No history available")
    
    # Example 4: Get inbox emails
    print("\n4️⃣ Inbox Emails:")
    emails = wrapper.get_inbox_emails(email)
    for i, email_info in enumerate(emails[:3], 1):  # Show first 3
        print(f"   Email {i}: {email_info['subject']} ({email_info['time']})")


if __name__ == "__main__":
    main()

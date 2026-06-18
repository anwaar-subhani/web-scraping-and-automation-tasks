"""Utility functions for URL manipulation and Google Sheets"""
import requests
import csv
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime
from . import config

def convert_google_sheet_to_csv_url(share_url):
    """Convert Google Sheet share URL to CSV export URL"""
    # Extract sheet ID from share URL
    if '/d/' in share_url:
        sheet_id = share_url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        return csv_url
    return None

def read_urls_from_google_sheet():
    """Read URLs from Google Sheet"""
    try:
        csv_url = convert_google_sheet_to_csv_url(config.GOOGLE_SHEET_URL)
        if not csv_url:
            print("[ERROR] Could not convert Google Sheet URL to CSV format")
            return []
        
        print(f"Reading URLs from Google Sheet: {csv_url}")
        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()
        
        # Parse CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        
        urls = []
        for line in lines:
            line = line.strip()
            # Skip empty lines and header if it exists
            if line and line.lower() not in ['url', 'link', 'search url']:
                # Remove quotes if present
                line = line.strip('"\'')
                # Check if it's a valid URL
                if line.startswith('http') and 'amazon' in line.lower():
                    urls.append(line)
        
        print(f"Found {len(urls)} URLs in Google Sheet")
        return urls
    except Exception as e:
        print(f"[ERROR] Failed to read Google Sheet: {e}")
        return []

def normalize_url(url):
    """Normalize URL for consistent matching (remove page parameter, normalize path)"""
    try:
        parsed = urlparse(url.strip())
        # Remove page parameter for normalization
        params = parse_qs(parsed.query)
        if 'page' in params:
            del params['page']
        # Normalize path (remove /-/en/ variations)
        path = parsed.path
        if '/-/en/' in path:
            path = path.replace('/-/en/', '/')
        elif '/-/en' in path:
            path = path.replace('/-/en', '/')
        
        # Rebuild URL without page parameter
        new_query = urlencode(params, doseq=True)
        normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, new_query, ''))
        return normalized
    except Exception as e:
        print(f"Warning: Could not normalize URL: {e}")
        return url.strip()

def extract_page_number_from_url(url):
    """Extract page number from Amazon search URL"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'page' in params:
            return int(params['page'][0])
        # No page parameter means page 1 (first page)
        return 1
    except:
        return 1

def build_page_url(base_url, page_num):
    """Build URL for a specific page"""
    try:
        parsed = urlparse(base_url)
        params = parse_qs(parsed.query)
        params['page'] = [str(page_num)]
        
        new_query = urlencode(params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)
    except Exception as e:
        print(f"Warning: Could not build page URL: {e}")
        # Fallback: append page parameter
        separator = '&' if '?' in base_url else '?'
        return f"{base_url}{separator}page={page_num}"

def extract_filename_from_url(url):
    """Extract meaningful filename from Amazon search URL"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Extract market from domain (e.g., amazon.fr -> fr, amazon.co.uk -> uk)
        domain = parsed.netloc.replace('www.', '')
        if 'amazon.co.uk' in domain:
            market = 'uk'
        elif 'amazon.' in domain:
            market = domain.split('amazon.')[-1].split('.')[0]  # Get part after amazon.
            if market == 'co':
                market = 'uk'  # Handle amazon.co.uk
        else:
            market = 'unknown'
        
        # Try to get category from 'i' parameter (e.g., i=electronics)
        category = None
        if 'i' in params and params['i']:
            category = params['i'][0]
        # Try to get search keyword from 'k' parameter as fallback
        elif 'k' in params and params['k']:
            category = params['k'][0]
        
        if category:
            # Clean category for filename
            clean_category = category.replace(' ', '_').replace('+', '_').replace('&', 'and').replace('/', '_').replace('%', '_')
            # Remove special characters, keep only alphanumeric and underscore
            clean_category = ''.join(c for c in clean_category if c.isalnum() or c == '_')
            # Limit length
            if len(clean_category) > 40:
                clean_category = clean_category[:40]
            return f"{clean_category}_sellers_{market}.xlsx"
        
        # Fallback: use domain and hash of URL
        domain_clean = domain.replace('.', '_').replace('-', '_')
        url_hash = abs(hash(url)) % 10000
        return f"sellers_{market}_{url_hash}.xlsx"
    except Exception as e:
        print(f"Warning: Could not extract filename from URL: {e}")
        # Last resort: use timestamp
        return f"sellers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

def clean_old_cache():
    """Clean up old cache files"""
    import shutil
    try:
        import os
        if os.path.exists("__pycache__"):
            shutil.rmtree("__pycache__")
            print("Cleaned up __pycache__ directory")
    except Exception as e:
        print(f"Warning: Could not clean __pycache__: {e}")

def visit_amazon_home_first(driver, url):
    """Visit Amazon home page first and click continue shopping (for proxy usage)
    ALWAYS visits base URL first, waits, then proceeds to actual URL
    Works with Selenium driver instead of Playwright page"""
    from urllib.parse import urlparse
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    print(f"[PROXY] ===== PROXY MODE: Visiting Amazon home first ======")
    print(f"[PROXY] Step 1: Going to base URL: {base_url}")
    
    # ALWAYS visit home page first - even if it times out, we still wait
    home_loaded = False
    try:
        driver.get(base_url)
        # Wait a bit for page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print(f"[PROXY] ✓ Successfully loaded Amazon home page")
        home_loaded = True
    except Exception as e:
        print(f"[PROXY] ⚠ Timeout/error loading home page (this is OK): {str(e)[:100]}")
        home_loaded = False
    
    # ALWAYS wait after attempting to load home page
    print(f"[PROXY] Step 2: Waiting 4 seconds after home page visit...")
    time.sleep(4)
    
    # Look for continue shopping button or similar (only if page loaded)
    if home_loaded:
        print(f"[PROXY] Step 3: Looking for continue shopping button...")
        continue_selectors = [
            'button[type="submit"].a-button-text',
            'input[type="submit"][value*="Continue"]',
            'input[type="submit"][value*="Continuer"]',
            'a[href*="/ref=cs_503_link"]',
        ]
        
        clicked = False
        for selector in continue_selectors:
            try:
                button = driver.find_element(By.CSS_SELECTOR, selector)
                if button and button.is_displayed():
                    driver.execute_script("arguments[0].click();", button)
                    print(f"[PROXY] ✓ Clicked continue shopping button")
                    clicked = True
                    break
            except:
                continue
        
        if not clicked:
            # Try JavaScript click as fallback
            try:
                result = driver.execute_script("""
                    const buttons = document.querySelectorAll('button, input[type="submit"], a');
                    for (let btn of buttons) {
                        const text = (btn.textContent || btn.value || '').toLowerCase();
                        if (text.includes('continue') || 
                            text.includes('shopping') ||
                            text.includes('continuer') ||
                            text.includes('acheter')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                """)
                if result:
                    print(f"[PROXY] ✓ Clicked continue button via JavaScript")
                else:
                    print(f"[PROXY] - No continue button found (OK, proceeding)")
            except:
                pass
        
        if clicked:
            print(f"[PROXY] Step 4: Waiting 3 seconds after clicking button...")
            time.sleep(3)
    
    # ALWAYS perform browsing actions after clicking continue (or even if button wasn't found)
    # Spend 10-15 seconds doing human-like browsing actions
    if home_loaded:
        start_time = time.time()
        print(f"[PROXY] Step 5: Performing human-like browsing (10-15 seconds)...")
        
        # Action 1: Initial scroll down slowly (2-3 seconds)
        try:
            driver.execute_script("""
                return new Promise((resolve) => {
                    let position = 0;
                    const scrollStep = 150;
                    const scrollInterval = setInterval(() => {
                        window.scrollBy(0, scrollStep);
                        position += scrollStep;
                        if (position >= Math.min(document.body.scrollHeight, 1500)) {
                            clearInterval(scrollInterval);
                            resolve();
                        }
                    }, 100);
                });
            """)
            print(f"[PROXY] ✓ Scrolled down the page")
        except Exception as e:
            print(f"[PROXY] ⚠ Scroll error: {e}")
        
        time.sleep(1.5)  # Wait after scroll
        
        # Action 2: Hover over some elements (1-2 seconds) - Selenium doesn't have hover, so we'll skip or use JS
        try:
            hover_selectors = [
                'a[href*="/gp/bestsellers"]',
                'a[href*="/gp/new-releases"]',
                '#nav-link-accountList',
                '.nav-link',
            ]
            for selector in hover_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and element.is_displayed():
                        # Use JavaScript to simulate hover
                        driver.execute_script("arguments[0].dispatchEvent(new Event('mouseover'));", element)
                        print(f"[PROXY] ✓ Hovered over element")
                        time.sleep(1.2)
                        break
                except:
                    continue
        except:
            pass
        
        # Action 3: Scroll back up a bit (1 second)
        try:
            driver.execute_script("window.scrollBy(0, -400)")
            time.sleep(1)
            print(f"[PROXY] ✓ Scrolled up slightly")
        except:
            pass
        
        # Action 4: Scroll down again to find products (1-2 seconds)
        try:
            driver.execute_script("""
                return new Promise((resolve) => {
                    let position = 0;
                    const scrollStep = 200;
                    const scrollInterval = setInterval(() => {
                        window.scrollBy(0, scrollStep);
                        position += scrollStep;
                        if (position >= 800) {
                            clearInterval(scrollInterval);
                            resolve();
                        }
                    }, 120);
                });
            """)
        except:
            pass
        time.sleep(1)
        
        # Action 5: Look for and click on a product (3-5 seconds)
        print(f"[PROXY] Step 6: Looking for a product to click...")
        product_clicked = False
        try:
            # Use JavaScript to find and click a product link
            result = driver.execute_script("""
                const selectors = [
                    'a[href*="/dp/"]',
                    'a[href*="/gp/product/"]',
                    '[data-component-type="s-product-image"] a',
                    '.s-result-item a[href*="/dp/"]',
                    'a[href*="/dp/"][class*="product"]'
                ];
                
                for (let selector of selectors) {
                    const links = document.querySelectorAll(selector);
                    for (let link of links) {
                        const rect = link.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && 
                            rect.top >= 0 && rect.left >= 0 &&
                            rect.bottom <= window.innerHeight && 
                            rect.right <= window.innerWidth) {
                            const href = link.getAttribute('href');
                            if (href && (href.includes('/dp/') || href.includes('/gp/product/'))) {
                                link.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                return href;
                            }
                        }
                    }
                }
                return null;
            """)
            
            if result:
                # Wait a bit for scroll to complete
                time.sleep(1.5)
                
                # Click the product using Selenium
                try:
                    # Extract product ID from href
                    if '/dp/' in result:
                        product_id = result.split('/dp/')[-1].split('/')[0].split('?')[0]
                    elif '/gp/product/' in result:
                        product_id = result.split('/gp/product/')[-1].split('/')[0].split('?')[0]
                    else:
                        product_id = None
                    
                    if product_id:
                        # Try to find and click using Selenium
                        product_link = driver.find_element(By.CSS_SELECTOR, f'a[href*="/dp/{product_id}"], a[href*="/gp/product/{product_id}"]')
                        driver.execute_script("arguments[0].click();", product_link)
                        print(f"[PROXY] ✓ Clicked on a product: {result[:80]}...")
                        product_clicked = True
                    else:
                        raise Exception("Could not extract product ID")
                except:
                    # Fallback: use JavaScript click
                    try:
                        driver.execute_script("""
                            const links = document.querySelectorAll('a[href*="/dp/"], a[href*="/gp/product/"]');
                            for (let link of links) {
                                const rect = link.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    const href = link.getAttribute('href');
                                    if (href && (href.includes('/dp/') || href.includes('/gp/product/'))) {
                                        link.click();
                                        return true;
                                    }
                                }
                            }
                            return false;
                        """)
                        print(f"[PROXY] ✓ Clicked on a product via JavaScript")
                        product_clicked = True
                    except:
                        pass
                
                if product_clicked:
                    # Wait on product page to simulate viewing (2-3 seconds)
                    time.sleep(2)
                    
                    # Scroll on product page (1-2 seconds)
                    try:
                        driver.execute_script("""
                            return new Promise((resolve) => {
                                let position = 0;
                                const scrollStep = 150;
                                const scrollInterval = setInterval(() => {
                                    window.scrollBy(0, scrollStep);
                                    position += scrollStep;
                                    if (position >= 600) {
                                        clearInterval(scrollInterval);
                                        resolve();
                                    }
                                }, 100);
                            });
                        """)
                        time.sleep(1.5)
                        print(f"[PROXY] ✓ Scrolled on product page")
                    except:
                        pass
                    
                    # Maybe hover over some product elements (1 second)
                    try:
                        hover_element = driver.find_element(By.CSS_SELECTOR, 'a[href*="#customerReviews"], .a-button-text')
                        if hover_element and hover_element.is_displayed():
                            driver.execute_script("arguments[0].dispatchEvent(new Event('mouseover'));", hover_element)
                            time.sleep(1)
                    except:
                        pass
            else:
                print(f"[PROXY] - No product found to click (OK, proceeding)")
        except Exception as e:
            print(f"[PROXY] ⚠ Product click error: {e}")
        
        # Ensure we've spent at least 10 seconds, but not more than 15
        elapsed_time = time.time() - start_time
        if elapsed_time < 10:
            remaining_time = 10 - elapsed_time
            print(f"[PROXY] Waiting {remaining_time:.1f} more seconds to reach 10 seconds total...")
            time.sleep(int(remaining_time))
        elif elapsed_time > 15:
            print(f"[PROXY] ⚠ Browsing took {elapsed_time:.1f} seconds (target: 10-15s)")
        else:
            print(f"[PROXY] ✓ Browsing completed in {elapsed_time:.1f} seconds")
        
        print(f"[PROXY] ✓ Human-like browsing simulation completed")
    
    # ALWAYS wait before proceeding to actual URL
    print(f"[PROXY] Step 6: Final wait (2 seconds) before going to search URL...")
    time.sleep(2)
    print(f"[PROXY] ===== Now proceeding to actual search URL ======")


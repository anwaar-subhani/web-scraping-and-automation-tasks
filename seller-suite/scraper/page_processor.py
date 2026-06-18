"""Single page processing logic"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse
from datetime import datetime
import pandas as pd
import os
import time
from . import config
from . import progress
from . import file_manager
from . import js_scripts
from . import browser_manager
from .utils import build_page_url

def get_driver(proxy_string=None):
    """Create undetected Chrome driver with optional proxy"""
    options = uc.ChromeOptions()
    
    if proxy_string:
        # Create proxy extension
        proxy_plugin_dir = browser_manager.create_proxy_auth_extension(proxy_string)
        options.add_argument("--disable-extensions-except=" + proxy_plugin_dir)
    
    # Block specific websites
    blocked_sites = [
        "optimizationguide-pa.googleapis.com",
        "clients2.googleusercontent.com"
    ]
    for site in blocked_sites:
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 2,
        })
    
    options.page_load_strategy = 'eager'
    
    # Try to use chromedriver.exe if it exists, otherwise let uc find it
    driver_executable_path = None
    if os.path.exists("chromedriver.exe"):
        driver_executable_path = "chromedriver.exe"
    elif os.path.exists("sample/chromedriver.exe"):
        driver_executable_path = "sample/chromedriver.exe"
    
    if config.HEADLESS:
        options.add_argument("--headless")
    
    driver = uc.Chrome(options=options, driver_executable_path=driver_executable_path)
    return driver

def process_single_page(search_url, page_num, thread_id, excel_filename, proxy_string=None, start_product_index=0):
    """Process a single page of search results - creates its own browser instance
    
    Args:
        search_url: Base search URL
        page_num: Page number to process
        thread_id: Thread identifier
        excel_filename: Output filename
        proxy_string: Proxy string (host:port:username:password or host:port) (optional)
        start_product_index: Product index to start from (0-based, for resuming)
    """
    # Check stop flag immediately
    if config.shutdown_flag.is_set():
        return []
    
    page_seller_data = []
    current_product_index = start_product_index
    driver = None
    
    # Mark page as starting (product_index 0 or resume position)
    if not config.shutdown_flag.is_set():
        progress.update_page_progress(search_url, page_num, current_product_index)
    
    try:
        try:
            # Create driver with proxy if provided
            driver = get_driver(proxy_string)
            
            # Build URL for this page
            if page_num == 1:
                page_url = search_url
            else:
                page_url = build_page_url(search_url, page_num)
            
            print(f"[Thread {thread_id}] [Page {page_num}] Processing page...")
            
            # Navigate to page with retry logic
            max_retries = 3
            for retry in range(max_retries):
                if config.shutdown_flag.is_set():
                    try:
                        driver.quit()
                    except:
                        pass
                    return page_seller_data
                try:
                    driver.get(page_url)
                    if config.shutdown_flag.is_set():
                        try:
                            driver.quit()
                        except:
                            pass
                        return page_seller_data
                    time.sleep(2)
                    break
                except Exception as e:
                    print(f"[Thread {thread_id}] [Page {page_num}] Navigation attempt {retry + 1} failed: {e}")
                    if retry < max_retries - 1:
                        time.sleep(5)
                    else:
                        print(f"[Thread {thread_id}] [Page {page_num}] Skipping page due to navigation failures")
                        try:
                            driver.quit()
                        except:
                            pass
                        return page_seller_data
            
            # Load products
            print(f"[Thread {thread_id}] [Page {page_num}] Loading products...")
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-component-type="s-search-result"]'))
                )
                print(f"[Thread {thread_id}] [Page {page_num}] Search results loaded")
            except:
                print(f"[Thread {thread_id}] [Page {page_num}] Search results not found, continuing...")
            
            # Scroll to trigger lazy loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)
            
            print(f"[Thread {thread_id}] [Page {page_num}] Products loaded")
            
            # Get ALL product links including sponsored links
            product_links = driver.execute_script(f"return ({js_scripts.GET_PRODUCT_LINKS_SCRIPT})();")
            
            print(f"[Thread {thread_id}] [Page {page_num}] Found {len(product_links)} products")
            
            if start_product_index > 0:
                print(f"[Thread {thread_id}] [Page {page_num}] Resuming from product {start_product_index + 1}/{len(product_links)}")
            
            # Visit each product (skip already processed ones)
            for i, product in enumerate(product_links[start_product_index:], start=start_product_index + 1):
                if config.shutdown_flag.is_set():
                    print(f"[Thread {thread_id}] [Page {page_num}] Shutdown requested")
                    try:
                        driver.quit()
                    except:
                        pass
                    return page_seller_data
                
                print(f"[Thread {thread_id}] [Page {page_num}] Product {i}/{len(product_links)}: {product['title'][:50]}...")
                
                try:
                    if config.shutdown_flag.is_set():
                        try:
                            driver.quit()
                        except:
                            pass
                        return page_seller_data
                    
                    # Go to product page
                    if product['href'].startswith('http'):
                        full_url = product['href']
                    else:
                        # Extract domain from search URL
                        parsed = urlparse(search_url)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"
                        full_url = f"{base_url}{product['href']}"
                    
                    driver.get(full_url)
                    if config.shutdown_flag.is_set():
                        try:
                            driver.quit()
                        except:
                            pass
                        return page_seller_data
                    time.sleep(1)
                    
                    # Get seller info
                    seller_info = driver.execute_script(f"return ({js_scripts.GET_SELLER_INFO_SCRIPT})();")
                    
                    # Check if third-party seller
                    if seller_info['seller'] and 'amazon' not in seller_info['seller'].lower():
                        print(f"[Thread {thread_id}] [Page {page_num}]   Third-party seller: {seller_info['seller']}")
                        
                        # Click seller link
                        try:
                            seller_link = driver.find_element(By.CSS_SELECTOR, '[data-csa-c-content-id="desktop-merchant-info"] a[href*="/gp/help/seller/"]')
                            if seller_link:
                                driver.execute_script("arguments[0].click();", seller_link)
                                time.sleep(1)
                                
                                # Get seller page URL
                                seller_page_url = driver.current_url
                                
                                # Get seller details
                                details = driver.execute_script(f"return ({js_scripts.GET_SELLER_DETAILS_SCRIPT})();")
                                
                                # Check if all seller attributes are missing
                                all_attributes_missing = (
                                    details['business_name'] == 'N/A' and
                                    details['phone_number'] == 'N/A' and
                                    details['email'] == 'N/A' and
                                    details['country'] == 'N/A'
                                )
                                
                                if all_attributes_missing:
                                    print(f"[Thread {thread_id}] [Page {page_num}]   All seller attributes missing - skipping entry")
                                    continue
                                
                                # Get current timestamp
                                extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
                                # Check for duplicates before adding (check in existing file)
                                new_seller = {
                                    'Business Name': details['business_name'],
                                    'Phone Number': details['phone_number'],
                                    'Email': details['email'],
                                    'Country': details['country'],
                                    'Seller Name': details.get('seller_name', 'N/A'),
                                    'Seller URL': seller_page_url,
                                    'Extracted At': extracted_at
                                }
                                
                                # Check in existing file if it exists
                                is_duplicate = False
                                if os.path.exists(excel_filename):
                                    try:
                                        existing_df = pd.read_excel(excel_filename, sheet_name='Sellers')
                                        for _, row in existing_df.iterrows():
                                            if (str(row.get('Business Name', '')) == new_seller['Business Name'] and 
                                                str(row.get('Email', '')) == new_seller['Email']):
                                                is_duplicate = True
                                                break
                                    except:
                                        pass
                                
                                if not is_duplicate:
                                    page_seller_data.append(new_seller)
                                    print(f"[Thread {thread_id}] [Page {page_num}]   Added: {details['business_name']} | {details['phone_number']} | {details['email']} | {details['country']}")
                                    # Save Excel and Google Sheets immediately when a record is found
                                    file_manager.save_results_incremental(excel_filename, [new_seller], search_url)
                                else:
                                    print(f"[Thread {thread_id}] [Page {page_num}]   Duplicate found - skipping: {details['business_name']} | {details['email']}")
                        except Exception as e:
                            print(f"[Thread {thread_id}] [Page {page_num}]   Error finding seller link: {e}")
                    else:
                        print(f"[Thread {thread_id}] [Page {page_num}]   Amazon seller - skipping")
                    
                    # Update progress after each product is processed
                    current_product_index = i - 1  # 0-based index
                    if not config.shutdown_flag.is_set():
                        progress.update_page_progress(search_url, page_num, current_product_index)
                    
                except Exception as e:
                    print(f"[Thread {thread_id}] [Page {page_num}]   Error: {e}")
                    # Still update progress even on error, so we don't retry the same product
                    current_product_index = i - 1
                    if not config.shutdown_flag.is_set():
                        progress.update_page_progress(search_url, page_num, current_product_index)
                    continue
            
            try:
                driver.quit()
            except:
                pass
            
            # Page completed - remove from progress tracking
            if not config.shutdown_flag.is_set():
                progress.remove_page_from_progress(search_url, page_num)
                print(f"[Thread {thread_id}] [Page {page_num}] Completed processing")
            return page_seller_data
            
        except Exception as e:
            print(f"[Thread {thread_id}] [Page {page_num}] Error: {e}")
            try:
                if driver:
                    driver.quit()
            except:
                pass
            return page_seller_data
        finally:
            # Update progress on error (save current position)
            if not config.shutdown_flag.is_set():
                progress.update_page_progress(search_url, page_num, current_product_index)
            # Ensure driver is closed
            try:
                if driver:
                    driver.quit()
            except:
                pass
    except Exception as e:
        print(f"[Thread {thread_id}] [Page {page_num}] Outer error: {e}")
        # Update progress even on outer exception
        if not config.shutdown_flag.is_set():
            progress.update_page_progress(search_url, page_num, current_product_index)
        # Ensure driver is closed
        try:
            if driver:
                driver.quit()
        except:
            pass
        return page_seller_data

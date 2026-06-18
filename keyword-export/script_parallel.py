from playwright.sync_api import sync_playwright
import json
import pandas as pd
import os
import shutil
import threading
import time
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Load configuration from JSON file
with open("config.json") as f:
    config = json.load(f)

SEARCH_KEYWORDS = config["SEARCH_KEYWORDS"]
MARKET = config["MARKET"]
MAX_THREADS = config["MAX_THREADS"]

# Global data storage with thread lock
seller_data = []
data_lock = threading.Lock()
shutdown_flag = threading.Event()

def clean_old_cache():
    """Clean up old cache files"""
    try:
        if os.path.exists("__pycache__"):
            shutil.rmtree("__pycache__")
            print("Cleaned up __pycache__ directory")
    except Exception as e:
        print(f"Warning: Could not clean __pycache__: {e}")

def get_amazon_domain():
    """Get the correct Amazon domain for the market"""
    return "amazon.co.uk" if MARKET == "uk" else f"amazon.{MARKET}"

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutdown signal received! Stopping all threads...")
    shutdown_flag.set()
    sys.exit(0)

def process_single_search(search_keyword, thread_id):
    """Process a single search keyword in a separate browser instance"""
    print(f"[Thread {thread_id}] Starting search for: {search_keyword}")
    
    # Check if shutdown was requested
    if shutdown_flag.is_set():
        print(f"[Thread {thread_id}] Shutdown requested, stopping...")
        return
    
    # Create Excel file with clean name (no thread ID)
    clean_keyword = search_keyword.replace(' ', '_').replace('+', '_').replace('&', 'and')
    excel_filename = f"Amazon_{MARKET.upper()}_Sellers_{clean_keyword}.xlsx"
    thread_seller_data = []
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=False,  # Make browsers visible
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-web-security']
            )
            page = browser.new_page()
            print(f"[Thread {thread_id}] Browser launched successfully")
        except Exception as e:
            print(f"[Thread {thread_id}] Failed to launch browser: {e}")
            return
        
        try:
            # Open Amazon with retry logic
            max_retries = 3
            for retry in range(max_retries):
                try:
                    print(f"[Thread {thread_id}] Connecting to Amazon {MARKET.upper()} (attempt {retry + 1}/{max_retries})...")
                    amazon_domain = get_amazon_domain()
                    page.goto(f"https://www.{amazon_domain}/", timeout=30000)
                    print(f"[Thread {thread_id}] Successfully connected to Amazon")
                    break
                except Exception as e:
                    print(f"[Thread {thread_id}] Connection attempt {retry + 1} failed: {e}")
                    if retry < max_retries - 1:
                        print(f"[Thread {thread_id}] Waiting 5 seconds before retry...")
                        page.wait_for_timeout(5000)
                    else:
                        print(f"[Thread {thread_id}] Failed to connect after all attempts")
                        return
            
            # Check for captcha page
            try:
                page.wait_for_timeout(3000)
                captcha_button = page.query_selector('button[type="submit"].a-button-text')
                if captcha_button and captcha_button.is_visible():
                    print(f"[Thread {thread_id}] Captcha page detected, clicking continue button...")
                    captcha_button.click()
                    page.wait_for_timeout(3000)
                else:
                    print(f"[Thread {thread_id}] No captcha page detected")
            except Exception as e:
                print(f"[Thread {thread_id}] Error checking for captcha: {e}")
            
            # Search for products
            max_retries = 3
            for retry in range(max_retries):
                try:
                    print(f"[Thread {thread_id}] Searching for '{search_keyword}' (attempt {retry + 1}/{max_retries})...")
                    amazon_domain = get_amazon_domain()
                    page.goto(f"https://www.{amazon_domain}/s?k={search_keyword}", timeout=30000)
                    page.wait_for_timeout(3000)
                    print(f"[Thread {thread_id}] Search completed successfully")
                    break
                except Exception as e:
                    print(f"[Thread {thread_id}] Search attempt {retry + 1} failed: {e}")
                    if retry < max_retries - 1:
                        page.wait_for_timeout(5000)
                    else:
                        print(f"[Thread {thread_id}] Failed to search after all attempts")
                        return
            
            # Find total pages (limited by MAX_PAGES_PER_SEARCH)
            print(f"[Thread {thread_id}] Looking for pagination...")
            total_pages = page.evaluate("""
                () => {
                    const currentPageSpan = document.querySelector('.s-pagination-item.s-pagination-disabled');
                    if (currentPageSpan) {
                        const pageNum = parseInt(currentPageSpan.textContent);
                        if (!isNaN(pageNum) && pageNum > 1) {
                            return pageNum;
                        }
                    }
                    
                    const pagination = document.querySelector('.s-pagination-container');
                    if (pagination) {
                        const pageElements = pagination.querySelectorAll('.s-pagination-item');
                        let maxPage = 1;
                        pageElements.forEach(element => {
                            const text = element.textContent?.trim();
                            const num = parseInt(text);
                            if (!isNaN(num) && num > maxPage) {
                                maxPage = num;
                            }
                        });
                        return maxPage;
                    }
                    
                    return 1;
                }
            """)
            
            print(f"[Thread {thread_id}] Processing {total_pages} pages")
            
            # Process each page
            for page_num in range(1, total_pages + 1):
                # Check if shutdown was requested
                if shutdown_flag.is_set():
                    print(f"[Thread {thread_id}] Shutdown requested, stopping page processing...")
                    return
                
                print(f"[Thread {thread_id}] Processing page {page_num}/{total_pages}...")
                
                # Go to page with retry logic
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        amazon_domain = get_amazon_domain()
                        page.goto(f"https://www.{amazon_domain}/s?k={search_keyword}&page={page_num}", timeout=60000)
                        page.wait_for_timeout(2000)
                        break
                    except Exception as e:
                        print(f"[Thread {thread_id}] Navigation attempt {retry + 1} failed: {e}")
                        if retry < max_retries - 1:
                            page.wait_for_timeout(5000)
                        else:
                            print(f"[Thread {thread_id}] Skipping page {page_num} due to navigation failures")
                            continue
                
                # Load products
                print(f"[Thread {thread_id}] Loading products on page {page_num}...")
                try:
                    page.wait_for_selector('[data-component-type="s-search-result"]', timeout=5000)
                    print(f"[Thread {thread_id}] Search results loaded")
                except:
                    print(f"[Thread {thread_id}] Search results not found, continuing...")
                
                # Scroll to trigger lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)
                
                print(f"[Thread {thread_id}] Products loaded")
                
                # Get product links
                product_links = page.evaluate("""
                    () => {
                        const links = [];
                        const processedHrefs = new Set();
                        const processedAsins = new Set();
                        
                        const searchResults = document.querySelectorAll('[data-component-type="s-search-result"]');
                        
                        searchResults.forEach((product, index) => {
                            const asin = product.getAttribute('data-asin');
                            
                            let link = product.querySelector('h2 a');
                            if (!link) link = product.querySelector('a[href*="/dp/"]');
                            if (!link) link = product.querySelector('a[href*="/-/en/"]');
                            
                            if (link) {
                                const href = link.getAttribute('href');
                                const title = link.textContent?.trim() || 'No title';
                                
                                const isDuplicate = processedHrefs.has(href) || 
                                                   (asin && processedAsins.has(asin));
                                
                                if (!isDuplicate) {
                                    processedHrefs.add(href);
                                    if (asin) processedAsins.add(asin);
                                    
                                    links.push({
                                        href: href,
                                        title: title,
                                        index: index,
                                        asin: asin
                                    });
                                }
                            }
                        });
                        
                        const filteredLinks = links.filter(link => {
                            const href = link.href;
                            const title = link.title.toLowerCase();
                            
                            return href && 
                                   (href.includes('/dp/') || href.includes('/-/en/')) &&
                                   !title.includes('learn about') &&
                                   !title.includes('visit the help') &&
                                   !title.includes('advertisement') &&
                                   title.length > 5;
                        });
                        
                        return filteredLinks;
                    }
                """)
                
                print(f"[Thread {thread_id}] Found {len(product_links)} products on page {page_num}")
                
                # Visit each product
                for i, product in enumerate(product_links, 1):
                    # Check if shutdown was requested
                    if shutdown_flag.is_set():
                        print(f"[Thread {thread_id}] Shutdown requested, stopping product processing...")
                        return
                    
                    print(f"[Thread {thread_id}] Product {i}/{len(product_links)}: {product['title'][:50]}...")
                    
                    try:
                        # Go to product page
                        if product['href'].startswith('http'):
                            full_url = product['href']
                        else:
                            amazon_domain = get_amazon_domain()
                            full_url = f"https://www.{amazon_domain}{product['href']}"
                        
                        page.goto(full_url)
                        page.wait_for_timeout(1000)
                        
                        # Get seller info
                        seller_info = page.evaluate("""
                            () => {
                                let seller = 'Unknown';
                                const sellerElement = document.querySelector('#merchantInfoFeature_feature_div .offer-display-feature-text-message');
                                if (sellerElement) {
                                    seller = sellerElement.textContent.trim();
                                }
                                return { seller: seller };
                            }
                        """)
                        
                        # Check if third-party seller (skip if seller name contains "amazon" in any case)
                        if seller_info['seller'] and 'amazon' not in seller_info['seller'].lower():
                            print(f"[Thread {thread_id}]   Third-party seller: {seller_info['seller']}")
                            
                            # Click seller link
                            seller_link = page.query_selector('[data-csa-c-content-id="desktop-merchant-info"] a[href*="/gp/help/seller/"]')
                            if seller_link:
                                seller_link.click()
                                page.wait_for_timeout(1000)
                                
                                # Get seller details
                                details = page.evaluate("""
                                    () => {
                                        const allData = {};
                                        
                                        const boldSpans = document.querySelectorAll('span.a-text-bold');
                                        boldSpans.forEach(span => {
                                            const label = span.textContent?.trim();
                                            const nextSpan = span.nextElementSibling;
                                            
                                            if (label && nextSpan) {
                                                const value = nextSpan.textContent?.trim();
                                                if (value && value !== '') {
                                                    allData[label] = value;
                                                }
                                            }
                                        });
                                        
                                        let businessName = 'N/A';
                                        let phoneNumber = 'N/A';
                                        let email = 'N/A';
                                        let country = 'N/A';
                                        
                                        for (const [label, value] of Object.entries(allData)) {
                                            if (label.toLowerCase().includes('name') || 
                                                label.toLowerCase().includes('nom') || 
                                                label.toLowerCase().includes('nombre') || 
                                                label.toLowerCase().includes('nome') || 
                                                label.toLowerCase().includes('firma') || 
                                                label.toLowerCase().includes('entreprise') || 
                                                label.toLowerCase().includes('empresa') || 
                                                label.toLowerCase().includes('azienda') || 
                                                label.toLowerCase().includes('företag') || 
                                                label.toLowerCase().includes('nazwa')) {
                                                businessName = value;
                                                break;
                                            }
                                        }
                                        
                                        for (const [label, value] of Object.entries(allData)) {
                                            if (label.toLowerCase().includes('phone') || 
                                                label.toLowerCase().includes('telephone') || 
                                                label.toLowerCase().includes('téléphone') || 
                                                label.toLowerCase().includes('teléfono') || 
                                                label.toLowerCase().includes('telefono') || 
                                                label.toLowerCase().includes('telefon') || 
                                                label.toLowerCase().includes('numer') || 
                                                label.toLowerCase().includes('nummer')) {
                                                phoneNumber = value;
                                                break;
                                            }
                                        }
                                        
                                        for (const [label, value] of Object.entries(allData)) {
                                            if (label.toLowerCase().includes('email') || 
                                                label.toLowerCase().includes('e-mail') || 
                                                label.toLowerCase().includes('courriel') || 
                                                label.toLowerCase().includes('correo') || 
                                                label.toLowerCase().includes('e-post') || 
                                                label.toLowerCase().includes('adres') || 
                                                label.toLowerCase().includes('adresse')) {
                                                email = value;
                                                break;
                                            }
                                        }
                                        
                                        const addressElements = document.querySelectorAll('.indent-left span');
                                        for (let element of addressElements) {
                                            const text = element.textContent?.trim();
                                            if (text && text.length === 2 && /^[A-Z]{2}$/.test(text)) {
                                                country = text;
                                                break;
                                            }
                                        }
                                        
                                        return {
                                            business_name: businessName,
                                            phone_number: phoneNumber,
                                            email: email,
                                            country: country
                                        };
                                    }
                                """)
                                
                                # Check if all seller attributes are missing (all N/A)
                                all_attributes_missing = (
                                    details['business_name'] == 'N/A' and
                                    details['phone_number'] == 'N/A' and
                                    details['email'] == 'N/A' and
                                    details['country'] == 'N/A'
                                )
                                
                                if all_attributes_missing:
                                    print(f"[Thread {thread_id}]   All seller attributes missing - skipping entry")
                                    continue
                                
                                # Check for duplicates before adding
                                new_seller = {
                                    'Business Name': details['business_name'],
                                    'Phone Number': details['phone_number'],
                                    'Email': details['email'],
                                    'Country': details['country']
                                }
                                
                                # Check if this seller already exists (by business name and email)
                                is_duplicate = False
                                with data_lock:
                                    for existing_seller in seller_data:
                                        if (existing_seller['Business Name'] == new_seller['Business Name'] and 
                                            existing_seller['Email'] == new_seller['Email']):
                                            is_duplicate = True
                                            break
                                
                                if not is_duplicate:
                                    with data_lock:
                                        seller_data.append(new_seller)
                                    thread_seller_data.append(new_seller)
                                    print(f"[Thread {thread_id}]   Added: {details['business_name']} | {details['phone_number']} | {details['email']} | {details['country']}")
                                else:
                                    print(f"[Thread {thread_id}]   Duplicate found - skipping: {details['business_name']} | {details['email']}")
                                
                                # Update Excel file immediately
                                df = pd.DataFrame(thread_seller_data)
                                with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                                    df.to_excel(writer, index=False, sheet_name='Sellers')
                                    worksheet = writer.sheets['Sellers']
                                    worksheet.column_dimensions['A'].width = 50
                                    worksheet.column_dimensions['B'].width = 20
                                    worksheet.column_dimensions['C'].width = 35
                                    worksheet.column_dimensions['D'].width = 10
                                
                                print(f"[Thread {thread_id}]   Excel updated with {len(thread_seller_data)} records")
                        else:
                            print(f"[Thread {thread_id}]   Amazon seller - skipping")
                            
                    except Exception as e:
                        print(f"[Thread {thread_id}]   Error: {e}")
                        continue
                
                # Small delay between pages
                page.wait_for_timeout(2000)
            
            print(f"[Thread {thread_id}] Completed search for '{search_keyword}' - Found {len(thread_seller_data)} sellers")
            
        except Exception as e:
            print(f"[Thread {thread_id}] Error in search processing: {e}")
        finally:
            browser.close()
            print(f"[Thread {thread_id}] Browser closed")

def main():
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting Parallel Amazon Scraper...")
    print(f"Search keywords: {SEARCH_KEYWORDS}")
    print(f"Market: {MARKET}")
    print(f"Max threads: {MAX_THREADS}")
    print("Press Ctrl+C to stop gracefully...")
    
    # Clean up old cache files
    clean_old_cache()
    
    # Create main Excel file with search keywords
    keywords_str = "_".join([keyword.replace(' ', '_').replace('+', '_').replace('&', 'and') for keyword in SEARCH_KEYWORDS])
    main_excel_filename = f"Amazon_{MARKET.upper()}_Sellers_{keywords_str}.xlsx"
    
    start_time = time.time()
    
    try:
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            # Submit all search tasks
            future_to_keyword = {
                executor.submit(process_single_search, keyword, i+1): keyword 
                for i, keyword in enumerate(SEARCH_KEYWORDS)
            }
            
            # Process completed tasks
            try:
                for future in as_completed(future_to_keyword):
                    # Check if shutdown was requested
                    if shutdown_flag.is_set():
                        print("🛑 Shutdown requested, cancelling remaining tasks...")
                        for f in future_to_keyword:
                            f.cancel()
                        break
                    
                    keyword = future_to_keyword[future]
                    try:
                        future.result()  # This will raise an exception if the thread failed
                        print(f"✓ Completed search for: {keyword}")
                    except Exception as e:
                        print(f"✗ Failed search for {keyword}: {e}")
            except KeyboardInterrupt:
                print("\n🛑 Keyboard interrupt received, shutting down...")
                shutdown_flag.set()
                for f in future_to_keyword:
                    f.cancel()
        
        # Create final combined Excel file
        if seller_data:
            df = pd.DataFrame(seller_data)
            with pd.ExcelWriter(main_excel_filename, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='All_Sellers')
                worksheet = writer.sheets['All_Sellers']
                worksheet.column_dimensions['A'].width = 50
                worksheet.column_dimensions['B'].width = 20
                worksheet.column_dimensions['C'].width = 35
                worksheet.column_dimensions['D'].width = 10
            
            print(f"\n✓ Completed! Found {len(seller_data)} total third-party sellers")
            print(f"✓ Main Excel file: {main_excel_filename}")
        else:
            print("\n✗ No sellers found")
        
        end_time = time.time()
        print(f"✓ Total execution time: {end_time - start_time:.2f} seconds")
        
    except Exception as e:
        print(f"✗ Error in main execution: {e}")
    
    input("Press Enter to close...")

if __name__ == "__main__":
    main()

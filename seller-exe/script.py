from playwright.sync_api import sync_playwright
import json
import pandas as pd
import os
import shutil

# Load configuration from JSON file
with open("config.json") as f:
    config = json.load(f)

SEARCH_KEYWORD = config["SEARCH_KEYWORD"]
MARKET = config["MARKET"]

def main():
    print("Starting Amazon scraper...")
    print(f"Search keyword: {SEARCH_KEYWORD}")
    print(f"Market: {MARKET}")
    
    # Clean up old cache files
    try:
        if os.path.exists("__pycache__"):
            shutil.rmtree("__pycache__")
            print("Cleaned up __pycache__ directory")
    except Exception as e:
        print(f"Warning: Could not clean __pycache__: {e}")
    
    # Create Excel file with shorter descriptive name
    clean_keyword = SEARCH_KEYWORD.replace(' ', '_').replace('+', '_').replace('&', 'and')
    excel_filename = f"Amazon_{MARKET.upper()}_Sellers_{clean_keyword}.xlsx"
    seller_data = []
    
    print(f"Excel file will be: {excel_filename}")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = browser.new_page()
            print("Browser launched successfully")
        except Exception as e:
            print(f"Failed to launch browser: {e}")
            return
        
        # Open Amazon with retry logic for network issues
        max_retries = 3
        for retry in range(max_retries):
            try:
                print(f"Connecting to Amazon {MARKET.upper()} (attempt {retry + 1}/{max_retries})...")
                # Special case for UK - use amazon.co.uk instead of amazon.uk
                amazon_domain = "amazon.co.uk" if MARKET == "uk" else f"amazon.{MARKET}"
                page.goto(f"https://www.{amazon_domain}/", timeout=30000)
                print("Successfully connected to Amazon")
                break
            except Exception as e:
                print(f"Connection attempt {retry + 1} failed: {e}")
                if retry < max_retries - 1:
                    print("Waiting 5 seconds before retry...")
                    try:
                        page.wait_for_timeout(5000)
                    except:
                        print("Browser closed during retry, attempting to continue...")
                        break
                else:
                    print("Failed to connect after all attempts. Please check your internet connection.")
                    return
        
        # Check for captcha page and click continue button if present
        try:
            # Wait for page to load
            page.wait_for_timeout(3000)
            
            # Check if captcha page is present by looking for the submit button
            captcha_button = page.query_selector('button[type="submit"].a-button-text')
            if captcha_button and captcha_button.is_visible():
                print("Captcha page detected, clicking continue button...")
                captcha_button.click()
                print("Clicked captcha button successfully")
                # Wait for navigation without causing browser closure
                try:
                    page.wait_for_timeout(3000)
                except:
                    pass  # Continue even if timeout occurs
            else:
                print("No captcha page detected")
        except Exception as e:
            print(f"Error checking for captcha: {e}")
            # Continue even if captcha handling fails
        
        # Search for products with retry logic
        max_retries = 3
        for retry in range(max_retries):
            try:
                print(f"Searching for '{SEARCH_KEYWORD}' (attempt {retry + 1}/{max_retries})...")
                # Special case for UK - use amazon.co.uk instead of amazon.uk
                amazon_domain = "amazon.co.uk" if MARKET == "uk" else f"amazon.{MARKET}"
                page.goto(f"https://www.{amazon_domain}/s?k={SEARCH_KEYWORD}", timeout=30000)
                page.wait_for_timeout(3000)
                print("Search completed successfully")
                break
            except Exception as e:
                print(f"Search attempt {retry + 1} failed: {e}")
                if retry < max_retries - 1:
                    print("Waiting 5 seconds before retry...")
                    page.wait_for_timeout(5000)
                else:
                    print("Failed to search after all attempts. Please check your internet connection.")
                    return
        
        # Find total pages
        print("Looking for pagination...")
        total_pages = page.evaluate("""
            () => {
                // Look for the current page number in disabled span
                const currentPageSpan = document.querySelector('.s-pagination-item.s-pagination-disabled');
                if (currentPageSpan) {
                    const pageNum = parseInt(currentPageSpan.textContent);
                    console.log('Found current page:', pageNum);
                    if (!isNaN(pageNum) && pageNum > 1) {
                        return pageNum;
                    }
                }
                
                // Fallback: look for pagination container and count pages
                const pagination = document.querySelector('.s-pagination-container');
                if (pagination) {
                    // Look for all page numbers (including disabled ones)
                    const pageElements = pagination.querySelectorAll('.s-pagination-item');
                    let maxPage = 1;
                    pageElements.forEach(element => {
                        const text = element.textContent?.trim();
                        const num = parseInt(text);
                        if (!isNaN(num) && num > maxPage) {
                            maxPage = num;
                        }
                    });
                    console.log('Max page found:', maxPage);
                    return maxPage;
                }
                
                // Last resort: look for "Go to page" links
                const pages = document.querySelectorAll('a[aria-label*="Go to page"]');
                if (pages.length > 0) {
                    const lastPage = parseInt(pages[pages.length-1].textContent);
                    console.log('Go to page method:', lastPage);
                    return isNaN(lastPage) ? 1 : lastPage;
                }
                
                return 1;
            }
        """)
        
        print(f"Found {total_pages} pages")
        
        # Process each page
        for page_num in range(1, total_pages + 1):
            print(f"Processing page {page_num}/{total_pages}...")
            
            # Go to page with retry logic
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # Special case for UK - use amazon.co.uk instead of amazon.uk
                    amazon_domain = "amazon.co.uk" if MARKET == "uk" else f"amazon.{MARKET}"
                    page.goto(f"https://www.{amazon_domain}/s?k={SEARCH_KEYWORD}&page={page_num}", timeout=60000)
                    page.wait_for_timeout(2000)
                    break
                except Exception as e:
                    print(f"Navigation attempt {retry + 1} failed: {e}")
                    if retry < max_retries - 1:
                        page.wait_for_timeout(5000)  # Wait before retry
                    else:
                        print(f"Skipping page {page_num} due to navigation failures")
                        continue
            
            # Fast loading - wait for products with minimal delays
            print(f"Loading products on page {page_num}...")
            
            # Wait for initial search results (faster timeout)
            try:
                page.wait_for_selector('[data-component-type="s-search-result"]', timeout=5000)
                print("Search results loaded")
            except:
                print("Search results not found, continuing...")
            
            # Quick scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)  # Reduced wait time
            
            # Quick scroll back
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)  # Reduced wait time
            
            print("Products loaded")
            
            # Get ALL product links - comprehensive extraction with strict duplicate prevention
            product_links = page.evaluate("""
                () => {
                    const links = [];
                    const processedHrefs = new Set();
                    const processedAsins = new Set();
                    
                    // Method 1: Standard search results
                    const searchResults = document.querySelectorAll('[data-component-type="s-search-result"]');
                    console.log('Standard search results found:', searchResults.length);
                    
                    searchResults.forEach((product, index) => {
                        const asin = product.getAttribute('data-asin');
                        
                        // Try multiple selectors for the product link
                        let link = product.querySelector('h2 a');
                        if (!link) link = product.querySelector('a[href*="/dp/"]');
                        if (!link) link = product.querySelector('a[href*="/-/en/"]');
                        
                        if (link) {
                            const href = link.getAttribute('href');
                            const title = link.textContent?.trim() || 'No title';
                            
                            // Check for duplicates by both href and asin
                            const isDuplicate = processedHrefs.has(href) || 
                                               (asin && processedAsins.has(asin));
                            
                            if (!isDuplicate) {
                                processedHrefs.add(href);
                                if (asin) processedAsins.add(asin);
                                
                                links.push({
                                    href: href,
                                    title: title,
                                    index: index,
                                    asin: asin,
                                    method: 'standard'
                                });
                            }
                        }
                    });
                    
                    // Method 2: Any product with data-asin (backup method) - only if not already captured
                    const allProducts = document.querySelectorAll('[data-asin]');
                    console.log('All products with data-asin:', allProducts.length);
                    
                    allProducts.forEach((product, index) => {
                        const asin = product.getAttribute('data-asin');
                        
                        // Skip if already processed by standard method
                        if (asin && processedAsins.has(asin)) {
                            return;
                        }
                        
                        let link = product.querySelector('h2 a');
                        if (!link) link = product.querySelector('a[href*="/dp/"]');
                        if (!link) link = product.querySelector('a[href*="/-/en/"]');
                        
                        if (link) {
                            const href = link.getAttribute('href');
                            const title = link.textContent?.trim() || 'No title';
                            
                            // Check for duplicates by href
                            if (href && !processedHrefs.has(href)) {
                                processedHrefs.add(href);
                                if (asin) processedAsins.add(asin);
                                
                                links.push({
                                    href: href,
                                    title: title,
                                    index: index,
                                    asin: asin,
                                    method: 'data-asin'
                                });
                            }
                        }
                    });
                    
                    // Filter out non-product links
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
                    
                    console.log('Total unique products found:', filteredLinks.length);
                    console.log('Processed hrefs:', processedHrefs.size);
                    console.log('Processed asins:', processedAsins.size);
                    return filteredLinks;
                }
            """)
            
            print(f"Found {len(product_links)} products on page {page_num}")
            
            # Visit each product
            for i, product in enumerate(product_links, 1):
                print(f"Product {i}/{len(product_links)}: {product['title'][:50]}...")
                
                try:
                    # Go to product page
                    if product['href'].startswith('http'):
                        full_url = product['href']
                    else:
                        # Special case for UK - use amazon.co.uk instead of amazon.uk
                        amazon_domain = "amazon.co.uk" if MARKET == "uk" else f"amazon.{MARKET}"
                        full_url = f"https://www.{amazon_domain}{product['href']}"
                    
                    page.goto(full_url)
                    page.wait_for_timeout(1000)  # Reduced wait time
                    
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
                    
                    # Check if third-party seller
                    if seller_info['seller'] and seller_info['seller'].lower() != 'amazon':
                        print(f"  Third-party seller: {seller_info['seller']}")
                        
                        # Click seller link
                        seller_link = page.query_selector('[data-csa-c-content-id="desktop-merchant-info"] a[href*="/gp/help/seller/"]')
                        if seller_link:
                            seller_link.click()
                            page.wait_for_timeout(1000)  # Reduced wait time
                            
                            # Get seller details - dynamic HTML extraction (English columns only)
                            details = page.evaluate("""
                                () => {
                                    // Extract all field-value pairs from the HTML structure
                                    const allData = {};
                                    
                                    // Look for all bold spans and their next siblings (field labels and values)
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
                                    
                                    // Extract values using dynamic HTML parsing
                                    let businessName = 'N/A';
                                    let phoneNumber = 'N/A';
                                    let email = 'N/A';
                                    let country = 'N/A';
                                    
                                    // Get business name value
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
                                    
                                    // Get phone value
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
                                    
                                    // Get email value
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
                                    
                                    // Look for country code in address (last element in indent-left spans)
                                    const addressElements = document.querySelectorAll('.indent-left span');
                                    for (let element of addressElements) {
                                        const text = element.textContent?.trim();
                                        if (text && text.length === 2 && /^[A-Z]{2}$/.test(text)) {
                                            country = text;
                                            break;
                                        }
                                    }
                                    
                                    // Debug: log all extracted data
                                    console.log('All extracted data:', allData);
                                    console.log('Values:', {businessName, phoneNumber, email, country});
                                    
                                    return {
                                        business_name: businessName,
                                        phone_number: phoneNumber,
                                        email: email,
                                        country: country
                                    };
                                }
                            """)
                            
                            # Check for duplicates before adding
                            new_seller = {
                                'Business Name': details['business_name'],
                                'Phone Number': details['phone_number'],
                                'Email': details['email'],
                                'Country': details['country']
                            }
                            
                            # Check if this seller already exists (by business name and email)
                            is_duplicate = False
                            for existing_seller in seller_data:
                                if (existing_seller['Business Name'] == new_seller['Business Name'] and 
                                    existing_seller['Email'] == new_seller['Email']):
                                    is_duplicate = True
                                    print(f"  Duplicate found - skipping: {details['business_name']} | {details['email']}")
                                    break
                            
                            if not is_duplicate:
                                # Add to Excel data
                                seller_data.append(new_seller)
                                print(f"  Added: {details['business_name']} | {details['phone_number']} | {details['email']} | {details['country']}")
                            else:
                                print(f"  Skipped duplicate: {details['business_name']} | {details['email']}")
                            
                            # Update Excel file immediately (append as processing)
                            df = pd.DataFrame(seller_data)
                            with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False, sheet_name='Sellers')
                                worksheet = writer.sheets['Sellers']
                                worksheet.column_dimensions['A'].width = 50
                                worksheet.column_dimensions['B'].width = 20
                                worksheet.column_dimensions['C'].width = 35
                                worksheet.column_dimensions['D'].width = 10
                            
                            print(f"  Excel updated with {len(seller_data)} records")
                    else:
                        print(f"  Amazon seller - skipping")
                        
                except Exception as e:
                    print(f"  Error: {e}")
                    continue
        
        # Excel file is already updated with all records during processing
        
        print(f"\nCompleted! Found {len(seller_data)} third-party sellers")
        print(f"Excel file: {excel_filename}")
        input("Press Enter to close...")
        browser.close()

if __name__ == "__main__":
    main()
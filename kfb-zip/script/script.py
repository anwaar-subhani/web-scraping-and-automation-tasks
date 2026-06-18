from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import json
import os
import pandas as pd
import shutil
from datetime import datetime

# Session file (never expires)
SESSION_FILE = "session.json"

def clean_pycache():
    """Clean up __pycache__ folders before running"""
    try:
        # Get the current script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Look for __pycache__ folders in the script directory and subdirectories
        for root, dirs, files in os.walk(script_dir):
            if '__pycache__' in dirs:
                pycache_path = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(pycache_path)
                except Exception as e:
                    pass
        
        return True
    except Exception as e:
        return False

# File paths
INPUT_FILE = "../input/input_zipcodes.txt"
OUTPUT_FOLDER = "../output"
PROCESSED_FILE = os.path.join(OUTPUT_FOLDER, "processed_zipcodes.txt")

# Generate Excel filename with current date and time
def get_excel_filename():
    """Generate Excel filename with current date and time"""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M")
    return f"output_{timestamp}.xlsx"

# Get the Excel file path (will be set when script starts)
EXCEL_FILE = None

def save_session(driver):
    """Save session data"""
    try:
        cookies = driver.get_cookies()
        
        try:
            local_storage = driver.execute_script("return window.localStorage;")
        except:
            local_storage = {}
        
        try:
            session_storage = driver.execute_script("return window.sessionStorage;")
        except:
            session_storage = {}
        
        session_data = {
            "cookies": cookies,
            "local_storage": local_storage,
            "session_storage": session_storage,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        return True
    except Exception as e:
        return False

def load_session(driver):
    """Load session data"""
    try:
        if not os.path.exists(SESSION_FILE):
            return False
        
        with open(SESSION_FILE, 'r') as f:
            session_data = json.load(f)
        
        cookies_restored = 0
        for cookie in session_data.get('cookies', []):
            try:
                clean_cookie = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False)
                }
                
                if 'domain' in cookie and cookie['domain']:
                    clean_cookie['domain'] = cookie['domain']
                
                driver.add_cookie(clean_cookie)
                cookies_restored += 1
            except:
                pass
        
        if session_data.get('local_storage'):
            for key, value in session_data['local_storage'].items():
                try:
                    driver.execute_script(f"window.localStorage.setItem('{key}', '{value}');")
                except:
                    pass
        
        if session_data.get('session_storage'):
            for key, value in session_data['session_storage'].items():
                try:
                    driver.execute_script(f"window.sessionStorage.setItem('{key}', '{value}');")
                except:
                    pass
        
        return True
        
    except Exception as e:
        return False

def check_if_logged_in(driver):
    """Check if already logged in"""
    try:
        current_url = driver.current_url
        if "login" not in current_url.lower():
            return True
        return False
    except:
        return False


def create_output_folder():
    """Create output folder if it doesn't exist"""
    try:
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        return True
    except Exception as e:
        return False

def read_zip_codes():
    """Read zip codes from input_zipcodes.txt"""
    try:
        if not os.path.exists(INPUT_FILE):
            return []
        
        with open(INPUT_FILE, 'r') as f:
            zip_codes = [line.strip() for line in f.readlines() if line.strip()]
        
        return zip_codes
    except Exception as e:
        return []

def get_processed_zip_codes():
    """Get list of already processed zip codes"""
    try:
        if not os.path.exists(PROCESSED_FILE):
            return []
        
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed = [line.strip() for line in f.readlines() if line.strip()]
        
        return processed
    except Exception as e:
        return []

def save_processed_zip_code(zip_code):
    """Save processed zip code to processed_zipcodes.txt"""
    try:
        import os
        
        # Ensure output folder exists
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        
        # Save the zip code
        with open(PROCESSED_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{zip_code}\n")
            f.flush()  # Force write to disk
        
        return True
    except Exception as e:
        return False

def remove_zip_code_from_input(zip_code):
    """Remove processed zip code from input_zipcodes.txt"""
    try:
        # Read all zip codes from input_zipcodes.txt
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            all_zip_codes = [line.strip() for line in f.readlines() if line.strip()]
        
        # Remove the processed zip code
        if zip_code in all_zip_codes:
            all_zip_codes.remove(zip_code)
            
            # Write back the remaining zip codes
            with open(INPUT_FILE, 'w') as f:
                for remaining_zip in all_zip_codes:
                    f.write(f"{remaining_zip}\n")
            
            return True
        else:
            return False
            
    except Exception as e:
        return False

def find_input_in_shadow_dom(driver):
    """Use JavaScript to find input field in Shadow DOM"""
    
    # JavaScript to search through Shadow DOM
    js_script = """
    function findInputInShadowDOM() {
        // Function to recursively search through shadow DOMs
        function searchShadowDOM(root) {
            // Look for input with placeholder containing 'Property Street Address'
            let inputs = root.querySelectorAll('input[placeholder*="Property Street Address"]');
            if (inputs.length > 0) {
                return inputs[0];
            }
            
            // Look for input with type='search'
            inputs = root.querySelectorAll('input[type="search"]');
            if (inputs.length > 0) {
                for (let input of inputs) {
                    let placeholder = input.getAttribute('placeholder') || '';
                    if (placeholder.toLowerCase().includes('property') || 
                        placeholder.toLowerCase().includes('address')) {
                        return input;
                    }
                }
            }
            
            // Search through all elements with shadow roots
            let allElements = root.querySelectorAll('*');
            for (let element of allElements) {
                if (element.shadowRoot) {
                    let found = searchShadowDOM(element.shadowRoot);
                    if (found) return found;
                }
            }
            
            return null;
        }
        
        // Start search from document
        return searchShadowDOM(document);
    }
    
    return findInputInShadowDOM();
    """
    
    return driver.execute_script(js_script)

def find_and_search_field(driver, wait, zip_code):
    """Find the search field (handles Shadow DOM) and type the given zip code"""
    try:
        current_url = driver.current_url
        
        # Smart page load detection
        try:
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            pass
        
        # Wait for Lightning components to initialize (smart wait)
        try:
            WebDriverWait(driver, 2).until(
                lambda d: d.execute_script("""
                    return document.querySelectorAll('*').length > 100 && 
                           document.readyState === 'complete'
                """)
            )
        except:
            pass
        
        # Try to find the input using JavaScript
        search_field = None
        try:
            search_field = find_input_in_shadow_dom(driver)
            
            if search_field:
                # Type into the field using JavaScript
                driver.execute_script(f"arguments[0].value = '{zip_code}';", search_field)
                
                # Trigger input event
                driver.execute_script("""
                    let event = new Event('input', { bubbles: true });
                    arguments[0].dispatchEvent(event);
                """, search_field)
                
                # Press Enter using JavaScript
                driver.execute_script("""
                    let event = new KeyboardEvent('keydown', {
                        key: 'Enter',
                        code: 'Enter',
                        keyCode: 13,
                        which: 13,
                        bubbles: true
                    });
                    arguments[0].dispatchEvent(event);
                """, search_field)
                
                # Smart wait for search results
                try:
                    WebDriverWait(driver, 3).until(
                        lambda d: d.execute_script("""
                            return document.readyState === 'complete' && 
                                   document.querySelectorAll('a[c-searchproperty_searchproperty]').length > 0
                        """)
                    )
                except:
                    pass
                
                return True
                
        except Exception as e:
            pass
        
        # Strategy 2: Try regular Selenium selectors (non-Shadow DOM)
        regular_selectors = [
            "input[placeholder='Enter Property Street Address...']",
            "input[placeholder*='Property Street Address']",
            "input[type='search'][placeholder*='Property']",
            "input.slds-input[type='search']",
            "input[type='search']"
        ]
        
        for i, selector in enumerate(regular_selectors):
            try:
                search_field = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                if search_field.is_displayed() and search_field.is_enabled():
                    search_field.clear()
                    search_field.send_keys(zip_code)
                    search_field.send_keys(Keys.RETURN)
                    
                    # Smart wait for search results
                    try:
                        WebDriverWait(driver, 3).until(
                            lambda d: d.execute_script("""
                                return document.readyState === 'complete' && 
                                       document.querySelectorAll('a[c-searchproperty_searchproperty]').length > 0
                            """)
                        )
                    except:
                        pass
                    
                    return True
                    
            except Exception as e:
                continue
        
        return False
            
    except Exception as e:
        return False

def count_property_links(driver):
    """Count the number of property links in search results using JavaScript only"""
    try:
        # Smart wait for search results to load
        try:
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script("""
                    return document.readyState === 'complete' && 
                           document.querySelectorAll('*').length > 200
                """)
            )
        except:
            pass
        
        # Smart wait for property links to appear
        try:
            WebDriverWait(driver, 2).until(
                lambda d: d.execute_script("""
                    return document.querySelectorAll('a[c-searchproperty_searchproperty]').length > 0
                """)
            )
        except:
            pass
        
        # Use JavaScript to find links in Shadow DOM (multiple attempts)
        for attempt in range(3):
            try:
                js_find_links = """
                function findPropertyLinks() {
                    let allLinks = [];
                    let seenIds = new Set(); // To avoid duplicates
                    
                    function searchDOM(root, depth) {
                        if (depth > 15) return; // Prevent infinite recursion
                        
                        // Look for links with c-searchproperty_searchproperty and data-id
                        let links = root.querySelectorAll('a[c-searchproperty_searchproperty][data-id]');
                        links.forEach(link => {
                            let dataId = link.getAttribute('data-id');
                            if (dataId && !seenIds.has(dataId)) {
                                seenIds.add(dataId);
                                allLinks.push({
                                    element: link,
                                    dataId: dataId,
                                    text: link.textContent.trim(),
                                    href: link.href
                                });
                            }
                        });
                        
                        // Search through all elements with shadow roots
                        let allElements = root.querySelectorAll('*');
                        allElements.forEach(element => {
                            if (element.shadowRoot) {
                                searchDOM(element.shadowRoot, depth + 1);
                            }
                        });
                        
                        // Also search in slot elements (Lightning Web Components)
                        let slotElements = root.querySelectorAll('slot');
                        slotElements.forEach(slot => {
                            if (slot.assignedNodes) {
                                slot.assignedNodes().forEach(node => {
                                    if (node.nodeType === Node.ELEMENT_NODE) {
                                        searchDOM(node, depth + 1);
                                    }
                                });
                            }
                        });
                    }
                    
                    searchDOM(document, 0);
                    return allLinks;
                }
                
                return findPropertyLinks();
                """
                
                js_links = driver.execute_script(js_find_links)
                if js_links and len(js_links) > 0:
                    return len(js_links)
                else:
                    if attempt < 2:  # Smart wait only if not last attempt
                        try:
                            WebDriverWait(driver, 1).until(
                                lambda d: d.execute_script("""
                                    return document.querySelectorAll('a[c-searchproperty_searchproperty]').length > 0
                                """)
                            )
                        except:
                            pass
                    
            except Exception as e:
                if attempt < 2:  # Smart wait only if not last attempt
                    try:
                        WebDriverWait(driver, 1).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    except:
                        pass
        
        return 0
        
    except Exception as e:
        return 0

def click_property_link(driver, link_index):
    """Click on a specific property link by index using JavaScript only"""
    try:
        # Use JavaScript to find and click the link
        try:
            js_click_link = f"""
            function clickPropertyLinkByIndex(index) {{
                let allLinks = [];
                let seenIds = new Set(); // To avoid duplicates
                
                function searchDOM(root, depth) {{
                    if (depth > 15) return;
                    
                    let links = root.querySelectorAll('a[c-searchproperty_searchproperty][data-id]');
                    links.forEach(link => {{
                        let dataId = link.getAttribute('data-id');
                        if (dataId && !seenIds.has(dataId)) {{
                            seenIds.add(dataId);
                            allLinks.push(link);
                        }}
                    }});
                    
                    let allElements = root.querySelectorAll('*');
                    allElements.forEach(element => {{
                        if (element.shadowRoot) {{
                            searchDOM(element.shadowRoot, depth + 1);
                        }}
                    }});
                    
                    // Also search in slot elements (Lightning Web Components)
                    let slotElements = root.querySelectorAll('slot');
                    slotElements.forEach(slot => {{
                        if (slot.assignedNodes) {{
                            slot.assignedNodes().forEach(node => {{
                                if (node.nodeType === Node.ELEMENT_NODE) {{
                                    searchDOM(node, depth + 1);
                                }}
                            }});
                        }}
                    }});
                }}
                
                searchDOM(document, 0);
                
                if (allLinks.length > index) {{
                    let link = allLinks[index];
                    let dataId = link.getAttribute('data-id');
                    let text = link.textContent.trim();
                    link.click();
                    return true;
                }}
                return false;
            }}
            
            return clickPropertyLinkByIndex({link_index});
            """
            
            success = driver.execute_script(js_click_link)
            if success:
                # Smart wait for property page to fully load with multiple checks
                wait_for_property_page_load(driver)
                return True
            else:
                return False
                
        except Exception as e:
            return False
        
    except Exception as e:
        return False

def wait_for_property_page_load(driver):
    """Wait for property page to fully load with comprehensive checks"""
    try:
        # Wait for basic page load
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Wait for Lightning components to initialize
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("""
                return document.querySelectorAll('*').length > 200 && 
                       document.readyState === 'complete'
            """)
        )
        
        # Wait for property-specific elements to appear
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("""
                // Check for property page indicators
                let hasPropertyElements = false;
                
                // Look for common property page elements
                const propertyIndicators = [
                    'lightning-card',
                    'lightning-input',
                    'button[class*="accordion"]',
                    'input[class*="slds-input"]',
                    '[data-field-name]'
                ];
                
                for (let selector of propertyIndicators) {
                    if (document.querySelector(selector)) {
                        hasPropertyElements = true;
                        break;
                    }
                }
                
                return hasPropertyElements;
            """)
        )
        
        # Additional wait for dynamic content to load
        time.sleep(2)
        
        # Wait for any loading spinners to disappear
        WebDriverWait(driver, 3).until(
            lambda d: d.execute_script("""
                // Check for loading spinners
                const spinners = document.querySelectorAll('[class*="spinner"], [class*="loading"], [class*="slds-spinner"]');
                return spinners.length === 0;
            """)
        )
        
        # Final wait for stability
        time.sleep(1)
        
        return True
        
    except Exception as e:
        # If any wait fails, still wait a bit for basic loading
        time.sleep(3)
        return True

def verify_property_page_ready(driver):
    """Verify that the property page is ready for data extraction"""
    try:
        # Check if we have the basic elements that indicate a property page is loaded
        is_ready = driver.execute_script("""
            // Check for property page indicators
            let hasPropertyElements = false;
            let hasInputFields = false;
            
            // Look for common property page elements
            const propertyIndicators = [
                'lightning-card',
                'lightning-input',
                'button[class*="accordion"]',
                'input[class*="slds-input"]',
                '[data-field-name]',
                'lightning-formatted-text',
                'lightning-formatted-phone',
                'lightning-formatted-email'
            ];
            
            for (let selector of propertyIndicators) {
                if (document.querySelector(selector)) {
                    hasPropertyElements = true;
                    break;
                }
            }
            
            // Check for input fields specifically
            const inputSelectors = [
                'input[class*="slds-input"]',
                'lightning-input',
                'lightning-combobox',
                'lightning-textarea',
                'input[type="text"]',
                'input[type="email"]',
                'input[type="tel"]'
            ];
            
            for (let selector of inputSelectors) {
                if (document.querySelector(selector)) {
                    hasInputFields = true;
                    break;
                }
            }
            
            // Also check for loading indicators that should be gone
            const loadingIndicators = document.querySelectorAll('[class*="spinner"], [class*="loading"], [class*="slds-spinner"]');
            const hasNoLoading = loadingIndicators.length === 0;
            
            return hasPropertyElements && hasInputFields && hasNoLoading;
        """)
        
        return is_ready
        
    except Exception as e:
        return False

def check_property_criteria(driver):
    """Check if property meets the configured criteria"""
    try:
        # Import config fresh each time (no caching)
        import config
        
        # Check which criteria are enabled in config
        kfb_stage_required = config.KFB_STAGE_INSTALLED
        pending_signature_required = config.PENDING_SIGNATURE
        
        # Only search for fields that are set to True in config
        kfb_stage_found = False
        pending_signature_found = False
        
        if kfb_stage_required == True:
            kfb_stage_found = search_for_field_value_in_shadow_dom(driver, "KFB Stage", "Installed")
        
        if pending_signature_required == True:
            pending_signature_found = search_for_field_value_in_shadow_dom(driver, "3P Communication Stage", "Contract Sent - Pending Signature")
        
        # Determine if property meets criteria based on config
        if kfb_stage_required == True and pending_signature_required == True:
            # CASE 1: Both criteria required - property must have BOTH specific values
            meets_criteria = kfb_stage_found and pending_signature_found
        elif kfb_stage_required == True and pending_signature_required == False:
            # CASE 2: Only KFB Stage required - property must have KFB Stage = 'Installed'
            meets_criteria = kfb_stage_found
        elif kfb_stage_required == False and pending_signature_required == True:
            # CASE 3: Only 3P Communication Stage required - property must have 3P Communication Stage = 'Contract Sent - Pending Signature'
            meets_criteria = pending_signature_found
        else:
            # CASE 4: Both criteria are False - process ALL properties
            meets_criteria = True
        
        return meets_criteria
        
    except Exception as e:
        return False

def search_for_field_value_in_shadow_dom(driver, field_label, expected_value):
    """Search for a specific field value in Shadow DOM using JavaScript"""
    try:
        # Optimized JavaScript search with correct depth (3 levels for KFB Stage)
        js_search = f"""
        function findFieldValueByLabel(labelText, expectedValue) {{
            function searchWithDepth(root, currentDepth) {{
                if (currentDepth > 3) return false; // Limit to 3 levels for KFB Stage
                
                // Search for labels
                const labels = root.querySelectorAll('label');
                for (let label of labels) {{
                    if (label.textContent && label.textContent.includes(labelText)) {{
                        const container = label.closest('div') || label.parentElement;
                        if (container) {{
                            const input = container.querySelector('input');
                            if (input) {{
                                const value = input.value || input.textContent || '';
                                if (value.toLowerCase().includes(expectedValue.toLowerCase())) {{
                                    return true;
                                }}
                            }}
                        }}
                    }}
                }}
                
                // Search shadow roots (limited to 3 levels)
                const elements = root.querySelectorAll('*');
                for (let el of elements) {{
                    if (el.shadowRoot) {{
                        const result = searchWithDepth(el.shadowRoot, currentDepth + 1);
                        if (result) return result;
                    }}
                }}
                
                return false;
            }}
            
            return searchWithDepth(document, 0);
        }}
        
        return findFieldValueByLabel('{field_label}', '{expected_value}');
        """
        
        # Execute JavaScript with timeout protection
        try:
            result = driver.execute_script(js_search)
            return result
                
        except Exception as e:
            return False
        
    except Exception as e:
        return False


def extract_property_data(driver):
    """Extract ALL input fields from the current page through Shadow DOM"""
    try:
        # Verify the page is ready for data extraction
        if not verify_property_page_ready(driver):
            time.sleep(3)
        
        # First, expand all accordion sections to reveal property data
        expand_accordions_js = """
        function expandAllAccordions() {
            // Find and click all accordion buttons to expand sections
            const accordionButtons = document.querySelectorAll('button[class*="accordion"], button[aria-expanded="false"]');
            accordionButtons.forEach(button => {
                if (button.textContent && (
                    button.textContent.includes('Property Details') ||
                    button.textContent.includes('Property') ||
                    button.textContent.includes('Details') ||
                    button.textContent.includes('Information')
                )) {
                    button.click();
                }
            });
            
            // Also look in shadow DOM
            function expandInShadowDOM(root, currentDepth) {
                if (currentDepth > 3) return;
                
                const shadowButtons = root.querySelectorAll('button[class*="accordion"], button[aria-expanded="false"]');
                shadowButtons.forEach(button => {
                    if (button.textContent && (
                        button.textContent.includes('Property Details') ||
                        button.textContent.includes('Property') ||
                        button.textContent.includes('Details') ||
                        button.textContent.includes('Information')
                    )) {
                        button.click();
                    }
                });
                
                const elements = root.querySelectorAll('*');
                elements.forEach(element => {
                    if (element.shadowRoot) {
                        expandInShadowDOM(element.shadowRoot, currentDepth + 1);
                    }
                });
            }
            
            expandInShadowDOM(document, 0);
        }
        
        expandAllAccordions();
        """
        
        # Execute accordion expansion
        driver.execute_script(expand_accordions_js)
        
        # Wait for accordions to expand and content to load
        time.sleep(3)
        
        # Verify accordions expanded successfully
        accordion_expanded = driver.execute_script("""
            // Check if accordions are expanded by looking for visible content
            const accordionContent = document.querySelectorAll('[aria-expanded="true"], .slds-show, .slds-is-open');
            return accordionContent.length > 0;
        """)
        
        if not accordion_expanded:
            time.sleep(2)
        
        # Extract ALL input fields dynamically from property details section
        js_extract = """
        function extractAllPropertyInputs() {
            let allFields = [];
            let processedInputs = new Set();
            
            // Function to find ALL input containers in property details
            function findAllInputContainers(root, currentDepth) {
                if (currentDepth > 5) return;
                
                // Find ALL possible input elements - comprehensive search
                const inputSelectors = [
                    'input[class*="slds-input"]',
                    'input[part="input"]',
                    'input[type="text"]',
                    'input[type="email"]',
                    'input[type="tel"]',
                    'input[type="url"]',
                    'input[type="number"]',
                    'input[type="date"]',
                    'input[type="datetime-local"]',
                    'input[type="time"]',
                    'input[type="password"]',
                    'select',
                    'textarea',
                    'lightning-input input',
                    'lightning-combobox input',
                    'lightning-textarea textarea',
                    'lightning-datepicker input',
                    'lightning-lookup input',
                    'lightning-dual-listbox input',
                    '[contenteditable="true"]',
                    '[role="textbox"]',
                    'input:not([type="hidden"]):not([type="button"]):not([type="submit"]):not([type="reset"])'
                ];
                
                // Search for inputs in current root
                inputSelectors.forEach(selector => {
                    try {
                        const elements = root.querySelectorAll(selector);
                        elements.forEach(element => {
                            // Skip if already processed or hidden
                            if (processedInputs.has(element) || element.type === 'hidden') return;
                            processedInputs.add(element);
                            
                            let fieldValue = '';
                            
                            // Extract value based on element type
                            if (element.tagName === 'INPUT') {
                                if (element.type === 'checkbox' || element.type === 'radio') {
                                    fieldValue = element.checked ? 'Yes' : 'No';
                                } else {
                                    fieldValue = element.value || '';
                                }
                            } else if (element.tagName === 'SELECT') {
                                fieldValue = element.selectedOptions[0]?.textContent || element.value || '';
                            } else if (element.tagName === 'TEXTAREA') {
                                fieldValue = element.value || '';
                            } else if (element.contentEditable === 'true') {
                                fieldValue = element.textContent || element.innerText || '';
                            } else if (element.getAttribute('role') === 'textbox') {
                                fieldValue = element.value || element.textContent || '';
                            } else {
                                // For any other element, try to get value
                                fieldValue = element.value || element.textContent || element.innerText || '';
                            }
                            
                            // Only add fields with actual values (not empty)
                            if (fieldValue && fieldValue.trim() && fieldValue.trim() !== '') {
                                allFields.push(fieldValue.trim());
                            }
                        });
                    } catch (e) {
                        // Continue if selector fails
                    }
                });
                
                // Search shadow roots recursively
                    const elements = root.querySelectorAll('*');
                elements.forEach(element => {
                    try {
                        if (element.shadowRoot) {
                            findAllInputContainers(element.shadowRoot, currentDepth + 1);
                        }
                    } catch (e) {
                        // Continue if element access fails
                    }
                });
            }
            
            // Start extraction from document root
            findAllInputContainers(document, 0);
            
            return allFields;
        }
        
        return extractAllPropertyInputs();
        """
        
        # Try extraction with retry mechanism for better reliability
        max_retries = 2
        best_result = []
        
        for attempt in range(max_retries):
            try:
                extracted_data = driver.execute_script(js_extract)
                
                if extracted_data and len(extracted_data) > 0:
                    # If this attempt got more data than previous, use it
                    if len(extracted_data) > len(best_result):
                        best_result = extracted_data
                    
                    # If we got a good amount of data, we can proceed
                    if len(extracted_data) >= 5:  # Reasonable minimum for property data
                        break
                    else:
                        # If we got few fields, wait a bit and try again
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue
        
        if best_result and len(best_result) > 0:
            # Return as a simple list of values (no column names)
            return best_result
        else:
            return []
        
    except Exception as e:
        return []

def is_duplicate_record(property_data, existing_data):
    """Check if the property data already exists in the Excel file"""
    try:
        if not property_data or len(property_data) == 0:
            return True
        
        if existing_data.empty:
            return False
        
        # Convert property data to a comparable format
        new_record = [str(val).strip().lower() if val else '' for val in property_data]
        
        # Check each existing row for duplicates
        for index, row in existing_data.iterrows():
            # Convert existing row to comparable format
            existing_record = [str(val).strip().lower() if pd.notna(val) and val else '' for val in row]
            
            # Method 1: Exact match (same number of fields)
            if len(new_record) == len(existing_record):
                matches = 0
                total_comparable_fields = 0
                
                for i in range(len(new_record)):
                    new_val = new_record[i]
                    existing_val = existing_record[i]
                    
                    # Only compare non-empty fields
                    if new_val and existing_val:
                        total_comparable_fields += 1
                        if new_val == existing_val:
                            matches += 1
                
                # If we have comparable fields and most match, consider it a duplicate
                if total_comparable_fields > 0 and matches >= total_comparable_fields * 0.8:
                    return True
            
            # Method 2: Cross-reference match (different number of fields but same property)
            else:
                # Find common non-empty values between the two records
                new_set = set(val for val in new_record if val)
                existing_set = set(val for val in existing_record if val)
                
                # Calculate intersection (common values)
                common_values = new_set.intersection(existing_set)
                
                # If there are significant common values, it might be the same property
                if len(common_values) >= 3:  # At least 3 common values
                    # Calculate similarity ratio
                    total_unique_values = len(new_set.union(existing_set))
                    similarity_ratio = len(common_values) / total_unique_values if total_unique_values > 0 else 0
                    
                    # If similarity is high enough, consider it a duplicate
                    if similarity_ratio >= 0.6:  # 60% similarity threshold
                        return True
        
        return False
        
    except Exception as e:
        return False

def export_to_excel(property_data, zip_code):
    """Export property data to Excel file (no column names, just values)"""
    try:
        # Ensure output folder exists
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        
        # Clean up any Excel lock files
        excel_filename = os.path.basename(EXCEL_FILE)
        lock_file = os.path.join(OUTPUT_FOLDER, f"~${excel_filename}")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except:
                pass
        
        # Check if Excel file exists and is accessible
        if os.path.exists(EXCEL_FILE):
            # Check for lock file (indicates Excel has file open)
            excel_filename = os.path.basename(EXCEL_FILE)
            lock_file = os.path.join(OUTPUT_FOLDER, f"~${excel_filename}")
            if os.path.exists(lock_file):
                pass
            
            # Read existing data
            try:
                df_existing = pd.read_excel(EXCEL_FILE, header=None)
            except PermissionError:
                df_existing = pd.DataFrame()
            except Exception as e:
                df_existing = pd.DataFrame()
        else:
            df_existing = pd.DataFrame()
        
        # Create new row from the list of values
        if property_data and len(property_data) > 0:
            # Check for duplicates before adding
            if is_duplicate_record(property_data, df_existing):
                return True
            
            new_row = pd.DataFrame([property_data])
            
            # Append to existing data
            df_combined = pd.concat([df_existing, new_row], ignore_index=True)
        else:
            df_combined = df_existing
        
        # Save to Excel with retry logic for permission issues (no headers)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df_combined.to_excel(EXCEL_FILE, index=False, header=False)
                break
            except PermissionError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise e
            except Exception as e:
                raise e
        
        # Auto-adjust column widths
        try:
            from openpyxl import load_workbook
            wb = load_workbook(EXCEL_FILE)
            ws = wb.active
            
            # Auto-adjust column widths
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # Set column width (with some padding)
                adjusted_width = min(max_length + 2, 50)  # Max width of 50
                ws.column_dimensions[column_letter].width = adjusted_width
            
            wb.save(EXCEL_FILE)
        except ImportError:
            pass
        except Exception as e:
            pass
        
        return True
        
    except Exception as e:
        return False

def process_property_page(driver, zip_code):
    """Process the current property page"""
    try:
        current_url = driver.current_url
        
        # Check if property meets configured criteria
        meets_criteria = check_property_criteria(driver)
        
        if not meets_criteria:
            return True
        
        # Extract property data
        property_data = extract_property_data(driver)
        
        if property_data and len(property_data) > 0:
            export_to_excel(property_data, zip_code)
        
        # Smart wait for processing completion
        try:
            WebDriverWait(driver, 1).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            pass
        
        return True
        
    except Exception as e:
        return False

def go_back_to_search(driver):
    """Go back to search results page"""
    try:
        # Try browser back button
        driver.back()
        
        # Smart wait for search results page to load
        try:
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script("""
                    return document.readyState === 'complete' && 
                           document.querySelectorAll('a[c-searchproperty_searchproperty]').length > 0
                """)
            )
        except:
            pass
        
        return True
        
    except Exception as e:
        return False

def process_all_zip_codes(driver, wait):
    """Process all zip codes from input_zipcodes.txt one by one"""
    try:
        # Create output folder
        if not create_output_folder():
            return False
        
        # Read zip codes
        zip_codes = read_zip_codes()
        if not zip_codes:
            print("No zip codes found in input file")
            return False
        
        # Process each zip code
        for i, zip_code in enumerate(zip_codes, 1):
            try:
                print(f"Zip {i}/{len(zip_codes)}: {zip_code}")
                
                # Search for the zip code
                search_success = find_and_search_field(driver, wait, zip_code)
                
                if search_success:
                    # Count property links
                    property_count = count_property_links(driver)
                    print(f"  Found {property_count} properties")
                    
                    if property_count > 0:
                        # Process each property link
                        for property_index in range(property_count):
                            try:
                                # Click on the property link
                                link_clicked = click_property_link(driver, property_index)
                                
                                if link_clicked:
                                    # Process the property page
                                    process_property_page(driver, zip_code)
                                    
                                    # Go back to search results
                                    go_back_to_search(driver)
                                    
                                    # Re-search the same zip code for next iteration
                                    if property_index < property_count - 1:
                                        find_and_search_field(driver, wait, zip_code)
                                    
                            except Exception as e:
                                go_back_to_search(driver)
                                continue
                        
                        # Mark zip code as processed
                        save_result = save_processed_zip_code(zip_code)
                        if save_result:
                            remove_result = remove_zip_code_from_input(zip_code)
                    else:
                        # Mark as processed even if no properties found
                        save_result = save_processed_zip_code(zip_code)
                        if save_result:
                            remove_result = remove_zip_code_from_input(zip_code)
                    
            except Exception as e:
                continue
        
        return True
        
    except Exception as e:
        return False

def continuous_monitoring_loop(driver, wait):
    """Continuously monitor input file for new zip codes and process them"""
    print("Monitoring input file for zip codes...")
    
    while True:
        try:
            # Read current zip codes from input file
            zip_codes = read_zip_codes()
            
            if zip_codes:
                print(f"Processing {len(zip_codes)} zip codes...")
                process_all_zip_codes(driver, wait)
                
                # Check if input file is now empty
                remaining_zip_codes = read_zip_codes()
                if not remaining_zip_codes:
                    time.sleep(2)
                    final_check = read_zip_codes()
                    if not final_check:
                        print("All zip codes processed - script complete")
                        break
                    continue
                else:
                    continue
                
            else:
                time.sleep(2)
                final_check = read_zip_codes()
                if not final_check:
                    print("No zip codes found - script complete")
                    break
                continue
            
        except KeyboardInterrupt:
            print("Script stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            break

def wait_for_otp(driver):
    """Wait for user to enter OTP manually"""
    while True:
        try:
            current_url = driver.current_url
            
            if "login" not in current_url.lower() and "otp" not in current_url.lower():
                return True
            
            time.sleep(0.5)
            
        except:
            return False

def main():
    """Main function"""
    global EXCEL_FILE
    
    print("KFB Web Scraper Starting...")
    
    # Clean up __pycache__ folders before starting
    clean_pycache()
    
    # Set the Excel file path with current timestamp
    EXCEL_FILE = os.path.join(OUTPUT_FOLDER, get_excel_filename())
    print(f"Output file: {EXCEL_FILE}")
    
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Disable background services to eliminate Google API errors
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    chrome_options.add_argument("--disable-hang-monitor")
    chrome_options.add_argument("--disable-prompt-on-repost")
    chrome_options.add_argument("--disable-domain-reliability")
    chrome_options.add_argument("--disable-component-extensions-with-background-pages")
    chrome_options.add_argument("--disable-background-downloads")
    chrome_options.add_argument("--disable-client-side-phishing-detection")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--log-level=3")
    
    # Disable notifications and popups
    prefs = {
        "profile.default_content_setting_values": {
            "notifications": 2,
            "geolocation": 2,
            "media_stream": 2,
        },
        "profile.managed_default_content_settings": {
            "images": 2
        }
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_script_timeout(2)  # Set 2-second timeout for JavaScript execution
    wait = WebDriverWait(driver, 2)
    
    try:
        driver.get("https://kfb.my.site.com")
        
        # Smart wait for initial page load
        try:
            WebDriverWait(driver, 2).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            pass
        
        session_loaded = load_session(driver)
        
        if session_loaded:
            driver.get("https://kfb.my.site.com/cac/s/")
            
            # Smart wait for portal page load
            try:
                WebDriverWait(driver, 3).until(
                    lambda d: d.execute_script("""
                        return document.readyState === 'complete' && 
                               document.querySelectorAll('*').length > 100
                    """)
                )
            except:
                pass
            
            if check_if_logged_in(driver):
                print("Login successful!")
                save_session(driver)
                
                # Start continuous monitoring loop
                continuous_monitoring_loop(driver, wait)
                
                return
        
        # Fresh login
        import config
        driver.get(config.KFB_LOGIN_URL)
        
        # Smart wait for login page load
        try:
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script("""
                    return document.readyState === 'complete' && 
                           document.querySelectorAll('input[type="text"], input[type="password"]').length > 0
                """)
            )
        except:
            pass
        
        username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")))
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        login_button = driver.find_element(By.CSS_SELECTOR, "button")
        
        username_field.clear()
        username_field.send_keys(config.DEFAULT_USERNAME)
        
        password_field.clear()
        password_field.send_keys(config.DEFAULT_PASSWORD)
        
        login_button.click()
        
        # Smart wait for login processing
        try:
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script("""
                    return document.readyState === 'complete' && 
                           (document.URL.includes('otp') || 
                            document.URL.includes('verification') || 
                            !document.URL.includes('login'))
                """)
            )
        except:
            pass
        
        current_url = driver.current_url
        
        if "otp" in current_url.lower() or "verification" in current_url.lower() or "KFBLoginVerification" in current_url:
            otp_success = wait_for_otp(driver)
            
            if otp_success:
                print("Login successful!")
                save_session(driver)
                
                # Start continuous monitoring loop
                continuous_monitoring_loop(driver, wait)
            else:
                driver.quit()
        
        elif "login" not in current_url.lower():
            print("Login successful!")
            save_session(driver)
            
            # Start continuous monitoring loop
            continuous_monitoring_loop(driver, wait)
        else:
            driver.quit()
    
    except Exception as e:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    main()

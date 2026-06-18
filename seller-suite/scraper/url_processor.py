"""URL processing with pagination"""
import os
import csv
import queue
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from . import config
from . import progress
from . import file_manager
from . import page_processor
from . import browser_manager
from . import js_scripts
from .utils import normalize_url, extract_page_number_from_url, extract_filename_from_url, build_page_url, visit_amazon_home_first

def process_single_url(search_url, thread_id):
    """Process a single search URL in a separate browser instance"""
    print(f"[Thread {thread_id}] Processing URL: {search_url[:80]}...")
    
    # Check if shutdown was requested
    if config.shutdown_flag.is_set():
        print(f"[Thread {thread_id}] Shutdown requested, stopping...")
        return
    
    # Load progress for THIS SPECIFIC URL ONLY - each thread is independent
    normalized_key = normalize_url(search_url)
    
    # Load progress using new format
    url_progress = progress.load_progress()
    stored_total_pages = None
    pages_to_resume = {}  # page_num -> product_index
    
    if normalized_key in url_progress:
        data = url_progress[normalized_key]
        stored_total_pages = data.get('total_pages')
        pages_to_resume = data.get('pages', {})
        print(f"[Thread {thread_id}] Found progress for URL: {len(pages_to_resume)} page(s) in progress, total_pages: {stored_total_pages}")
        for p_num, p_idx in pages_to_resume.items():
            print(f"[Thread {thread_id}]   Page {p_num}: resume from product {p_idx + 1}")
    
    # Determine starting pages
    # If we have pages in progress, resume those pages
    # Otherwise, start from page 1
    if pages_to_resume:
        # We have pages to resume - these will be processed first
        resume_pages = sorted(pages_to_resume.keys())
        start_page = min(resume_pages)
        print(f"[Thread {thread_id}] Resuming: {len(resume_pages)} page(s) in progress, starting from page {start_page}")
    else:
        start_page = 1
        print(f"[Thread {thread_id}] Starting fresh from page 1")
    
    # Generate filename for this URL
    excel_filename = extract_filename_from_url(search_url)
    print(f"[Thread {thread_id}] Results will be saved to: {excel_filename}")
    
    thread_seller_data = []
    
    # Get proxy for this thread if enabled (returns string format)
    proxy_string = browser_manager.get_next_proxy() if config.USE_PROXIES and config.PROXIES_LIST else None
    
    if proxy_string:
        print(f"[Thread {thread_id}] Using proxy: {proxy_string}")
    else:
        print(f"[Thread {thread_id}] Running without proxy")
    
    driver = None
    try:
        try:
            # Create driver with proxy if provided
            driver = page_processor.get_driver(proxy_string)
            print(f"[Thread {thread_id}] Browser launched{' with proxy' if proxy_string else ' without proxy'}")
        except Exception as e:
            print(f"[Thread {thread_id}] Failed to launch browser: {e}")
            if proxy_string:
                print(f"[Thread {thread_id}] Proxy might be invalid, trying without proxy...")
                try:
                    driver = page_processor.get_driver(None)
                    proxy_string = None  # Clear proxy for page processing
                    print(f"[Thread {thread_id}] Browser launched without proxy")
                except Exception as e2:
                    print(f"[Thread {thread_id}] Failed to launch browser without proxy: {e2}")
                    return
            else:
                return
        
        try:
            # If using proxies, visit Amazon home first BEFORE going to actual URL
            if config.USE_PROXIES and proxy_string:
                visit_amazon_home_first(driver, search_url)
            
            # Navigate to first page with retry logic
            max_retries = 3
            for retry in range(max_retries):
                if config.shutdown_flag.is_set():
                    return
                try:
                    print(f"[Thread {thread_id}] Loading URL (attempt {retry + 1}/{max_retries})...")
                    driver.get(search_url)
                    if config.shutdown_flag.is_set():
                        return
                    time.sleep(3)
                    print(f"[Thread {thread_id}] Successfully loaded URL")
                    break
                except Exception as e:
                    print(f"[Thread {thread_id}] Load attempt {retry + 1} failed: {e}")
                    if retry < max_retries - 1:
                        time.sleep(5)
                    else:
                        print(f"[Thread {thread_id}] Failed to load URL after all attempts")
                        return
            
            # Check for captcha page
            try:
                captcha_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"].a-button-text')
                if captcha_button and captcha_button.is_displayed():
                    print(f"[Thread {thread_id}] Captcha page detected, clicking continue button...")
                    driver.execute_script("arguments[0].click();", captcha_button)
                    time.sleep(3)
            except Exception as e:
                # Captcha button not found, that's OK
                pass
            
            # Find total pages - use stored value if available, otherwise detect it
            if stored_total_pages:
                total_pages = stored_total_pages
                print(f"[Thread {thread_id}] Using stored total pages: {total_pages}, starting from page {start_page}")
            else:
                print(f"[Thread {thread_id}] Looking for pagination...")
                total_pages = driver.execute_script(f"return ({js_scripts.GET_TOTAL_PAGES_SCRIPT})();")
                
                print(f"[Thread {thread_id}] Detected {total_pages} total pages, saving to progress file")
                # Save the total_pages for future reference
                progress.update_total_pages(search_url, total_pages)
            
            # Determine max pages to process - use exact detected total, no buffer
            if stored_total_pages:
                max_pages_to_check = stored_total_pages
                print(f"[Thread {thread_id}] Will process up to page {max_pages_to_check} (stored total pages)")
            else:
                # Use exact detected total pages (no buffer, no minimum)
                if total_pages and total_pages > 0:
                    max_pages_to_check = total_pages
                else:
                    # Fallback: if detection failed, process at least page 1
                    max_pages_to_check = 1
                print(f"[Thread {thread_id}] Will process up to page {max_pages_to_check} (exact detected total)")
            
            # Process pages using a dynamic queue - threads pull pages as they become available
            # Ensure start_page doesn't exceed max_pages_to_check
            if start_page > max_pages_to_check:
                print(f"[Thread {thread_id}] Warning: Start page {start_page} exceeds max pages {max_pages_to_check}. Resetting to page 1.")
                start_page = 1
                pages_to_resume = {}
            
            # Create a queue for pages to process with their resume positions
            # Format: (page_num, product_index)
            page_queue = queue.Queue()
            
            # First, add pages that need to be resumed (with their product_index)
            for page_num in sorted(pages_to_resume.keys()):
                if page_num <= max_pages_to_check:
                    product_idx = pages_to_resume[page_num]
                    page_queue.put((page_num, product_idx))
                    print(f"[Thread {thread_id}] Queueing page {page_num} to resume from product {product_idx + 1}")
            
            # Then add remaining pages (starting from product 0)
            pages_to_process = list(range(start_page, max_pages_to_check + 1))
            for page_num in pages_to_process:
                if page_num not in pages_to_resume:
                    page_queue.put((page_num, 0))
            
            print(f"[Thread {thread_id}] Processing {page_queue.qsize()} pages with {config.CONCURRENT_PAGES} concurrent workers")
            
            # Track processed pages and results
            processed_pages = set()
            all_seller_data = []
            
            # Check shutdown before starting executor
            if config.shutdown_flag.is_set():
                print(f"[Thread {thread_id}] Shutdown requested before starting page processing")
                return
            
            # Process pages dynamically - threads pull from queue as they become available
            executor = ThreadPoolExecutor(max_workers=config.CONCURRENT_PAGES)
            # Register executor for shutdown
            with config.executors_lock:
                config.active_executors.append(executor)
            
            try:
                # Submit initial batch of pages
                future_to_page = {}
                
                # Submit up to CONCURRENT_PAGES initial tasks
                initial_count = min(config.CONCURRENT_PAGES, page_queue.qsize())
                for _ in range(initial_count):
                    # CRITICAL: Atomically check flag BEFORE doing anything
                    if not config.can_create_new_threads():
                        print(f"[Thread {thread_id}] NO_NEW_THREADS detected! Cancelling initial pages...")
                        for f in future_to_page:
                            f.cancel()
                        future_to_page.clear()
                        return
                    
                    page_data = page_queue.get()
                    page_num, product_idx = page_data
                    
                    # Atomically check again before submitting
                    if not config.can_create_new_threads():
                        page_queue.put(page_data)
                        return
                    
                    # Double-check with lock held to prevent race condition
                    with config.no_new_threads_lock:
                        if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                            page_queue.put(page_data)
                            return
                    
                    future = executor.submit(page_processor.process_single_page, search_url, page_num, thread_id, excel_filename, proxy_string, product_idx)
                    
                    # Atomically check immediately after submit
                    if not config.can_create_new_threads():
                        future.cancel()
                        page_queue.put(page_data)
                        return
                    
                    # Track future for shutdown
                    with config.futures_lock:
                        config.active_futures.append(future)
                    future_to_page[future] = page_num
                
                # Process completed tasks and immediately submit new ones
                while future_to_page and not (config.NO_NEW_THREADS or config.shutdown_flag.is_set()):
                    # Re-check flags on every iteration
                    if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                        # Cancel remaining futures
                        for future in future_to_page:
                            future.cancel()
                        # Shutdown executor immediately
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    # Wait for any task to complete with SHORT timeout to check shutdown frequently (0.3s = check 3 times per second)
                    try:
                        done, not_done = wait(future_to_page.keys(), timeout=0.3, return_when=FIRST_COMPLETED)
                    except KeyboardInterrupt:
                        # Set flags immediately
                        with config.no_new_threads_lock:
                            config.NO_NEW_THREADS = True
                        config.shutdown_flag.set()
                        # Cancel and break
                        for future in future_to_page:
                            future.cancel()
                        executor.shutdown(wait=False, cancel_futures=True)
                        # Re-raise to propagate to outer handler
                        raise
                    
                    # Re-check flags after wait
                    if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                        # Cancel remaining futures
                        for future in future_to_page:
                            future.cancel()
                        # Shutdown executor immediately
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    # Process completed futures
                    for future in done:
                        # Check flags before processing
                        if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                            break
                        
                        page_num = future_to_page.pop(future)
                        
                        # Remove from tracking when done
                        with config.futures_lock:
                            if future in config.active_futures:
                                config.active_futures.remove(future)
                        
                        try:
                            page_seller_data = future.result()
                            if page_seller_data:
                                all_seller_data.extend(page_seller_data)
                                # Save results incrementally to Excel and Google Sheets
                                file_manager.save_results_incremental(excel_filename, page_seller_data, search_url)
                            processed_pages.add(page_num)
                            print(f"[Thread {thread_id}] Page {page_num} completed. Processed: {len(processed_pages)} pages")
                        except Exception as e:
                            print(f"[Thread {thread_id}] Page {page_num} failed: {e}")
                        
                        # Check flags before submitting new work
                        if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                            break
                        
                        # Immediately submit next page from queue if available
                        if not page_queue.empty():
                            # Check flag before getting from queue
                            if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                                break
                            
                            next_page_data = page_queue.get()
                            next_page, next_product_idx = next_page_data
                            
                            # Check again before submitting
                            if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                                page_queue.put(next_page_data)
                                break
                            
                            # Double-check with lock held right before submit
                            with config.no_new_threads_lock:
                                if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                                    page_queue.put(next_page_data)
                                    break
                            
                            new_future = executor.submit(page_processor.process_single_page, search_url, next_page, thread_id, excel_filename, proxy_string, next_product_idx)
                            
                            # Check immediately after submit
                            if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                                new_future.cancel()
                                page_queue.put(next_page_data)
                                break
                            
                            # Track future for shutdown
                            with config.futures_lock:
                                config.active_futures.append(new_future)
                            future_to_page[new_future] = next_page
                    
                    # If shutdown was requested, break from while loop
                    if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                        # Cancel remaining futures
                        for future in future_to_page:
                            future.cancel()
                        # Shutdown executor immediately
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
            finally:
                # Unregister executor and shutdown
                with config.executors_lock:
                    if executor in config.active_executors:
                        config.active_executors.remove(executor)
                executor.shutdown(wait=False, cancel_futures=True)
            
            # All pages processed
            if processed_pages:
                print(f"[Thread {thread_id}] All pages processed. Total processed: {len(processed_pages)} pages")
            
            # Check completion - verify ALL pages are done and last product on last page visited
            # A URL is complete ONLY when:
            # 1. No active pages in progress file for this URL
            # 2. All pages up to total_pages have been processed
            # 3. The last product on the last page has been visited
            try:
                if not processed_pages:
                    print(f"[Thread {thread_id}] No pages were processed successfully")
                else:
                    # Check if there are any active pages still in progress file
                    url_progress = progress.load_progress()
                    active_pages_for_url = url_progress.get(normalized_key, {}).get('pages', {})
                    
                    if active_pages_for_url:
                        # Still have active pages - not complete yet
                        print(f"[Thread {thread_id}] Still have {len(active_pages_for_url)} active page(s) in progress. URL not complete yet.")
                    else:
                        # No active pages - check if we've processed all pages
                        max_processed_page = max(processed_pages) if processed_pages else 0
                        
                        if stored_total_pages:
                            # We know the total pages - verify we've processed up to the last page
                            if max_processed_page >= stored_total_pages:
                                # Check if last page's last product was visited by verifying no next page exists
                                last_page_url = build_page_url(search_url, stored_total_pages)
                                try:
                                    driver.get(last_page_url)
                                    time.sleep(2)
                                    
                                    has_next_page = driver.execute_script(f"return ({js_scripts.HAS_NEXT_PAGE_SCRIPT})();")
                                    
                                    if not has_next_page:
                                        # No next page - all pages and products completed
                                        print(f"[Thread {thread_id}] All {stored_total_pages} pages and all products completed. Marking URL as completed.")
                                        file_manager.mark_url_completed(search_url)
                                        progress.remove_url_from_progress(normalized_key)
                                    else:
                                        # There's a next page - update total_pages
                                        new_total = driver.execute_script(f"return ({js_scripts.GET_TOTAL_PAGES_SCRIPT})();")
                                        if new_total > stored_total_pages:
                                            print(f"[Thread {thread_id}] Found more pages: {new_total}. Updating total_pages.")
                                            progress.update_total_pages(search_url, new_total)
                                        else:
                                            print(f"[Thread {thread_id}] More pages exist but couldn't detect total. Progress saved.")
                                except Exception as e:
                                    print(f"[Thread {thread_id}] Error checking last page: {e}. Progress saved.")
                            else:
                                print(f"[Thread {thread_id}] Processed up to page {max_processed_page}, but total is {stored_total_pages}. More pages to process.")
                        else:
                            # Don't know total pages - check if there's a next page from the last processed page
                            last_page_to_check = max_processed_page if max_processed_page > 0 else start_page
                            if last_page_to_check == 1:
                                check_url = search_url
                            else:
                                check_url = build_page_url(search_url, last_page_to_check)
                            
                            try:
                                driver.get(check_url)
                                time.sleep(2)
                                
                                has_next_page = driver.execute_script(f"return ({js_scripts.HAS_NEXT_PAGE_SCRIPT})();")
                                
                                if not has_next_page:
                                    # No next page - all pages and products completed
                                    print(f"[Thread {thread_id}] All pages and all products completed. Marking URL as completed.")
                                    file_manager.mark_url_completed(search_url)
                                    progress.remove_url_from_progress(normalized_key)
                                else:
                                    # There's a next page - get total and update
                                    new_total = driver.execute_script(f"return ({js_scripts.GET_TOTAL_PAGES_SCRIPT})();")
                                    if new_total:
                                        print(f"[Thread {thread_id}] Found {new_total} total pages. Updating total_pages.")
                                        progress.update_total_pages(search_url, new_total)
                                    else:
                                        print(f"[Thread {thread_id}] More pages exist. Progress saved at page {last_page_to_check}")
                            except Exception as e:
                                print(f"[Thread {thread_id}] Error checking for next page: {e}. Progress saved.")
            except Exception as e:
                print(f"[Thread {thread_id}] Error checking completion: {e}")
            
            print(f"[Thread {thread_id}] Completed URL - Found {len(all_seller_data)} sellers")
            
        except KeyboardInterrupt:
            # Set flags before re-raising
            with config.no_new_threads_lock:
                config.NO_NEW_THREADS = True
            config.shutdown_flag.set()
            raise  # Re-raise to propagate to main handler
        except Exception as e:
            print(f"[Thread {thread_id}] Error in URL processing: {e}")
        finally:
            if config.shutdown_flag.is_set():
                print(f"[Thread {thread_id}] Shutdown requested, closing browser...")
            try:
                if driver:
                    driver.quit()
            except:
                pass
            if not config.shutdown_flag.is_set():
                print(f"[Thread {thread_id}] Browser closed")
    except Exception as e:
        print(f"[Thread {thread_id}] Outer error: {e}")
        try:
            if driver:
                driver.quit()
        except:
            pass

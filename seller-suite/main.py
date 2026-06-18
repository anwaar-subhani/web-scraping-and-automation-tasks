"""Main entry point and orchestration"""
import os
import signal
import time
import queue
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from scraper import config
from scraper import utils
from scraper import progress
from scraper import file_manager
from scraper import url_processor

def signal_handler(signum, frame):
    """Handle Ctrl+C - Immediately stop everything"""
    print("\n🛑 Ctrl+C detected - Shutting down...")
    
    # Set global flag to prevent new thread creation
    with config.no_new_threads_lock:
        config.NO_NEW_THREADS = True
    
    # Set shutdown flag
    config.shutdown_flag.set()
    
    # Cancel all tracked futures
    with config.futures_lock:
        for future in config.active_futures[:]:
            try:
                if not future.done():
                    future.cancel()
            except:
                pass
        config.active_futures.clear()
    
    # Shutdown all active executors
    with config.executors_lock:
        for executor in config.active_executors[:]:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except:
                pass
    
    # Give threads a moment to close browsers
    time.sleep(3)
    
    # Force exit
    os._exit(1)

def main():
    # Register signal handler for Ctrl+C (works on Windows with Python 3.8+)
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except:
        pass
    
    print("Starting Parallel Amazon URL Scraper...")
    print(f"Max threads: {config.MAX_THREADS}")
    print(f"Concurrent pages per link: {config.CONCURRENT_PAGES}")
    print("Press Ctrl+C to stop gracefully...")
    
    # Clean up old cache files
    utils.clean_old_cache()
    
    # Read URLs from Google Sheet
    all_urls = utils.read_urls_from_google_sheet()
    
    if not all_urls:
        print("[ERROR] No URLs found in Google Sheet")
        return
    
    # Load completed URLs and filter them out
    completed_urls = file_manager.load_completed_urls()
    pending_urls = [url for url in all_urls if url not in completed_urls]
    
    if not pending_urls:
        print("[INFO] All URLs have been completed!")
        return
    
    print(f"[INFO] Total URLs: {len(all_urls)}, Completed: {len(completed_urls)}, Pending: {len(pending_urls)}")
    
    # Initialize all pending URLs in url_progress.csv (if they don't exist, add them with page 1)
    progress.initialize_urls_in_progress(pending_urls)
    
    # Create a queue of all pending URLs
    url_queue = queue.Queue()
    for url in pending_urls:
        url_queue.put(url)
    
    start_time = time.time()
    thread_counter = [0]  # Use list to allow modification in nested scope
    
    # Track all URLs we've already seen/queued so we can add new ones dynamically
    seen_urls = set(all_urls)
    
    executor = None
    try:
        # Use ThreadPoolExecutor for parallel processing
        executor = ThreadPoolExecutor(max_workers=config.MAX_THREADS)
        # Register executor for shutdown
        with config.executors_lock:
            config.active_executors.append(executor)
        
        # Submit initial batch of URLs (up to MAX_THREADS)
        future_to_url = {}
        should_submit = config.can_create_new_threads()
        
        if should_submit:
            initial_count = min(config.MAX_THREADS, url_queue.qsize())
            for i in range(initial_count):
                # Atomically check before each submission
                if not config.can_create_new_threads():
                    break
                
                if url_queue.empty():
                    break
                
                # Double-check with lock held right before submit
                with config.no_new_threads_lock:
                    if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                        break
                
                url = url_queue.get()
                thread_counter[0] += 1
                thread_id = thread_counter[0]
                
                future = executor.submit(url_processor.process_single_url, url, thread_id)
                
                # Atomically check again immediately after submit
                if not config.can_create_new_threads():
                    future.cancel()
                    url_queue.put(url)  # Put it back
                    thread_counter[0] -= 1
                    break
                
                # Track future for shutdown
                with config.futures_lock:
                    config.active_futures.append(future)
                future_to_url[future] = url
                print(f"[INFO] Started processing URL {thread_id}/{len(pending_urls)}: {url[:80]}...")
        
        # Process completed tasks and continuously submit new ones from queue
        try:
            while future_to_url or not url_queue.empty():
                # Check flags first
                if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                    for f in future_to_url:
                        f.cancel()
                    break
                
                # Wait for any future to complete with short timeout (0.5s) to allow KeyboardInterrupt
                try:
                    if future_to_url:
                        done, not_done = wait(future_to_url.keys(), timeout=0.5, return_when=FIRST_COMPLETED)
                    else:
                        # No active futures but queue not empty - wait a bit and check again
                        time.sleep(0.1)
                        continue
                except KeyboardInterrupt:
                    with config.no_new_threads_lock:
                        config.NO_NEW_THREADS = True
                    config.shutdown_flag.set()
                    # Cancel all futures
                    for f in future_to_url:
                        f.cancel()
                    break
                
                # Process completed futures
                for future in done:
                    # Check flags again
                    if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                        for f in future_to_url:
                            f.cancel()
                        break
                    
                    url = future_to_url.pop(future, None)
                    if url is None:
                        continue
                    
                    # Remove from tracking when done
                    with config.futures_lock:
                        if future in config.active_futures:
                            config.active_futures.remove(future)
                    
                    try:
                        future.result()
                        if not (config.NO_NEW_THREADS or config.shutdown_flag.is_set()):
                            remaining = url_queue.qsize() + len(future_to_url)
                            print(f"[SUCCESS] Completed URL: {url[:80]}... ({remaining} remaining)")
                    except KeyboardInterrupt:
                        # Re-raise KeyboardInterrupt so it's caught by outer handler
                        raise
                    except Exception as e:
                        if not (config.NO_NEW_THREADS or config.shutdown_flag.is_set()):
                            remaining = url_queue.qsize() + len(future_to_url)
                            print(f"[ERROR] Failed URL {url[:80]}...: {e} ({remaining} remaining)")
                    
                    # After each URL finishes (success or error), immediately check for new URLs in the sheet
                    if not (config.NO_NEW_THREADS or config.shutdown_flag.is_set()):
                        try:
                            latest_urls = utils.read_urls_from_google_sheet()
                            if latest_urls:
                                # Only keep URLs that are truly new for this run
                                new_urls = [u for u in latest_urls if u not in seen_urls]
                                if new_urls:
                                    print(f"[INFO] Detected {len(new_urls)} new URL(s) in Google Sheet, adding to queue...")
                                    # Initialize progress entries for these new URLs
                                    progress.initialize_urls_in_progress(new_urls)
                                    # Add new URLs to queue and tracking
                                    for new_url in new_urls:
                                        url_queue.put(new_url)
                                        seen_urls.add(new_url)
                                        pending_urls.append(new_url)
                        except Exception as e:
                            print(f"[WARN] Failed to refresh URLs from Google Sheet: {e}")
                    
                    # Immediately submit next URL from queue if available
                    if not url_queue.empty() and not (config.NO_NEW_THREADS or config.shutdown_flag.is_set()):
                        # Check flag before getting from queue
                        if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                            break
                        
                        next_url = url_queue.get()
                        thread_counter[0] += 1
                        next_thread_id = thread_counter[0]
                        
                        # Check again before submitting
                        if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                            url_queue.put(next_url)  # Put it back
                            thread_counter[0] -= 1
                            break
                        
                        # Double-check with lock held right before submit
                        with config.no_new_threads_lock:
                            if config.NO_NEW_THREADS or config.shutdown_flag.is_set():
                                url_queue.put(next_url)  # Put it back
                                thread_counter[0] -= 1
                                break
                        
                        new_future = executor.submit(url_processor.process_single_url, next_url, next_thread_id)
                        
                        # Check immediately after submit
                        if not config.can_create_new_threads():
                            new_future.cancel()
                            url_queue.put(next_url)  # Put it back
                            thread_counter[0] -= 1
                            break
                        
                        # Track future for shutdown
                        with config.futures_lock:
                            config.active_futures.append(new_future)
                        future_to_url[new_future] = next_url
                        remaining = url_queue.qsize() + len(future_to_url)
                        print(f"[INFO] Started processing URL {next_thread_id}/{len(pending_urls)}: {next_url[:80]}... ({remaining} remaining)")
        except KeyboardInterrupt:
            print("\n🛑 Ctrl+C detected - Shutting down...")
            # Set global flag to prevent new threads
            with config.no_new_threads_lock:
                config.NO_NEW_THREADS = True
            config.shutdown_flag.set()
            
            # Cancel all tracked futures
            with config.futures_lock:
                for f in config.active_futures[:]:
                    try:
                        if not f.done():
                            f.cancel()
                    except:
                        pass
                config.active_futures.clear()
            
            # Cancel URL futures
            for f in future_to_url:
                f.cancel()
            
            # Shutdown all active executors
            with config.executors_lock:
                for exec in config.active_executors[:]:
                    try:
                        exec.shutdown(wait=False, cancel_futures=True)
                    except:
                        pass
            
            # Shutdown main executor
            if executor:
                executor.shutdown(wait=False, cancel_futures=True)
            
            # Give threads a moment to close browsers
            time.sleep(3)
            
            # Force exit
            os._exit(1)
    except Exception as e:
        print(f"✗ Error in main execution: {e}")
    finally:
        # Wait for all threads to finish (they check shutdown_flag)
        
        # Unregister executor and shutdown
        if executor:
            with config.executors_lock:
                if executor in config.active_executors:
                    config.active_executors.remove(executor)
            # Shutdown executor and wait for threads to finish
            executor.shutdown(wait=True)
        
        if config.shutdown_flag.is_set():
            print("✓ All threads stopped.")
        else:
            print(f"\n✓ All URLs processing completed!")
            end_time = time.time()
            print(f"✓ Total execution time: {end_time - start_time:.2f} seconds")
    
    if not config.shutdown_flag.is_set():
        input("Press Enter to close...")

if __name__ == "__main__":
    main()


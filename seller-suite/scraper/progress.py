"""Progress tracking and management"""
import os
import csv
from . import config
from .utils import normalize_url, extract_page_number_from_url, build_page_url

def load_progress():
    """Load progress tracking - New format: url,page_number,product_index,total_pages
    Returns: dict[normalized_url] = {
        'base_url': str,
        'total_pages': int or None,
        'pages': dict[page_num] = product_index  # page_num -> last processed product index
    }
    """
    progress = {}
    if os.path.exists(config.PROGRESS_FILE):
        try:
            with open(config.PROGRESS_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('url', '').strip()
                    if not url:
                        continue
                    
                    normalized_key = normalize_url(url)
                    
                    # Check if this is new format (has page_number and product_index columns)
                    page_num_str = row.get('page_number', '').strip()
                    product_idx_str = row.get('product_index', '').strip()
                    
                    if page_num_str and product_idx_str:
                        # New format: url,page_number,product_index,total_pages
                        try:
                            page_num = int(page_num_str)
                            product_idx = int(product_idx_str)
                        except ValueError:
                            continue
                        
                        if normalized_key not in progress:
                            progress[normalized_key] = {
                                'base_url': url,
                                'total_pages': None,
                                'pages': {}
                            }
                        
                        # Store page progress
                        progress[normalized_key]['pages'][page_num] = product_idx
                        
                        # Store total_pages if available
                        total_pages_str = row.get('total_pages', '').strip()
                        if total_pages_str and total_pages_str.isdigit():
                            progress[normalized_key]['total_pages'] = int(total_pages_str)
                    else:
                        # Old format: url,total_pages (with page in URL)
                        # Try to extract page from URL for backward compatibility
                        page = extract_page_number_from_url(url)
                        total_pages = row.get('total_pages', '').strip()
                        
                        if normalized_key not in progress:
                            progress[normalized_key] = {
                                'base_url': url,
                                'total_pages': int(total_pages) if total_pages and total_pages.isdigit() else None,
                                'pages': {}
                            }
                        
                        # Convert old format: assume page was completed, start from next page
                        # But we don't know product_index, so start from 0
                        if page > 0:
                            progress[normalized_key]['pages'][page] = 0
            print(f"Loaded progress for {len(progress)} URLs")
        except Exception as e:
            print(f"Warning: Could not load progress file: {e}")
    return progress

def initialize_urls_in_progress(urls):
    """Initialize URLs in url_progress.csv (new format: url,page_number,product_index,total_pages)
    Only adds new URLs, doesn't modify existing ones. Limits to CONCURRENT_PAGES per URL.
    """
    with config.progress_lock:
        # Read existing rows
        existing_rows = []
        existing_urls = set()
        
        if os.path.exists(config.PROGRESS_FILE):
            try:
                with open(config.PROGRESS_FILE, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('url', '').strip()
                        if url:
                            existing_rows.append(row)
                            existing_urls.add(normalize_url(url))
            except Exception as e:
                print(f"Warning: Could not read progress file: {e}")
        
        # Add new URLs (only page 1, product_index 0)
        new_urls_count = 0
        for url in urls:
            normalized_key = normalize_url(url)
            if normalized_key not in existing_urls:
                # Add initial row for this URL (page 1, product 0)
                existing_rows.append({
                    'url': url,
                    'page_number': '1',
                    'product_index': '0',
                    'total_pages': ''
                })
                new_urls_count += 1
        
        # Write back if we added new URLs
        if new_urls_count > 0:
            try:
                temp_file = config.PROGRESS_FILE + '.tmp'
                with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['url', 'page_number', 'product_index', 'total_pages']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(existing_rows)
                
                if os.path.exists(config.PROGRESS_FILE):
                    os.replace(temp_file, config.PROGRESS_FILE)
                else:
                    os.rename(temp_file, config.PROGRESS_FILE)
                print(f"Initialized {new_urls_count} new URL(s) in progress file")
            except Exception as e:
                print(f"Warning: Could not initialize progress file: {e}")

def update_page_progress(base_url, page_num, product_index, total_pages=None):
    """Update progress for a specific page and product index (thread-safe)
    Only updates THIS thread's page row, doesn't touch other pages.
    
    Note: Maximum records in CSV = MAX_THREADS * CONCURRENT_PAGES
    (Each URL can have up to CONCURRENT_PAGES active pages)
    
    Args:
        base_url: Base URL (normalized)
        page_num: Page number being processed
        product_index: Last processed product index (0-based) on this page
        total_pages: Total pages (optional, will preserve existing if None)
    """
    normalized_key = normalize_url(base_url)
    
    with config.progress_lock:
        # Read existing CSV rows
        rows = []
        url_total_pages = None
        url_pages = {}  # page_num -> product_index for this URL
        
        if os.path.exists(config.PROGRESS_FILE):
            try:
                with open(config.PROGRESS_FILE, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('url', '').strip()
                        if not url:
                            continue
                        
                        row_normalized = normalize_url(url)
                        
                        if row_normalized == normalized_key:
                            # This is our URL - collect its pages
                            p_num_str = row.get('page_number', '').strip()
                            p_idx_str = row.get('product_index', '').strip()
                            total_str = row.get('total_pages', '').strip()
                            
                            if p_num_str and p_idx_str:
                                try:
                                    p_num = int(p_num_str)
                                    p_idx = int(p_idx_str)
                                    url_pages[p_num] = p_idx
                                    
                                    # Update total_pages if available
                                    if total_str and total_str.isdigit():
                                        url_total_pages = int(total_str)
                                except ValueError:
                                    pass
                        else:
                            # Different URL - keep as is
                            rows.append(row)
            except Exception as e:
                print(f"[PROGRESS] Warning: Could not read progress file: {e}")
        
        # Update THIS page's progress
        url_pages[page_num] = product_index
        
        # Preserve total_pages
        if total_pages is not None:
            url_total_pages = total_pages
        elif url_total_pages is None:
            url_total_pages = total_pages
        
        # Limit to CONCURRENT_PAGES per URL - keep only the most recent pages
        if len(url_pages) > config.CONCURRENT_PAGES:
            # Keep only the CONCURRENT_PAGES most recent pages (highest page numbers)
            sorted_pages = sorted(url_pages.keys(), reverse=True)
            pages_to_keep = sorted_pages[:config.CONCURRENT_PAGES]
            url_pages = {p: url_pages[p] for p in pages_to_keep}
            print(f"[PROGRESS] Limited to {config.CONCURRENT_PAGES} active pages for URL")
        
        # Add/update rows for this URL
        base_url_for_file = base_url  # Use the provided base_url
        for p_num, p_idx in url_pages.items():
            rows.append({
                'url': base_url_for_file,
                'page_number': str(p_num),
                'product_index': str(p_idx),
                'total_pages': str(url_total_pages) if url_total_pages else ''
            })
        
        # Write back atomically
        try:
            temp_file = config.PROGRESS_FILE + '.tmp'
            with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['url', 'page_number', 'product_index', 'total_pages']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            # Atomic replace
            if os.path.exists(config.PROGRESS_FILE):
                os.replace(temp_file, config.PROGRESS_FILE)
            else:
                os.rename(temp_file, config.PROGRESS_FILE)
            
            print(f"[PROGRESS] Updated: page {page_num}, product {product_index}")
        except Exception as e:
            print(f"[PROGRESS ERROR] Could not save progress: {e}")
            import traceback
            traceback.print_exc()
            if os.path.exists(config.PROGRESS_FILE + '.tmp'):
                try:
                    os.remove(config.PROGRESS_FILE + '.tmp')
                except:
                    pass

def update_total_pages(base_url, total_pages):
    """Update total_pages for all pages of a URL - only updates total_pages field"""
    normalized_key = normalize_url(base_url)
    
    with config.progress_lock:
        # Read existing CSV rows and update total_pages for this URL only
        rows = []
        
        if os.path.exists(config.PROGRESS_FILE):
            try:
                with open(config.PROGRESS_FILE, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('url', '').strip()
                        if not url:
                            continue
                        
                        row_normalized = normalize_url(url)
                        
                        # Update total_pages for this URL's rows
                        if row_normalized == normalized_key:
                            row['total_pages'] = str(total_pages) if total_pages else ''
                        
                        rows.append(row)
            except Exception as e:
                print(f"[PROGRESS] Warning: Could not read progress file: {e}")
        
        # Write back with updated total_pages
        try:
            temp_file = config.PROGRESS_FILE + '.tmp'
            with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['url', 'page_number', 'product_index', 'total_pages']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            if os.path.exists(config.PROGRESS_FILE):
                os.replace(temp_file, config.PROGRESS_FILE)
            else:
                os.rename(temp_file, config.PROGRESS_FILE)
        except Exception as e:
            print(f"Warning: Could not update total_pages: {e}")

def remove_page_from_progress(base_url, page_num):
    """Remove a completed page from progress tracking - only removes THIS page's row"""
    normalized_key = normalize_url(base_url)
    
    with config.progress_lock:
        # Read existing CSV rows
        rows = []
        
        if os.path.exists(config.PROGRESS_FILE):
            try:
                with open(config.PROGRESS_FILE, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        url = row.get('url', '').strip()
                        if not url:
                            continue
                        
                        row_normalized = normalize_url(url)
                        p_num_str = row.get('page_number', '').strip()
                        
                        # Skip this specific page for this URL
                        if row_normalized == normalized_key and p_num_str and p_num_str.isdigit():
                            if int(p_num_str) == page_num:
                                # Skip this row (remove it)
                                continue
                        
                        # Keep all other rows
                        rows.append(row)
            except Exception as e:
                print(f"[PROGRESS] Warning: Could not read progress file: {e}")
        
        # Write back without the removed page
        try:
            temp_file = config.PROGRESS_FILE + '.tmp'
            with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['url', 'page_number', 'product_index', 'total_pages']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            if os.path.exists(config.PROGRESS_FILE):
                os.replace(temp_file, config.PROGRESS_FILE)
            else:
                os.rename(temp_file, config.PROGRESS_FILE)
            
            print(f"[PROGRESS] Removed page {page_num} from progress")
        except Exception as e:
            print(f"Warning: Could not update progress file: {e}")

def remove_url_from_progress(normalized_key):
    """Remove a URL from progress file (when URL is fully completed)"""
    with config.progress_lock:
        progress = load_progress()
        
        if normalized_key in progress:
            del progress[normalized_key]
        
        # Write back
        try:
            temp_file = config.PROGRESS_FILE + '.tmp'
            with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['url', 'page_number', 'product_index', 'total_pages']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for norm_key, data in progress.items():
                    base = data['base_url']
                    total = data.get('total_pages')
                    pages = data.get('pages', {})
                    
                    # Write one row per active page
                    for p_num, p_idx in pages.items():
                        row = {
                            'url': base,
                            'page_number': p_num,
                            'product_index': p_idx,
                            'total_pages': total if total else ''
                        }
                        writer.writerow(row)
            
            if os.path.exists(config.PROGRESS_FILE):
                os.replace(temp_file, config.PROGRESS_FILE)
            else:
                os.rename(temp_file, config.PROGRESS_FILE)
        except Exception as e:
            print(f"Warning: Could not update progress file: {e}")


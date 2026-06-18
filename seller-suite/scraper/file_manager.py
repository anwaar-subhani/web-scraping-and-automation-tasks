"""File operations for Excel, CSV, and completed URLs"""
import os
import csv
import pandas as pd
import time
from datetime import datetime
from . import config
from . import google_sheets_manager

def load_completed_urls():
    """Load list of completed URLs"""
    completed = set()
    if os.path.exists(config.COMPLETED_URLS_FILE):
        try:
            with open(config.COMPLETED_URLS_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get('url', '').strip()
                    if url:
                        completed.add(url)
            print(f"Loaded {len(completed)} completed URLs")
        except Exception as e:
            print(f"Warning: Could not load completed URLs file: {e}")
    return completed

def mark_url_completed(url):
    """Mark a URL as completed"""
    with config.completed_lock:
        completed = load_completed_urls()
        completed.add(url)
        
        # Write all completed URLs to file
        with open(config.COMPLETED_URLS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'completed_at'])
            writer.writeheader()
            for u in completed:
                writer.writerow({'url': u, 'completed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

def save_results_incremental(excel_filename, seller_data_list, search_url=None):
    """Save results incrementally to Excel file and Google Sheet (append to existing if exists)"""
    if not seller_data_list:
        return
    
    # Save to Google Sheets if URL provided
    if search_url:
        google_sheets_manager.append_to_google_sheet(search_url, seller_data_list)
    
    # Skip Excel if disabled in config
    if not config.SAVE_TO_EXCEL:
        return
    
    # Retry logic for file locking (in case Excel is open)
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Check if file exists
            file_exists = os.path.exists(excel_filename)
            
            if file_exists:
                # Read existing data
                try:
                    existing_df = pd.read_excel(excel_filename, sheet_name='Sellers')
                    # Combine with new data
                    new_df = pd.DataFrame(seller_data_list)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    # Remove duplicates based on Business Name and Email
                    combined_df = combined_df.drop_duplicates(subset=['Business Name', 'Email'], keep='last')
                    df = combined_df
                except PermissionError:
                    if attempt < max_retries - 1:
                        print(f"Warning: Excel file is locked (probably open in Excel). Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"Warning: Could not read existing file after {max_retries} attempts. File may be locked by Excel. Skipping this save.")
                        return
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"Warning: Could not read existing file: {e}. Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"Warning: Could not read existing file after {max_retries} attempts: {e}. Creating new file.")
                        df = pd.DataFrame(seller_data_list)
            else:
                # Create new dataframe
                df = pd.DataFrame(seller_data_list)
            
            # Save to Excel
            try:
                with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sellers')
                    worksheet = writer.sheets['Sellers']
                    worksheet.column_dimensions['A'].width = 50  # Business Name
                    worksheet.column_dimensions['B'].width = 20  # Phone Number
                    worksheet.column_dimensions['C'].width = 35  # Email
                    worksheet.column_dimensions['D'].width = 10  # Country
                    worksheet.column_dimensions['E'].width = 30  # Seller Name
                    worksheet.column_dimensions['F'].width = 60  # Seller URL
                    worksheet.column_dimensions['G'].width = 20  # Extracted At
                # Success - break out of retry loop
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    print(f"Warning: Excel file is locked (probably open in Excel). Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Warning: Could not save to Excel file after {max_retries} attempts. File may be locked by Excel. Data will be saved on next attempt.")
                    return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Warning: Could not save results: {e}. Retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            else:
                print(f"Warning: Could not save results after {max_retries} attempts: {e}")
                return


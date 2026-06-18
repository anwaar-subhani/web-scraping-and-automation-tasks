"""Google Sheets operations for writing seller data"""
import gspread
from google.oauth2.service_account import Credentials
import os
from . import config
from .utils import normalize_url, extract_filename_from_url

# Google Sheets client (initialized once)
_gs_client = None
_gs_spreadsheet = None

def initialize_google_sheets():
    """Initialize Google Sheets client"""
    global _gs_client, _gs_spreadsheet
    
    if _gs_client is not None:
        return _gs_client, _gs_spreadsheet
    
    # Check if credentials file exists
    credentials_path = config.GOOGLE_CREDENTIALS_PATH
    if not credentials_path or not os.path.exists(credentials_path):
        print("[INFO] Google Sheets writing disabled - credentials file not found.")
        print("[INFO] Script will continue - only Excel files will be saved (if enabled).")
        return None, None
    
    try:
        # Authenticate with service account
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(credentials_path, scopes=scope)
        _gs_client = gspread.authorize(creds)
        
        # Open the spreadsheet
        sheet_id = config.GOOGLE_SHEET_URL.split('/d/')[1].split('/')[0]
        _gs_spreadsheet = _gs_client.open_by_key(sheet_id)
        
        print("[INFO] Google Sheets initialized successfully")
        return _gs_client, _gs_spreadsheet
    except Exception as e:
        print(f"[WARNING] Failed to initialize Google Sheets: {e}")
        return None, None

def get_or_create_sheet_tab(spreadsheet, url):
    """Get or create a sheet tab for a specific URL"""
    if spreadsheet is None:
        return None
    
    try:
        # Generate a clean sheet name from URL
        sheet_name = generate_sheet_name(url)
        
        # Try to get existing sheet
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"[GOOGLE SHEETS] Using existing tab: {sheet_name}")
            # Set column widths for existing sheet (in case they weren't set before)
            _set_column_widths(spreadsheet, worksheet)
        except gspread.exceptions.WorksheetNotFound:
            # Create new sheet
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
            # Add headers
            headers = ['Business Name', 'Phone Number', 'Email', 'Country', 'Seller Name', 'Seller URL', 'Extracted At']
            worksheet.append_row(headers)
            # Set column widths for new sheet
            _set_column_widths(spreadsheet, worksheet)
            print(f"[GOOGLE SHEETS] Created new tab: {sheet_name}")
        
        return worksheet
    except Exception as e:
        print(f"[WARNING] Failed to get/create sheet tab: {e}")
        return None

def _set_column_widths(spreadsheet, worksheet):
    """Set column widths for Google Sheet (matching Excel widths)"""
    # Column widths in pixels (approximate conversion from Excel)
    # Excel: A=50, B=20, C=35, D=10, E=30, F=60, G=20
    column_widths = [
        {'startColumnIndex': 0, 'endColumnIndex': 1, 'pixelSize': 300},  # Business Name (A)
        {'startColumnIndex': 1, 'endColumnIndex': 2, 'pixelSize': 150},  # Phone Number (B)
        {'startColumnIndex': 2, 'endColumnIndex': 3, 'pixelSize': 250},  # Email (C)
        {'startColumnIndex': 3, 'endColumnIndex': 4, 'pixelSize': 100},  # Country (D)
        {'startColumnIndex': 4, 'endColumnIndex': 5, 'pixelSize': 200},  # Seller Name (E)
        {'startColumnIndex': 5, 'endColumnIndex': 6, 'pixelSize': 400},  # Seller URL (F)
        {'startColumnIndex': 6, 'endColumnIndex': 7, 'pixelSize': 150}   # Extracted At (G)
    ]
    try:
        spreadsheet.batch_update({
            'requests': [{
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': worksheet.id,
                        'dimension': 'COLUMNS',
                        'startIndex': width['startColumnIndex'],
                        'endIndex': width['endColumnIndex']
                    },
                    'properties': {
                        'pixelSize': width['pixelSize']
                    },
                    'fields': 'pixelSize'
                }
            } for width in column_widths]
        })
    except Exception as e:
        # Silently fail - column widths are nice to have but not critical
        pass

def generate_sheet_name(url):
    """Generate a clean sheet name from URL (max 100 chars, Google Sheets limit)"""
    try:
        # Use similar logic as filename extraction
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Extract market
        domain = parsed.netloc.replace('www.', '')
        if 'amazon.co.uk' in domain:
            market = 'uk'
        elif 'amazon.' in domain:
            market = domain.split('amazon.')[-1].split('.')[0]
            if market == 'co':
                market = 'uk'
        else:
            market = 'unknown'
        
        # Get category or keyword
        category = None
        if 'i' in params and params['i']:
            category = params['i'][0]
        elif 'k' in params and params['k']:
            category = params['k'][0]
        
        if category:
            clean_name = category.replace(' ', '_').replace('+', '_')[:50]
            sheet_name = f"{clean_name}_{market}"
        else:
            url_hash = abs(hash(url)) % 10000
            sheet_name = f"sellers_{market}_{url_hash}"
        
        # Google Sheets sheet name limit is 100 characters
        if len(sheet_name) > 100:
            sheet_name = sheet_name[:100]
        
        return sheet_name
    except Exception as e:
        # Fallback to hash-based name
        url_hash = abs(hash(url)) % 100000
        return f"sellers_{url_hash}"

def append_to_google_sheet(url, seller_data_list):
    """Append seller data to Google Sheet tab for the URL (with duplicate checking)"""
    if not seller_data_list:
        return
    
    client, spreadsheet = initialize_google_sheets()
    if spreadsheet is None:
        return
    
    try:
        worksheet = get_or_create_sheet_tab(spreadsheet, url)
        if worksheet is None:
            return
        
        # Get existing data to check for duplicates
        existing_data = []
        try:
            existing_records = worksheet.get_all_records()
            for record in existing_records:
                existing_data.append({
                    'Business Name': str(record.get('Business Name', '')),
                    'Email': str(record.get('Email', ''))
                })
        except Exception as e:
            # If no existing data or error reading, start fresh
            existing_data = []
        
        # Prepare data rows (only non-duplicates)
        rows_to_add = []
        duplicates_count = 0
        for seller in seller_data_list:
            business_name = str(seller.get('Business Name', ''))
            email = str(seller.get('Email', ''))
            
            # Check if this seller already exists
            is_duplicate = False
            for existing in existing_data:
                if (existing['Business Name'] == business_name and 
                    existing['Email'] == email):
                    is_duplicate = True
                    duplicates_count += 1
                    break
            
            # Also check against new rows we're about to add
            if not is_duplicate:
                for new_row in rows_to_add:
                    if (new_row[0] == business_name and new_row[2] == email):
                        is_duplicate = True
                        duplicates_count += 1
                        break
            
            # Only add if not duplicate
            if not is_duplicate:
                row = [
                    business_name,
                    seller.get('Phone Number', ''),
                    email,
                    seller.get('Country', ''),
                    seller.get('Seller Name', ''),
                    seller.get('Seller URL', ''),
                    seller.get('Extracted At', '')
                ]
                rows_to_add.append(row)
                # Add to existing_data to check future duplicates in same batch
                existing_data.append({'Business Name': business_name, 'Email': email})
        
        # Append only non-duplicate rows
        if rows_to_add:
            worksheet.append_rows(rows_to_add)
            print(f"[GOOGLE SHEETS] Added {len(rows_to_add)} seller(s) to sheet tab")
            if duplicates_count > 0:
                print(f"[GOOGLE SHEETS] Skipped {duplicates_count} duplicate(s)")
        elif duplicates_count > 0:
            print(f"[GOOGLE SHEETS] All {duplicates_count} seller(s) were duplicates - nothing added")
    
    except Exception as e:
        print(f"[WARNING] Failed to append to Google Sheet: {e}")


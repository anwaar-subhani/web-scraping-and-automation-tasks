# KFB Web Scraper Setup

## Install Required Libraries
```bash
# Install Python & ChromeDriver
brew install python3 chromedriver

# Install Python packages
pip3 install selenium pandas openpyxl

# Download Chrome browser
# https://www.google.com/chrome/
```

## Setup
1. **Edit credentials** in `script/config.py`:
   ```python
   DEFAULT_USERNAME = "your_username@domain.com"
   DEFAULT_PASSWORD = "your_password"
   ```

2. **Configure property filters**:
   ```python
   KFB_STAGE_INSTALLED = True   # Only extract properties with "KFB Stage = Installed"
   PENDING_SIGNATURE = True     # Only extract properties with "3P Communication Stage = Contract Sent - Pending Signature"
   ```
   - Set both to `True` = Extract properties with BOTH criteria
   - Set one to `True` = Extract properties with that criteria only
   - Set both to `False` = Extract ALL properties (no filtering)
   - **Note**: You can change these settings anytime - changes apply immediately without restart

3. **Add zip codes** to `input/input_zipcodes.txt` (one per line)

## Run Script
```bash
cd script
python3 script.py
```

## What You Can Do
- **Add zip codes anytime** - Script will process them automatically
- **Run for any duration** - Hours, days, or until all zip codes processed
- **Stop anytime** - Press Ctrl+C to stop
- **Check progress** - View `output/processed_zipcodes.txt`

## Output Files
- **Excel data**: `output/output_YYYY-MM-DD_HHMM.xlsx`
- **Progress log**: `output/processed_zipcodes.txt`



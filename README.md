# Web Scraping & Automation Tasks

A collection of Python web scraping, browser automation, and data extraction projects for Amazon and KFB workflows.

## Projects

### 1. [hiring-token](./hiring-token)
Automates the Amazon Hiring login flow, pulls OTPs from YOPmail, and captures authorization tokens for later use.

**Tech**: Playwright, YOPmail  
**Output**: Token files  
**Main script**: `script/script_sync.py`

---

### 2. [keyword-export](./keyword-export)
Runs multiple Amazon keyword searches in parallel and exports seller details from the results.

**Tech**: Playwright, concurrent threading  
**Output**: Excel spreadsheets  
**Main script**: `script_parallel.py`

---

### 3. [seller-exe](./seller-exe)
Scrapes third-party Amazon seller details for a single keyword and market.

**Tech**: Playwright  
**Output**: Excel spreadsheet  
**Main script**: `script.py`

---

### 4. [seller-suite](./seller-suite)
Modular Amazon seller scraping suite with reusable components, Google Sheets support, and progress tracking.

**Tech**: Playwright, Google Sheets API, concurrent threading  
**Output**: Excel spreadsheets with incremental saving  
**Main script**: `main.py`  
**Modules**: Browser manager, URL processor, progress tracker, file manager

---

### 5. [kfb-zip](./kfb-zip)
Automates KFB portal scraping by ZIP code, extracts property data, and writes results to Excel.

**Tech**: Selenium, environment-based credentials  
**Output**: Excel exports  
**Main script**: `script/script.py`

---

### 6. [kfb-zip-alt](./kfb-zip-alt)
Alternate version of the KFB ZIP scraping workflow for testing and experimentation.

**Tech**: Selenium, environment-based credentials  
**Output**: Excel exports  
**Main script**: `script/script.py`

---

## License

Use these projects at your own discretion. Ensure compliance with website terms of service before scraping.

---

**Last updated**: June 2026

# KFB Property ZIP Scraper

This project automates KFB portal scraping by ZIP code, extracts property data, and writes the results to Excel.

## What I did

- Read ZIP codes from the input list.
- Automated portal navigation and property lookup.
- Extracted field values from property records.
- Wrote the processed data to local output files.

## Main entry point

- `script/script.py`

## Local setup

- Store runtime values in a local `.env` file.
- Required variables: `KFB_LOGIN_URL`, `KFB_DEFAULT_USERNAME`, `KFB_DEFAULT_PASSWORD`.

## GitHub notes

- Generated outputs and local secrets stay out of Git.

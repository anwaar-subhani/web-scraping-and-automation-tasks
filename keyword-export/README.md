# Amazon Keyword Seller Export

This project runs multiple Amazon keyword searches in parallel and exports seller details from the results.

## What I did

- Loaded the keyword list and run settings from `config.json`.
- Started concurrent browser sessions for scraping.
- Extracted seller details from product and seller pages.
- Exported the collected data to spreadsheet output.

## Main entry point

- `script_parallel.py` — parallel scraper runner.

## GitHub notes

- Generated Excel files and progress files are excluded from Git.

# Hiring Token Automation

This project automates the Amazon Hiring login flow, pulls OTPs from YOPmail, and captures authorization tokens for later use.

## What I did

- Read account data from the input files.
- Automated the login and OTP verification flow.
- Captured auth tokens from browser requests/storage.
- Saved the collected output into the local `output/` folder.

## Main entry point

- `script/script_sync.py` — synchronous runner for multiple accounts.

## GitHub notes

- Token, cookie, and OTP files stay out of Git.
- Real account data should never be committed.

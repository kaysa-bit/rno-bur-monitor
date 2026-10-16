# RNO → BUR Southwest delay monitor

This repo checks Southwest flights from Reno/Tahoe International Airport (RNO) to Hollywood Burbank Airport (BUR) and opens a GitHub issue when a flight is delayed by 15+ minutes.

What it does
- Uses the free AviationStack API to fetch flights for a target date.
- Filters to Southwest flights (carrier code WN).
- Compares the scheduled departure to the estimated or actual departure.
- Creates a GitHub issue when a delay is detected.
- Runs every 30 minutes on a schedule and can also be triggered manually.

Setup
1. Create a free AviationStack account and get an API key.
2. In GitHub, go to the repo -> Settings -> Secrets and variables -> Actions.
3. Create a secret named `AVIATIONSTACK_KEY` with your API key.
4. Watch the repo to receive GitHub email notifications whenever a new issue is created.

How to run
- Manual run from the GitHub Actions tab:
  - Open Actions -> Monitor RNO→BUR Southwest Delays -> Run workflow
  - Enter a date in `YYYY-MM-DD` format, or leave blank to check tomorrow.
- Scheduled run:
  - The workflow runs every 30 minutes and defaults to tomorrow.

Notes
- The workflow uses `workflow_dispatch` so you can change the date often without editing files.
- If you want a different delay threshold, change `THRESHOLD_MINUTES` in the workflow.
- If you want to monitor a specific date permanently, set `target_date` in the run menu or edit the workflow default before a run.

#!/usr/bin/env python3
"""
Check Southwest (WN) flights RNO -> BUR for a target date using AviationStack,
create GitHub issues when a delay >= THRESHOLD is detected.

Behavior change: the script fetches the scheduled departures for the target date and
computes the latest scheduled departure. If the current time is later than (latest - 2 hours)
then the script exits early (no checks) to avoid running after the last flight window.

Environment variables:
  AVIATIONSTACK_KEY   - required
  GITHUB_TOKEN        - required (provided by GitHub Actions)
  REPO                - optional; defaults to GITHUB_REPOSITORY
  TARGET_DATE         - required, YYYY-MM-DD
  THRESHOLD_MINUTES   - optional, default 15
  FORCE_RUN           - optional, if set to true/1/yes the script will run even after cutoff

Run locally:
  AVIATIONSTACK_KEY=... GITHUB_TOKEN=... TARGET_DATE=2026-10-16 python check_delays.py
"""
import os
import sys
import requests
from datetime import datetime, timedelta
from dateutil import parser, tz

API_KEY = os.getenv("AVIATIONSTACK_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("REPO") or os.getenv("GITHUB_REPOSITORY")
TARGET_DATE = os.getenv("TARGET_DATE")
THRESHOLD = int(os.getenv("THRESHOLD_MINUTES", "15"))
FORCE_RUN = os.getenv("FORCE_RUN", "").lower() in ("1", "true", "yes")

if not API_KEY:
    print("Missing AVIATIONSTACK_KEY", file=sys.stderr)
    sys.exit(1)

if not TARGET_DATE:
    print("Missing TARGET_DATE", file=sys.stderr)
    sys.exit(1)

if not REPO:
    print("Missing REPO / GITHUB_REPOSITORY", file=sys.stderr)
    sys.exit(1)

OWNER, REPO_NAME = REPO.split("/", 1)
BASE = "http://api.aviationstack.com/v1/flights"
PARAMS = {
    "access_key": API_KEY,
    "dep_iata": "RNO",
    "arr_iata": "BUR",
    "flight_date": TARGET_DATE,
    "limit": 100,
}


def is_southwest(flight):
    airline = flight.get("airline") or {}
    iata = (airline.get("iata") or "").upper()
    name = (airline.get("name") or "").lower()
    return iata == "WN" or "southwest" in name


def minutes_between(a, b):
    return int((a - b).total_seconds() / 60)


def issue_exists(session, title):
    url = f"https://api.github.com/repos/{OWNER}/{REPO_NAME}/issues"
    r = session.get(url, params={"state": "open", "per_page": 100}, timeout=10)
    r.raise_for_status()
    for issue in r.json():
        if issue.get("title") == title:
            return True
    return False


def create_issue(session, title, body):
    url = f"https://api.github.com/repos/{OWNER}/{REPO_NAME}/issues"
    payload = {"title": title, "body": body}
    r = session.post(url, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def run_check():
    # Fetch flights once
    r = requests.get(BASE, params=PARAMS, timeout=15)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        print(f"No flights returned for {TARGET_DATE}.")
        return

    # Determine latest scheduled departure among Southwest flights
    scheduled_times = []
    for flight in data:
        if not is_southwest(flight):
            continue
        scheduled_s = (flight.get("departure") or {}).get("scheduled")
        if scheduled_s:
            try:
                scheduled_times.append(parser.parse(scheduled_s))
            except Exception:
                continue

    if not scheduled_times:
        print(f"No scheduled Southwest departures found for {TARGET_DATE}.")
        return

    latest_scheduled = max(scheduled_times)
    cutoff = latest_scheduled - timedelta(hours=2)
    # convert to UTC for robust comparison
    cutoff_utc = cutoff.astimezone(tz.tzutc())
    now_utc = datetime.now(tz.tzutc())

    print(f"Latest scheduled departure: {latest_scheduled.isoformat()} (cutoff {cutoff_utc.isoformat()})")
    if now_utc > cutoff_utc and not FORCE_RUN:
        print("Current time is past cutoff (latest departure - 2 hours). Exiting without checks.")
        return

    session = requests.Session()
    if GITHUB_TOKEN:
        session.headers.update({
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "rno-bur-monitor/1.0",
        })

    found_any = False
    for flight in data:
        if not is_southwest(flight):
            continue

        flight_number = (
            flight.get("flight", {}).get("iata")
            or flight.get("flight", {}).get("number")
            or "UNKNOWN"
        )
        airline_name = (flight.get("airline") or {}).get("name", "Southwest")
        scheduled_s = (flight.get("departure") or {}).get("scheduled")
        estimated_s = (flight.get("departure") or {}).get("estimated")
        actual_s = (flight.get("departure") or {}).get("actual")
        status = flight.get("flight_status") or "unknown"

        try:
            scheduled = parser.parse(scheduled_s) if scheduled_s else None
            compare_time = (
                parser.parse(estimated_s) if estimated_s else (parser.parse(actual_s) if actual_s else None)
            )
        except Exception as exc:
            print(f"Unable to parse times for {flight_number}: {exc}")
            continue

        if not scheduled or not compare_time:
            print(f"{flight_number}: missing scheduled or compare time ({scheduled_s}, {estimated_s}, {actual_s})")
            continue

        delay_min = minutes_between(compare_time, scheduled)
        if delay_min >= THRESHOLD:
            found_any = True
            local_scheduled = scheduled.astimezone(tz.tzlocal()).strftime("%Y-%m-%d %H:%M %Z")
            local_compare = compare_time.astimezone(tz.tzlocal()).strftime("%Y-%m-%d %H:%M %Z")
            title = f"Delay: {flight_number} {TARGET_DATE} RNO→BUR — {delay_min}m"
            body = (
                f"Detected delay for {airline_name} {flight_number} (RNO → BUR) on {TARGET_DATE}.\n\n"
                f"- Scheduled departure: {local_scheduled}\n"
                f"- Estimated/actual departure: {local_compare}\n"
                f"- Status: {status}\n"
                f"- Delay: {delay_min} minutes\n\n"
                f"Flight data (raw):\n```\n{flight}\n```\n"
            )

            if issue_exists(session, title):
                print(f"Issue already exists: {title}")
            else:
                created = create_issue(session, title, body)
                print(f"Created issue: {created.get('html_url')}")
        else:
            print(f"{flight_number}: not delayed ({delay_min} min) — status {status}")

    if not found_any:
        print(f"No Southwest delays >= {THRESHOLD} min found for {TARGET_DATE}.")


if __name__ == "__main__":
    run_check()

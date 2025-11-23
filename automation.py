import requests
import feedparser
import pandas as pd
from datetime import datetime
from dateutil import parser
import gspread
from google.oauth2.service_account import Credentials
import json
import os

# -----------------------------
# 1. SETTINGS
# -----------------------------
KEYWORD = "AI automation"   # You can edit this anytime
SPREADSHEET_NAME = "Automation Results"   # Your Google Sheet name

# -----------------------------
# 2. GOOGLE SHEET AUTH
# -----------------------------
def connect_to_google_sheet():
    print("Connecting to Google Sheet...")

    # If running inside GitHub Actions, credentials come from the secret
    if "SERVICE_ACCOUNT_JSON" in os.environ:
        service_account_json = os.environ["SERVICE_ACCOUNT_JSON"]
        with open("service_account.json", "w") as f:
            f.write(service_account_json)
        json_path = "service_account.json"
    else:
        # Local testing fallback
        json_path = "service_account.json"

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(json_path, scopes=scopes)
    client = gspread.authorize(creds)

    try:
        sheet = client.open(SPREADSHEET_NAME).sheet1
    except:
        # Create new spreadsheet if not found
        spreadsheet = client.create(SPREADSHEET_NAME)
        spreadsheet.share(None, perm_type="anyone", role="writer")
        sheet = spreadsheet.sheet1

    print("Connected successfully.")
    return sheet

# -----------------------------
# 3. SOURCES
# -----------------------------

# Reddit Search
def fetch_reddit(keyword):
    print("Fetching Reddit data...")
    url = f"https://www.reddit.com/search.json?q={keyword}&sort=new"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=10).json()
        posts = response["data"]["children"]

        data = []
        for p in posts:
            item = p["data"]
            data.append({
                "source": "Reddit",
                "title": item.get("title", ""),
                "link": "https://www.reddit.com" + item.get("permalink", ""),
                "date": datetime.fromtimestamp(item.get("created_utc", 0)).isoformat(),
                "summary": item.get("selftext", "")[:200]
            })
        return data

    except Exception as e:
        print("Reddit error:", e)
        return []


# Google News RSS
def fetch_google_news(keyword):
    print("Fetching Google News RSS...")
    url = f"https://news.google.com/rss/search?q={keyword}"

    try:
        feed = feedparser.parse(url)
        data = []
        for entry in feed.entries:
            data.append({
                "source": "Google News",
                "title": entry.title,
                "link": entry.link,
                "date": parser.parse(entry.published).isoformat(),
                "summary": entry.summary[:200]
            })
        return data

    except Exception as e:
        print("Google News error:", e)
        return []


# Hacker News Search (Algolia API)
def fetch_hacker_news(keyword):
    print("Fetching Hacker News...")
    url = f"http://hn.algolia.com/api/v1/search?query={keyword}&tags=story"

    try:
        response = requests.get(url, timeout=10).json()
        hits = response["hits"]

        data = []
        for h in hits:
            data.append({
                "source": "Hacker News",
                "title": h.get("title", ""),
                "link": h.get("url", ""),
                "date": h.get("created_at", ""),
                "summary": h.get("story_text", "") if h.get("story_text") else ""
            })
        return data

    except Exception as e:
        print("HN error:", e)
        return []

# -----------------------------
# 4. MERGE + CLEAN DATA
# -----------------------------
def clean_and_merge(results):
    print("Cleaning the data...")

    df = pd.DataFrame(results)

    # Drop empty rows
    df = df.dropna(subset=["title"])

    # Remove duplicates using Title + Link
    df = df.drop_duplicates(subset=["title", "link"], keep="first")

    # Sort newest first
    df = df.sort_values(by="date", ascending=False)

    print("Cleaning completed.")
    return df

# -----------------------------
# 5. SAVE TO GOOGLE SHEETS
# -----------------------------
def save_to_sheet(df, sheet):
    print("Uploading to Google Sheets...")

    sheet.clear()

    # Convert df to list of lists
    rows = [df.columns.tolist()] + df.values.tolist()

    sheet.update(rows)

    print("Upload completed.")

# -----------------------------
# 6. MAIN AUTOMATION
# -----------------------------
def run_automation():
    print("Starting automation...")

    reddit = fetch_reddit(KEYWORD)
    gnews = fetch_google_news(KEYWORD)
    hacker = fetch_hacker_news(KEYWORD)

    combined = reddit + gnews + hacker

    df = clean_and_merge(combined)

    sheet = connect_to_google_sheet()
    save_to_sheet(df, sheet)

    print("Automation finished successfully.")

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    run_automation()

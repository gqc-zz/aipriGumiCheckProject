import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime

# =========================
# CONFIG
# =========================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

QUERY = 'site:amazon.co.jp "アイプリカード♪コレクショングミ"'

CHECK_WORDS = [
    "vol.2",
]

SEARCH_URL = (
    "https://www.google.com/search?q="
    + quote(QUERY)
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
}

STATE_FILE = "state.json"

# =========================
# UTIL
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"seen": []}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def notify_discord(message):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL is missing")
        return

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": message},
        timeout=20
    )

    print("Discord status:", r.status_code)


# =========================
# GOOGLE SEARCH
# =========================

def fetch_html():
    r = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        timeout=20
    )

    r.raise_for_status()

    return r.text

# =========================
# NOTIFY CONTROL
# =========================

ERROR_STATE_FILE = "error_state.json"


def load_error_state():
    if not os.path.exists(ERROR_STATE_FILE):
        return {
            "last_error": False,
            "last_start_notify_date": ""
        }

    with open(ERROR_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_error_state(state):
    with open(ERROR_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_morning_notification(error_state):
    now = datetime.now()

    today = now.strftime("%Y-%m-%d")
    hour = now.hour

    # 朝7〜9時のみ
    if hour < 6 or hour >= 10:
        return

    # 今日すでに送信済み
    if error_state["last_start_notify_date"] == today:
        return

    notify_discord("🟢 aipri watcher 正常稼働中")

    error_state["last_start_notify_date"] = today

    save_error_state(error_state)

def handle_error(error_state, message):
    # すでにエラー中なら通知しない
    if error_state["last_error"]:
        print("already in error state")
        return

    notify_discord(f"⚠ watcher error\n\n{message}")

    error_state["last_error"] = True

    save_error_state(error_state)


def clear_error_state(error_state):
    if not error_state["last_error"]:
        return

    notify_discord("🟢 watcher recovered")

    error_state["last_error"] = False

    save_error_state(error_state)

def extract_results(html):
    soup = BeautifulSoup(html, "html.parser")

    results = []
    
    for a in soup.select("a"):
        href = a.get("href", "")

        # Google検索結果リンク
        if not href.startswith("/url?q="):
            continue

        title = a.get_text(" ", strip=True)

        if not title:
            continue

        url = href.split("/url?q=")[1].split("&")[0]

        # Amazonだけ
        if "amazon.co.jp" not in url:
            continue

        # 商品ページ優先
        if "/dp/" not in url:
            continue

        results.append({
            "title": title,
            "url": url,
        })

    return results


# =========================
# FILTER
# =========================

def is_target(title):
    t = title.lower()

    for word in CHECK_WORDS:
        if word.lower() not in t:
            return False

    return True


# =========================
# MAIN
# =========================

def main():
    print("🟢 SCRIPT STARTED")

    error_state = load_error_state()

    send_morning_notification(error_state)

    try:
        state = load_state()

        html = fetch_html()

        print("HTML LENGTH:", len(html))

        results = extract_results(html)

        print("RESULT COUNT:", len(results))

        for item in results:
            print("CHECK:", item["title"])

            if not is_target(item["title"]):
                continue

            uid = item["url"]

            if uid in state["seen"]:
                continue

            state["seen"].append(uid)

            notify_discord(
                "🎉 新商品検知\n\n"
                f"{item['title']}\n"
                f"{item['url']}"
            )

        save_state(state)

        clear_error_state(error_state)

    except Exception as e:
        print("ERROR:", e)

        handle_error(error_state, str(e))

    print("✅ SCRIPT FINISHED")


if __name__ == "__main__":
    main()
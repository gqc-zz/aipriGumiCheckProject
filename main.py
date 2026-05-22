import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

# =========================
# 設定
# =========================

SEARCH_URL = (
    "https://www.amazon.co.jp/s?k="
    "%E3%80%90%E5%88%9D%E5%9B%9E%E7%94%9F%E7%94%A3%E9%99%90%E5%AE%9A%E3%80%91+"
    "BOX+%E3%81%8A%E3%81%AD%E3%81%8C%E3%81%84%E3%82%A2%E3%82%A4%E3%83%97%E3%83%AA+"
    "%E3%82%A2%E3%82%A4%E3%83%97%E3%83%AA%E3%82%AB%E3%83%BC%E3%83%89%E2%99%AA%E3%82%B3%E3%83%AC%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E3%82%B0%E3%83%9F"
)

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

STATE_FILE = "state.json"

CHECK_INTERVAL = 60 * 30  # 30分

TEST_MODE = True

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
}

# =========================
# state管理
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"asins": []}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"asins": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# =========================
# Discord通知
# =========================

def notify_discord(title, url):
    if not DISCORD_WEBHOOK_URL:
        print("Webhook not set")
        return

    try:
        payload = {
            "content": f"🎉 新商品検知\n**{title}**\n{url}"
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print("Discord error:", e)


# =========================
# Amazon取得
# =========================

def fetch_html():
    if TEST_MODE:
        # 必ずヒットするAmazon商品ページ
        url = "https://www.amazon.co.jp/dp/B08N5WRWNW"
    else:
        url = SEARCH_URL

    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

# =========================
# 商品抽出
# =========================

def extract_items(html):
    soup = BeautifulSoup(html, "html.parser")

    items = []
    seen = set()

    for a in soup.select("a[href*='/dp/']"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)

        m = re.search(r"/dp/([A-Z0-9]{10})", href)
        if not m:
            continue

        asin = m.group(1)

        if asin in seen:
            continue
        seen.add(asin)

        if len(text) < 5:
            continue

        items.append({
            "asin": asin,
            "title": text,
            "url": f"https://www.amazon.co.jp/dp/{asin}"
        })

    return items


# =========================
# 判定ロジック
# =========================

def is_target(title):
    keywords = [
        "アイプリ",
        "コレクショングミ",
        "BOX",
        "初回",
    ]

    t = title.lower()

    return all(k.lower() in t for k in keywords)

# =========================
# 初期確認処理
# =========================

def send_startup():
    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": "🟢 Amazon監視開始（正常稼働中）"},
            timeout=10
        )
    except Exception as e:
        print("startup notify failed:", e)
# =========================
# ハートビート処理
# =========================

def heartbeat():
    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": "💓 監視正常稼働中"},
            timeout=10
        )
    except:
        pass 
# =========================
# メイン処理
# =========================

def run_once(state):
    try:
        html = fetch_html()
        items = extract_items(html)

        for item in items:
            asin = item["asin"]
            title = item["title"]
            url = item["url"]

            if asin in state["asins"]:
                continue

            if not is_target(title):
                continue

            print("NEW:", title)
            print(url)

            notify_discord(title, url)

            state["asins"].append(asin)

    except Exception as e:
        print("ERROR:", e)


# =========================
# メインループ
# =========================

def main():
    print("Watcher started")
    print("🟢 SCRIPT STARTED")
    print("WEBHOOK:", DISCORD_WEBHOOK_URL)
    send_startup()
    while True:
        state = load_state()

        run_once(state)

        save_state(state)

        if int(time.time()) % (60 * 60 * 6) < 30:
            heartbeat()

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
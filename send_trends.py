import os
import json
import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
STATE_FILE = "sent_trends.json"


def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN bulunamadi")
    if not CHAT_ID:
        raise ValueError("CHAT_ID bulunamadi")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
    }

    response = requests.post(url, data=data, timeout=15)
    print("Telegram response:", response.status_code, response.text)
    response.raise_for_status()
    return True


def get_google_trends():
    try:
        pytrends = TrendReq(hl="tr-TR", tz=180, timeout=(10, 25))
        trends = pytrends.trending_searches(pn="turkey")
        return trends[0].dropna().astype(str).tolist()
    except Exception as e:
        print("Google Trends fallback:", str(e))
        return [
            "bitcoin",
            "dolar",
            "yapayzeka",
            "instagram",
            "sondakika",
            "teknoloji",
        ]


def clean_hashtag(text: str) -> str:
    text = text.strip()

    if not text.startswith("#"):
        return ""

    body = text[1:]
    allowed = []

    for ch in body:
        if ch.isalnum() or ch == "_":
            allowed.append(ch)

    cleaned = "".join(allowed)

    if len(cleaned) < 2:
        return ""

    return "#" + cleaned


def get_x_trends():
    try:
        url = "https://trends24.in/turkey/"
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            },
        )

        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        trends = []
        seen = set()

        for a in soup.find_all("a"):
            text = a.get_text(" ", strip=True)
            cleaned = clean_hashtag(text)

            if not cleaned:
                continue

            low = cleaned.lower()

            bad_fragments = [
                "trends24",
                "twitter",
                "trends",
                "turkey",
                "location",
                "explore",
                "login",
                "signup",
            ]

            if any(bad in low for bad in bad_fragments):
                continue

            if low not in seen:
                seen.add(low)
                trends.append(cleaned)

        return trends[:10]

    except Exception as e:
        print("X Trends fallback:", str(e))
        return []


def normalize_tag(value: str) -> str:
    value = str(value).strip()

    if not value:
        return ""

    value = value.replace(" ", "")

    if not value.startswith("#"):
        value = "#" + value

    return value


def get_all_trends():
    google_trends = get_google_trends()
    x_trends = get_x_trends()

    merged = []
    seen = set()

    for item in x_trends + google_trends:
        value = normalize_tag(item)

        if not value or len(value) < 2:
            continue

        low = value.lower()

        if low not in seen:
            seen.add(low)
            merged.append(value)

    return merged[:10]


def load_sent_trends():
    if not os.path.exists(STATE_FILE):
        return []

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []
    except Exception as e:
        print("State file okunamadi:", str(e))
        return []


def save_sent_trends(trends):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)


def get_new_trends(current_trends, old_trends):
    old_set = {str(x).lower() for x in old_trends}
    return [trend for trend in current_trends if trend.lower() not in old_set]


def build_message(trends):
    if not trends:
        return ""

    lines = ["🔥 Yeni Trendler", ""]

    for i, trend in enumerate(trends, start=1):
        lines.append(f"{i}. {trend}")

    return "\n".join(lines)


def main():
    current_trends = get_all_trends()
    old_trends = load_sent_trends()
    new_trends = get_new_trends(current_trends, old_trends)

    if not new_trends:
        print("Yeni trend yok. Mesaj gonderilmedi.")
        return

    message = build_message(new_trends[:10])
    send_telegram(message)
    save_sent_trends(current_trends)

    print("Yeni trendler gonderildi.")


if __name__ == "__main__":
    main()

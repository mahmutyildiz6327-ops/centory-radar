import os
import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


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


def build_message(trends):
    if not trends:
        return "🔥 Saatlik Trendler\n\nBugun su anda uygun trend bulunamadi."

    lines = ["🔥 Saatlik Trendler", ""]

    for i, trend in enumerate(trends, start=1):
        lines.append(f"{i}. {trend}")

    return "\n".join(lines)


def main():
    trends = get_all_trends()
    message = build_message(trends)

    ok = send_telegram(message)

    if ok:
        print("Mesaj gonderildi.")
    else:
        print("Mesaj gonderilemedi.")


if __name__ == "__main__":
    main()

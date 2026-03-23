import os
import re
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
            "yapay zeka",
            "instagram",
            "son dakika",
            "teknoloji",
        ]


def normalize_hashtag(text: str) -> str:
    text = str(text).strip()

    if not text:
        return ""

    if not text.startswith("#"):
        return ""

    body = text[1:]

    cleaned = []
    for ch in body:
        if ch.isalnum() or ch == "_":
            cleaned.append(ch)

    body = "".join(cleaned)

    if not body:
        return ""

    return "#" + body


def is_valid_hashtag(tag: str) -> bool:
    if not tag.startswith("#"):
        return False

    body = tag[1:]

    if len(body) < 2:
        return False

    if len(body) > 24:
        return False

    # tamamen sayi veya neredeyse sayiysa alma
    letters = sum(1 for c in body if c.isalpha())
    digits = sum(1 for c in body if c.isdigit())

    if letters == 0:
        return False

    if digits > letters:
        return False

    # cok fazla alt cizgi istemiyoruz
    if body.count("_") > 2:
        return False

    # cok garip tekrarli etiketleri ele
    if len(set(body.lower())) <= 2 and len(body) > 4:
        return False

    low = body.lower()

    blocked_exact = {
        "turkey",
        "trends",
        "trend",
        "twitter",
        "x",
        "gundem",
        "gündem",
        "kesfet",
        "keşfet",
        "explore",
        "login",
        "signup",
        "register",
        "account",
        "home",
        "news",
        "video",
        "photos",
        "turkiye",
        "türkiye",
    }

    if low in blocked_exact:
        return False

    blocked_fragments = [
        "trends24",
        "login",
        "signup",
        "register",
        "status",
        "photo",
        "video",
        "explore",
        "search",
        "privacy",
        "cookie",
        "terms",
    ]

    if any(bad in low for bad in blocked_fragments):
        return False

    # en az bir harf olsun, sadece karisik random sayi-harf olmasin
    if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", body):
        return False

    return True


def extract_hashtags_from_text(text: str):
    matches = re.findall(r"#([A-Za-z0-9ÇĞİÖŞÜçğıöşü_]{2,24})", text)
    return ["#" + m for m in matches]


def get_x_trends():
    urls = [
        "https://trends24.in/turkey/",
        "https://trends24.in/turkiye/",
    ]

    all_tags = []
    seen = set()

    for url in urls:
        try:
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

            candidate_texts = []

            # linklerden metin topla
            for a in soup.find_all("a"):
                txt = a.get_text(" ", strip=True)
                if txt:
                    candidate_texts.append(txt)

            # sayfanin duz metninden de hashtag ayikla
            page_text = soup.get_text(" ", strip=True)
            if page_text:
                candidate_texts.append(page_text)

            for raw_text in candidate_texts:
                tags = extract_hashtags_from_text(raw_text)

                for tag in tags:
                    tag = normalize_hashtag(tag)

                    if not tag:
                        continue

                    if not is_valid_hashtag(tag):
                        continue

                    low = tag.lower()
                    if low not in seen:
                        seen.add(low)
                        all_tags.append(tag)

            if all_tags:
                break

        except Exception as e:
            print("X Trends source error:", url, str(e))

    return all_tags[:10]


def normalize_google_item(text: str) -> str:
    text = str(text).strip()

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()

    # cöp kadar kisa olanlari alma
    if len(text) < 2:
        return ""

    return text


def get_all_trends():
    x_trends = get_x_trends()

    # X tarafindan yeterince etiket geldiyse onu kullan
    if len(x_trends) >= 3:
        return x_trends[:10]

    # yetmezse Google Trends ile destekle
    google_trends = get_google_trends()

    merged = []
    seen = set()

    for item in x_trends:
        low = item.lower()
        if low not in seen:
            seen.add(low)
            merged.append(item)

    for item in google_trends:
        value = normalize_google_item(item)
        if not value:
            continue

        low = value.lower()
        if low not in seen:
            seen.add(low)
            merged.append(value)

    return merged[:10]


def get_new_trends(current_trends, old_trends):
    old_set = {str(x).lower() for x in old_trends}
    return [trend for trend in current_trends if trend.lower() not in old_set]


def build_message(trends):
    if not trends:
        return ""

    lines = ["🔥 Trend Radar", ""]

    for i, trend in enumerate(trends, start=1):
        lines.append(f"{i}. {trend}")

    return "\n".join(lines)


def main():
    current_trends = get_all_trends()
    old_trends = load_sent_trends()
    new_trends = get_new_trends(current_trends, old_trends)

    if not current_trends:
        print("Trend bulunamadi.")
        return

    if not new_trends:
        print("Yeni trend yok. Mesaj gonderilmedi.")
        return

    message = build_message(new_trends[:10])
    send_telegram(message)
    save_sent_trends(current_trends)

    print("Yeni trendler gonderildi.")


if __name__ == "__main__":
    main()

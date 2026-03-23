import os
import re
import json
import requests
import tweepy
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

STATE_FILE = "sent_trends.json"

BASE_POST_TEXT = (
    "Gundemde one cikan basliklari takip ediyorum.\n"
    "Iste su an dikkat ceken etiketler:"
)


def load_sent_trends():
    if not os.path.exists(STATE_FILE):
        return []

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print("State file okunamadi:", str(e))
        return []


def save_sent_trends(trends):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)


def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram secrets yok, Telegram atlandi.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
    }

    response = requests.post(url, data=data, timeout=20)
    print("Telegram response:", response.status_code, response.text)
    response.raise_for_status()
    return True


def send_x_post(text: str) -> bool:
    required = [X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]
    if not all(required):
        raise ValueError("X API secretleri eksik")

    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
    )

    response = client.create_tweet(text=text)
    print("X post response:", response.data)
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
            "altin",
            "petrol",
            "borsa",
            "yapay zeka",
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

    body = "".join(cleaned).strip("_")

    if not body:
        return ""

    return "#" + body


def extract_hashtags_from_text(text: str):
    matches = re.findall(r"#([A-Za-z0-9ÇĞİÖŞÜçğıöşü_]{2,30})", text)
    return ["#" + m for m in matches]


def is_valid_hashtag(tag: str) -> bool:
    if not tag.startswith("#"):
        return False

    body = tag[1:]
    low = body.lower()

    if len(body) < 2:
        return False

    if len(body) > 18:
        return False

    letters = sum(1 for c in body if c.isalpha())
    digits = sum(1 for c in body if c.isdigit())

    if letters == 0:
        return False

    if digits > letters:
        return False

    if body.count("_") > 1:
        return False

    if len(set(low)) <= 2 and len(body) > 4:
        return False

    if body.isupper() and len(body) > 6:
        return False

    if re.search(r"[A-Z][a-z]+[A-Z]", body) and len(body) > 12:
        return False

    blocked_exact = {
        "turkey",
        "turkiye",
        "türkiye",
        "trend",
        "trends",
        "twitter",
        "gundem",
        "gündem",
        "kesfet",
        "keşfet",
        "explore",
        "login",
        "signup",
        "register",
        "home",
        "video",
        "news",
        "status",
    }

    if low in blocked_exact:
        return False

    blocked_fragments = [
        "trends24",
        "login",
        "signup",
        "register",
        "privacy",
        "cookie",
        "search",
        "explore",
        "video",
        "photo",
        "status",
        "account",
        "official",
        "only",
        "follow",
        "join",
        "live",
    ]

    if any(x in low for x in blocked_fragments):
        return False

    blocked_keywords = [
        "enhypen",
        "army",
        "bts",
        "blackpink",
        "kpop",
        "vote",
        "stream",
        "stan",
        "fandom",
        "fan",
        "award",
        "comeback",
        "taniyalim",
        "tanıyalım",
        "hakayagakalk",
        "always",
        "selam",
        "dua",
        "kutluolsun",
    ]

    if any(x in low for x in blocked_keywords):
        return False

    if "_" in body and len(body) > 10:
        return False

    if sum(1 for c in body if c.isupper()) >= 4:
        return False

    return True


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
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                },
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"

            soup = BeautifulSoup(response.text, "html.parser")

            candidate_texts = []

            for a in soup.find_all("a"):
                txt = a.get_text(" ", strip=True)
                if txt:
                    candidate_texts.append(txt)

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
    low = text.lower()

    blocked_google = [
        "canli skor",
        "canlı skor",
        "hava durumu",
        "son dakika",
        "tv yayin akisi",
        "tv yayın akışı",
    ]

    if any(x in low for x in blocked_google):
        return ""

    if len(text) > 24:
        return ""

    return text


def get_all_trends():
    x_trends = get_x_trends()

    if len(x_trends) >= 3:
        return x_trends[:10]

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


def choose_hashtags(trends, limit=3):
    hashtags = [t for t in trends if str(t).startswith("#")]
    if hashtags:
        return hashtags[:limit]

    fallback = []
    for t in trends:
        text = str(t).strip().replace(" ", "")
        if not text:
            continue
        fallback.append("#" + text[:18])
        if len(fallback) >= limit:
            break
    return fallback


def build_post_text(tags):
    hashtag_line = " ".join(tags)
    return f"{BASE_POST_TEXT}\n\n{hashtag_line}".strip()


def main():
    current_trends = get_all_trends()

    if not current_trends:
        print("Trend bulunamadi.")
        return

    old_trends = load_sent_trends()
    new_trends = get_new_trends(current_trends, old_trends)

    if not new_trends:
        print("Yeni trend yok. Mesaj gonderilmedi.")
        return

    tags = choose_hashtags(new_trends, limit=3)
    post_text = build_post_text(tags)

    send_x_post(post_text)
    send_telegram(post_text)

    save_sent_trends(current_trends)
    print("X ve Telegram gonderimi tamamlandi.")


if __name__ == "__main__":
    main()

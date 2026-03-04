import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "92f87f8b62f14bbdb17329ba4cb4e34c")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://claude-telegram.onrender.com")
PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else None

def fetch_page_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        title = None
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "").strip()
        elif soup.title:
            title = soup.title.string.strip()
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content", "").strip():
            body_text = og_desc.get("content", "").strip()
        else:
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            body_text = soup.get_text(separator=" ", strip=True)[:3000]
        return title, body_text
    except Exception:
        return None, None

def summarize_with_gemini(title, body_text, url):
    if not GEMINI_API_KEY:
        return "요약 불가 (API 키 없음)"
    try:
        prompt = f"""다음 웹페이지 내용을 한국어로 3~4줄 요약해줘. 핵심 내용만 간결하게.

제목: {title or '알 수 없음'}
URL: {url}
본문: {body_text or '본문 없음'}

요약:"""
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=15
        )
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error(f"요약 실패: {e}")
        return body_text[:500] if body_text else url

def classify_message(text):
    if extract_url(text):
        return "링크"
    idea_keywords = ["아이디어", "idea", "생각", "어떨까", "기획", "제안"]
    for kw in idea_keywords:
        if kw in text.lower():
            return "아이디어"
    return "메모"

def detect_source(text):
    sources = {
        "instagram.com": "인스타그램",
        "youtube.com": "유튜브",
        "youtu.be": "유튜브",
        "twitter.com": "트위터",
        "x.com": "트위터",
        "tiktok.com": "틱톡",
        "naver.com": "네이버",
        "facebook.com": "페이스북",
    }
    for domain, name in sources.items():
        if domain in text:
            return name
    return "텔레그램"

def save_to_notion(title, content, url, category, source):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    properties = {
        "제목": {"title": [{"text": {"content": title[:100]}}]},
        "분류": {"select": {"name": category}},
        "내용": {"rich_text": [{"text": {"content": content[:2000]}}]},
        "출처": {"rich_text": [{"text": {"content": source}}]},
    }
    if url:
        properties["URL"] = {"url": url}
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json={"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
    )
    return response.status_code == 200

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    text = message.text.strip()
    url = extract_url(text)
    category = classify_message(text)
    source = detect_source(text)

    if url:
        await message.reply_text("잠깐만요, 내용 요약 중...")
        title, body_text = fetch_page_content(url)
        blocked_keywords = ["log in", "sign up", "login", "로그인", "회원가입"]
        is_blocked = not body_text or any(kw in body_text.lower() for kw in blocked_keywords)
        if is_blocked:
            extra_text = text.replace(url, "").strip()
            summary = summarize_with_gemini(
                title=None,
                body_text=extra_text if extra_text else f"이 URL을 사용자가 저장했습니다: {url}",
                url=url
            )
            title = title if title and "log in" not in title.lower() else url
        else:
            summary = summarize_with_gemini(title, body_text, url)
            title = title if title else url
    else:
        title = text.split("\n")[0]
        summary = text

    if save_to_notion(title, summary, url, category, source):
        await message.reply_text(f"Notion 저장 완료!\n제목: {title}\n분류: {category}\n출처: {source}")
    else:
        await message.reply_text("저장 실패. 설정을 확인해주세요.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("봇 시작! (webhook 모드)")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )

if __name__ == "__main__":
    main()

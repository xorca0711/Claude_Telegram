import os
import re
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "92f87f8b62f14bbdb17329ba4cb4e34c")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_url(text):
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else None

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
    first_line = text.split("\n")[0]
    title = first_line if len(first_line) > 5 else (url or "무제")

    if save_to_notion(title, text, url, category, source):
        await message.reply_text(f"Notion 저장 완료!\n분류: {category}\n출처: {source}")
    else:
        await message.reply_text("저장 실패. 설정을 확인해주세요.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("봇 시작!")
    app.run_polling()

if __name__ == "__main__":
    main()

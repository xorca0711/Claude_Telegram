# Claude_Telegram
Telegram messages and links are saved to Notion with a Korean summary, one
color-coded theme, and up to three subject tags.

## Notion setup

Keep the existing 제목, 내용, URL, 분류, 출처 and 저장일 properties.
Add the following properties before deploying this version:

- 테마: Select. Use the exact values in THEMES in bot.py.
- 주제: Multi-select. Use the exact values in SUBJECTS in bot.py.
- 분류 상태: Select with 분류 완료 and 확인 필요.

These fields and views were created in the linked Telegram inbox on 2026-09-06.
The original table is grouped by 테마. Additional tabs offer a theme board,
a subject board, and 확인 필요 for empty or uncertain classifications.
Keep one database so the existing bot destination remains valid.

## Configuration and rollout

Existing environment variables remain TELEGRAM_BOT_TOKEN, NOTION_API_KEY,
NOTION_DATABASE_ID, WEBHOOK_URL and PORT. Set GEMINI_API_KEY for automatic
summaries and classification. GEMINI_MODEL defaults to gemini-2.5-flash and
can be changed to a structured-output-capable model available to your account.
The API key stays in a request header.

Install requirements.txt and run python bot.py. On Render, merge this change
and deploy the new commit using the existing service environment. This PR
does not deploy the service or change its Telegram webhook.

The model returns validated JSON, following Google's structured output API:
https://ai.google.dev/gemini-api/docs/generate-content/structured-output
Titles, content, theme names and subject tags are checked before saving.
Unrecognized output, missing keys, timeouts and unavailable previews fall
back to 확인 필요 while retaining available text and the source URL.
A descriptive Telegram note can categorize a link whose preview is blocked.
The bot does not inspect image/video pixels or bypass platform login pages.
Plain text notes retain their original text in 내용.

## Validation

Run python -m unittest -v. Tests mock Telegram, Gemini and Notion calls;
they do not send messages or create production pages.
After deployment, send a descriptive link and a bare inaccessible link
through the bot and confirm their theme/subject and review placement.
Existing items are not overwritten by this version; taxonomy backfills
should update only the three new properties.


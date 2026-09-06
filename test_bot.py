import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import requests
import bot


class ClassificationTests(unittest.TestCase):
    def result(self, **changes):
        result = {"title": "팔 운동 루틴", "summary": "팔 운동 방법을 설명합니다.",
                  "theme": "💪 건강·운동", "subjects": ["운동"], "needs_review": False}
        result.update(changes)
        return result

    def response(self, result):
        response = Mock()
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": json.dumps(result)}]}}]}
        return response

    @patch.object(bot, "GEMINI_API_KEY", "test-key")
    @patch.object(bot.requests, "post")
    def test_classification_and_summary_in_one_request(self, post):
        post.return_value = self.response(self.result())
        result = bot.analyze_content("운동", "이두근과 삼두근 운동 방법", "https://example.com")
        self.assertEqual(result["theme"], "💪 건강·운동")
        self.assertEqual(result["subjects"], ["운동"])
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("test-key", post.call_args.args[0])

    @patch.object(bot, "GEMINI_API_KEY", "test-key")
    @patch.object(bot.requests, "post")
    def test_blocked_or_generic_preview_does_not_guess(self, post):
        for body in ["Instagram", "Our systems have detected unusual traffic",
                     "이 URL을 사용자가 저장했습니다: https://example.com"]:
            with self.subTest(body=body):
                result = bot.analyze_content("Instagram", body, "https://example.com")
                self.assertEqual(result["theme"], bot.REVIEW)
                self.assertTrue(result["needs_review"])
        post.assert_not_called()

    @patch.object(bot, "GEMINI_API_KEY", "test-key")
    @patch.object(bot.requests, "post")
    def test_user_note_can_classify_blocked_url(self, post):
        post.return_value = self.response(self.result())
        result = bot.analyze_content("Instagram", "Instagram", "https://example.com", "팔 운동 루틴")
        self.assertFalse(result["needs_review"])
        self.assertEqual(post.call_count, 1)

    @patch.object(bot, "GEMINI_API_KEY", None)
    def test_missing_key_preserves_content(self):
        result = bot.analyze_content("제목", "소중한 메모")
        self.assertEqual(result["summary"], "소중한 메모")
        self.assertTrue(result["needs_review"])

    @patch.object(bot, "GEMINI_API_KEY", "test-key")
    @patch.object(bot.requests, "post")
    def test_invalid_model_output_falls_back(self, post):
        for invalid in [self.result(theme="invented"), self.result(subjects=["invented"]),
                        self.result(needs_review="false"), self.result(title=""),
                        self.result(subjects=[{}]), [], None]:
            post.return_value = self.response(invalid)
            result = bot.analyze_content("원본", "보존할 내용")
            self.assertEqual(result["theme"], bot.REVIEW)
            self.assertEqual(result["summary"], "보존할 내용")

    @patch.object(bot, "GEMINI_API_KEY", "test-key")
    @patch.object(bot.requests, "post", side_effect=requests.Timeout)
    def test_model_timeout_preserves_content(self, post):
        self.assertEqual(bot.analyze_content("원본", "메모")["summary"], "메모")

    @patch.object(bot.requests, "post")
    def test_notion_payload_keeps_old_fields_and_adds_taxonomy(self, post):
        self.assertTrue(bot.save_to_notion("제목", "내용", "https://example.com", "링크", "텔레그램", self.result()))
        payload = post.call_args.kwargs["json"]["properties"]
        self.assertEqual(payload["주제"]["multi_select"], [{"name": "운동"}])
        self.assertEqual(payload["분류 상태"]["select"]["name"], "분류 완료")
        self.assertEqual(payload["URL"]["url"], "https://example.com")
        self.assertEqual(payload["분류"]["select"]["name"], "링크")

    @patch.object(bot.requests, "post", side_effect=requests.Timeout)
    def test_notion_failure_reports_failure(self, post):
        self.assertFalse(bot.save_to_notion("제목", "내용", None, "메모", "텔레그램", self.result()))

    def test_format_and_source(self):
        self.assertEqual(bot.classify_message("아이디어 하나"), "💡 아이디어")
        self.assertEqual(bot.extract_url("메모 https://example.com 다음"), "https://example.com")
        self.assertEqual(bot.detect_source("https://notx.com"), "텔레그램")
        self.assertEqual(bot.detect_source("https://www.instagram.com/p/example"), "인스타그램")


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    @patch.object(bot, "analyze_content")
    @patch.object(bot, "save_to_notion")
    async def test_text_message_retains_original(self, save, analyze):
        analyze.return_value = {"title": "제목", "summary": "요약", "theme": bot.REVIEW,
                                "subjects": [], "needs_review": True}
        save.return_value = True
        message = Mock(text="원본 메모\n두 번째 줄", reply_text=AsyncMock())
        await bot.handle_message(Mock(message=message), Mock())
        self.assertEqual(save.call_args.args[1], "원본 메모\n두 번째 줄")
        self.assertIn("Notion 저장 완료", message.reply_text.call_args.args[0])


if __name__ == "__main__":
    unittest.main()


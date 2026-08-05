import json
import unittest
from unittest.mock import Mock, patch

from app.nodes import analyze_email_node, clean_email_text
from app.email_client import urgency_from_subject
from app.store import apply_rule


class CleanEmailTests(unittest.TestCase):
    def test_removes_html_quotes_and_old_thread(self):
        raw = "<b>请今天确认</b>\n\nOn Tue, A wrote:\n> very old content"
        cleaned = clean_email_text(raw)
        self.assertEqual(cleaned, "请今天确认")

    def test_truncates_input(self):
        self.assertEqual(clean_email_text("a" * 20, max_chars=5), "aaaaa")

    def test_ad_subject_is_low_priority(self):
        self.assertEqual(urgency_from_subject("<广告> 立即购买"), "低")
        self.assertEqual(urgency_from_subject(" ＜广告＞限时优惠"), "低")

    def test_enterprise_notice_defaults_low_except_account_action(self):
        self.assertEqual(urgency_from_subject("Product news", "Wolfram <news@wolfram.com>"), "低")
        self.assertEqual(urgency_from_subject("账号验证通知", "Microsoft <mail@microsoft.com>"), "普通")
        self.assertEqual(urgency_from_subject("订阅即将到期", "OneDrive <mail@onedrive.com>"), "紧急")

    def test_custom_rule_matches_sender_and_subject(self):
        rules = [{"sender_contains": "boss@example.com", "subject_contains": "合同", "urgency": "紧急"}]
        self.assertEqual(apply_rule(rules, "Boss <boss@example.com>", "合同确认"), "紧急")
        self.assertIsNone(apply_rule(rules, "Boss <boss@example.com>", "午餐"))

class AnalyzeEmailTests(unittest.TestCase):
    @patch("app.nodes.get_llm")
    def test_one_call_returns_normalized_fields(self, get_llm):
        llm = Mock()
        llm.invoke.return_value.content = json.dumps({
            "summary": "今天确认方案",
            "urgency": "紧急",
            "draft_reply": "收到，我会尽快确认。",
        }, ensure_ascii=False)
        get_llm.return_value = llm

        result = analyze_email_node({"email_content": "请今天确认方案", "user_instruction": "简短回复"})

        self.assertEqual(result["urgency"], "紧急")
        self.assertEqual(llm.invoke.call_count, 1)

    @patch("app.nodes.get_llm")
    def test_invalid_urgency_falls_back(self, get_llm):
        llm = Mock()
        llm.invoke.return_value.content = '{"summary":"通知", "urgency":"一般", "draft_reply":""}'
        get_llm.return_value = llm
        self.assertEqual(analyze_email_node({"email_content": "通知"})["urgency"], "普通")

    @patch("app.nodes.get_llm")
    def test_ad_subject_overrides_model_urgency(self, get_llm):
        llm = Mock()
        llm.invoke.return_value.content = '{"summary":"促销", "urgency":"紧急", "draft_reply":""}'
        get_llm.return_value = llm
        result = analyze_email_node({"email_content": "主题: <广告> 立即购买\n正文: 限时促销"})
        self.assertEqual(result["urgency"], "低")

    @patch("app.nodes.get_llm")
    def test_enterprise_body_action_is_not_forced_to_ad(self, get_llm):
        llm = Mock()
        llm.invoke.return_value.content = '{"summary":"需要验证", "urgency":"普通", "draft_reply":""}'
        get_llm.return_value = llm
        result = analyze_email_node({"email_content": "发件人: OneDrive\n主题: Account notice\n正文: 请完成账号验证"})
        self.assertEqual(result["urgency"], "普通")


if __name__ == "__main__":
    unittest.main()

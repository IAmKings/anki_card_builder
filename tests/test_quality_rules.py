"""内容层规则 Q1–Q9：确定性、逐条可断言，不依赖 ingest 或模型。"""

import unittest

from ankicards.quality import (ERROR, RULE_LEVEL, RULE_TEXT, WARNING,
                               check_card)


def rules(card, unit_text=None):
    return [finding.rule for finding in check_card(card, unit_text=unit_text)]


def qa(q, a, **extra):
    return {"type": "qa", "q": q, "a": a, **extra}


class QualityRulesTest(unittest.TestCase):
    def test_rule_table_is_complete(self):
        expected = {f"Q{i}" for i in range(1, 10)}
        self.assertEqual(set(RULE_TEXT), expected)
        self.assertEqual(set(RULE_LEVEL), expected)
        self.assertTrue(all(level in (ERROR, WARNING) for level in RULE_LEVEL.values()))

    def test_clean_card_has_no_findings(self):
        self.assertEqual(check_card(qa("什么是幂等？", "同一操作执行多次与执行一次的结果相同。")), [])

    def test_q1_short_answer(self):
        self.assertEqual(rules(qa("什么是 TAG？", "短")), ["Q1"])
        self.assertEqual(RULE_LEVEL["Q1"], ERROR)

    def test_q2_dangling_punctuation(self):
        self.assertIn("Q2", rules(qa("启动服务要监听什么？", "监听端口 8080；")))
        self.assertEqual(RULE_LEVEL["Q2"], ERROR)

    def test_q2_answer_is_prefix_of_source_unit(self):
        card = qa("启动服务要做什么？", "监听端口")
        self.assertIn("Q2", rules(card, unit_text="1. **启动服务**：监听端口 8080 并开启 TLS。"))

    def test_q2_not_triggered_when_answer_ends_the_unit(self):
        card = qa("环境准备要做什么？", "安装运行时依赖")
        self.assertNotIn("Q2", rules(card, unit_text="1. **环境准备**：安装运行时依赖"))

    def test_q3_cross_reference(self):
        self.assertIn("Q3", rules(qa("日志在哪？", "见第 4 节。")))
        self.assertIn("Q3", rules(qa("日志在哪？", "同上")))
        self.assertEqual(RULE_LEVEL["Q3"], ERROR)

    def test_q4_heading_word_as_prompt(self):
        self.assertIn("Q4", rules(qa("什么是第一步？", "先安装依赖，再启动服务。")))
        self.assertEqual(RULE_LEVEL["Q4"], WARNING)

    def test_q5_prompt_equals_answer(self):
        self.assertIn("Q5", rules(qa("幂等", "幂等")))
        self.assertEqual(RULE_LEVEL["Q5"], ERROR)

    def test_q6_long_answer(self):
        self.assertIn("Q6", rules(qa("长答案是什么？", "长" * 201)))
        self.assertEqual(RULE_LEVEL["Q6"], WARNING)

    def test_q7_header_row_as_data(self):
        self.assertIn("Q7", rules(qa("概念", "解释 | 说明")))
        self.assertIn("Q7", rules(qa("解释", "说明 | 内容")))
        self.assertNotIn("Q7", rules(qa("端口", "8080 | 开启 TLS")))
        self.assertEqual(RULE_LEVEL["Q7"], WARNING)

    def test_q8_multiple_numbered_points(self):
        self.assertIn("Q8", rules(qa("部署步骤？", "1. 安装依赖 2. 启动服务")))
        self.assertEqual(RULE_LEVEL["Q8"], WARNING)

    def test_q9_incomplete_ending(self):
        self.assertIn("Q9", rules(qa("这句话完整吗？", "这是一个没有句号的答案但是长度超过二十个字符")))
        self.assertEqual(RULE_LEVEL["Q9"], WARNING)

    def test_cloze_uses_text_and_extra(self):
        card = {"type": "cloze", "text": "{{c1::短}}", "extra": "短"}
        self.assertIn("Q1", rules(card))


if __name__ == "__main__":
    unittest.main()

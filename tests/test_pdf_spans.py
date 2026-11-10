"""PDF 跨页检测：只标记「可能在续写」的相邻页，不替人决定怎么用。"""

from __future__ import annotations

import unittest

from ankicards.ingest import _page_spans


class PageSpanTest(unittest.TestCase):
    def test_mid_sentence_boundary_makes_span(self):
        spans = _page_spans({1: "上一段没有结束", 2: "下一段接着"})
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["locator"], "page:1-2")
        self.assertEqual(spans[0]["pages"], [1, 2])

    def test_sentence_end_does_not_span(self):
        self.assertEqual(_page_spans({1: "上一段结束了。", 2: "下一段"}), [])

    def test_empty_page_skipped(self):
        self.assertEqual(_page_spans({1: "没有结束", 2: "   ", 3: "继续"}), [])

    def test_chars_sum_both_pages(self):
        spans = _page_spans({1: "abc", 2: "de"})
        self.assertEqual(spans[0]["chars"], 5)

    def test_span_ids_follow_left_page(self):
        spans = _page_spans({3: "未完", 4: "待续"})
        self.assertEqual(spans[0]["id"], "span:3")

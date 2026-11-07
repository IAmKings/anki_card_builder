"""净化器的绕过回归：每一条都是评审中实际复现过的攻击形状。"""

import re
import unittest

from ankicards.sanitize import sanitize_html


class SanitizeBypassTest(unittest.TestCase):
    def test_script_with_content_removed(self):
        clean = sanitize_html("<b>答案</b><script>alert(1)</script>")
        self.assertEqual(clean, "<b>答案</b>")

    def test_svg_onload_removed(self):
        clean = sanitize_html("<svg/onload=alert(1)>")
        self.assertNotIn("onload", clean.lower())
        self.assertNotIn("<svg", clean.lower())

    def test_entity_encoded_javascript_removed(self):
        clean = sanitize_html('<a href="jav&#x61;script:alert(1)">x</a>')
        self.assertNotIn("javascript", clean.lower())
        self.assertNotIn("script", clean.lower())
        self.assertIn("<a>x</a>", clean)

    def test_slash_separated_event_attr_not_an_attribute(self):
        clean = sanitize_html("<img src=x/onerror=alert(1)>")
        # 不允许出现“空白 + onXXX=”属性；值里残留的文本不构成事件处理器
        self.assertNotRegex(clean, r"(?i)\s+on[a-z]+\s*=")
        self.assertEqual(clean.count("<img"), 1)

    def test_nested_script_not_reassembled(self):
        clean = sanitize_html("<scr<script>ipt>alert(1)</scr<script>ipt>")
        self.assertNotIn("<script", clean.lower())
        self.assertNotIn("</script", clean.lower())

    def test_style_removed_with_content(self):
        clean = sanitize_html("<style>body{background:url(x)}</style>ok")
        self.assertEqual(clean, "ok")

    def test_allowed_markup_preserved(self):
        html_in = ('<table><tr><th>A</th><td><b>B</b></td></tr></table>'
                   '<br><ul><li>x</li></ul>')
        clean = sanitize_html(html_in)
        self.assertIn("<table>", clean)
        self.assertIn("<th>A</th>", clean)
        self.assertIn("<b>B</b>", clean)
        self.assertIn("<br>", clean)
        self.assertIn("<li>x</li>", clean)

    def test_data_image_png_allowed_svg_rejected(self):
        self.assertIn("data:image/png", sanitize_html('<img src="data:image/png;base64,AAAA">'))
        self.assertNotIn("data:", sanitize_html('<img src="data:image/svg+xml;base64,AAAA">'))

    def test_quotes_never_break_out_of_attribute(self):
        clean = sanitize_html('<img src="x&quot; onerror=&quot;alert(1)">')
        self.assertEqual(clean.count("<img"), 1)
        self.assertEqual(clean.count("src="), 1)
        self.assertNotIn("<script", clean.lower())

    def test_self_closing_blocked_tags_removed(self):
        self.assertEqual(sanitize_html("<script/>ok"), "ok")
        self.assertEqual(sanitize_html("<style/>ok"), "ok")
        self.assertIn("<br>", sanitize_html("a<br/>b"))

    def test_relative_media_kept(self):
        self.assertIn('src="abc-1.jpg"', sanitize_html('<img class="photo" src="abc-1.jpg">'))


if __name__ == "__main__":
    unittest.main()

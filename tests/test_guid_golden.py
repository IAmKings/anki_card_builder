"""黄金测试：锁定 note guid 的派生算法。

身份规则一旦改变，已发布的牌组在 Anki 里会变成新卡而不是更新旧卡。
本测试用固定输入断言 seed 与 sha1 前缀；改算法必须显式改这里，而不是悄悄漂移。
"""

import hashlib
import unittest

from ankicards.schema import identity_seed

GOLDEN = [
    ({"type": "qa", "q": "问 题", "a": "答 案"},
     '黄金牌组|["qa", "问题", "答案"]', "b6bf190585e1"),
    ({"type": "image", "q": "哪张？", "a": "A", "img": "图1"},
     '黄金牌组|["image", "图1", "哪张？", "A"]', "4bb380854af8"),
    ({"type": "cloze", "text": "x{{c1::y}}"},
     '黄金牌组|["cloze", "x{{c1::y}}"]', "74532b7b7885"),
]


class GuidGoldenTest(unittest.TestCase):
    def test_identity_seed_is_stable(self):
        for card, seed, guid in GOLDEN:
            self.assertEqual(identity_seed("黄金牌组", card), seed)
            self.assertEqual(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12], guid)

    def test_build_uses_same_seed(self):
        """build 的 guid 必须等于 identity_seed 的 sha1 前缀（防止两套算法）。"""
        import inspect

        from ankicards import build as build_module

        source = inspect.getsource(build_module)
        self.assertIn("identity_seed(full_name, card)", source)
        self.assertNotIn("json.dumps(card_identity", source)


if __name__ == "__main__":
    unittest.main()

"""视频流量筛选：解析与低播放合并单测"""

import unittest
from datetime import datetime, timedelta

from src.publishing.weixin.channel_post import ChannelPost
from src.publishing.weixin.notification import (
    extract_export_id_from_ref_url,
    parse_optimize_tip_content,
    parse_optimize_tip_item,
)
from src.publishing.weixin.post_list import parse_post_item
from src.publishing.weixin.traffic_filter import (
    REASON_LOW_VIEWS,
    merge_traffic_candidates,
)


class TestFetchPostsEarlyStopLogic(unittest.TestCase):
    """验证 published_after 窗口截断规则（不发起真实网络）。"""

    def test_window_keeps_recent_only(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        cutoff = now - timedelta(hours=24)
        page_posts = [
            ChannelPost("new", "n", now - timedelta(hours=1), 1),
            ChannelPost("old", "o", now - timedelta(hours=40), 2),
        ]
        kept = [p for p in page_posts if p.published_at >= cutoff]
        self.assertEqual([p.post_id for p in kept], ["new"])
        newest = max(p.published_at for p in page_posts)
        self.assertGreaterEqual(newest, cutoff)

    def test_all_old_page_should_stop(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        cutoff = now - timedelta(hours=24)
        page_posts = [
            ChannelPost("a", "a", now - timedelta(hours=30), 1),
            ChannelPost("b", "b", now - timedelta(hours=40), 2),
        ]
        newest = max(p.published_at for p in page_posts)
        self.assertLess(newest, cutoff)


class TestPostListParse(unittest.TestCase):
    def test_parse_post_item_from_har_shape(self):
        item = {
            "exportId": "export/UzFfBgAAxOigeD8kdk-4jMzT4DCa0dlBWBUv6yHyjEAQqV2d3Q",
            "objectId": "export/UzFfBgAAxOigeD8kdk-4jMzT4DCa0dlBWBUv6yHyjEAQqV2d3Q",
            "createTime": 1784368703,
            "readCount": 1,
            "desc": {"description": "#ys点击上方【免费剧集】0元看全集", "mediaType": 4},
        }
        post = parse_post_item(item)
        self.assertIsNotNone(post)
        self.assertEqual(post.post_id, item["exportId"])
        self.assertEqual(post.view_count, 1)
        self.assertIn("免费剧集", post.title)
        self.assertEqual(post.published_at, datetime.fromtimestamp(1784368703))


class TestNotificationParse(unittest.TestCase):
    def test_extract_export_id_from_ref_url(self):
        url = (
            "https://channels.weixin.qq.com/pandora/pages/appeal/index/"
            "?export_id=export/SzFfBgAApl0EPLux9hUXzkMOAtz2JJTZfJ5PmC7V"
            "&unique_id=mmfindermachineauditdelivery14923276624030271850"
            "&appeal_type=6&new=1"
        )
        self.assertEqual(
            extract_export_id_from_ref_url(url),
            "export/SzFfBgAApl0EPLux9hUXzkMOAtz2JJTZfJ5PmC7V",
        )

    def test_parse_optimize_tip_content(self):
        content = (
            "作品标题：#ys点击上方【免费剧集】0……\n"
            "发布时间：2026-05-17 12:46:44\n"
            "存在问题：多次发表情景、文案、元素等近似的同质化内容。\n\n"
            "轻触下方「了解详情」查看详细原因或作品优化建议。"
        )
        title, published_at = parse_optimize_tip_content(content)
        self.assertTrue(title.startswith("#ys点击上方"))
        self.assertEqual(published_at, datetime(2026, 5, 17, 12, 46, 44))

    def test_parse_optimize_tip_item(self):
        item = {
            "title": "作品优化建议",
            "content": (
                "作品标题：测试标题\n"
                "发布时间：2026-05-17 12:46:44\n"
                "存在问题：同质化\n"
            ),
            "refUrl": (
                "https://channels.weixin.qq.com/pandora/pages/appeal/index/"
                "?export_id=export/ABC123&appeal_type=6"
            ),
            "msgid": "14699",
            "isRead": 1,
        }
        notice = parse_optimize_tip_item(item)
        self.assertIsNotNone(notice)
        self.assertEqual(notice.post_id, "export/ABC123")
        self.assertEqual(notice.title, "测试标题")


class TestMergeTrafficCandidates(unittest.TestCase):
    def test_low_views_only(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        posts = [
            ChannelPost(
                post_id="export/low",
                title="低播放",
                published_at=now - timedelta(hours=100),
                view_count=10,
            ),
            ChannelPost(
                post_id="export/hot",
                title="高播放",
                published_at=now - timedelta(hours=100),
                view_count=5000,
            ),
            ChannelPost(
                post_id="export/new",
                title="太新",
                published_at=now - timedelta(hours=1),
                view_count=0,
            ),
        ]
        cands = merge_traffic_candidates(
            posts, grace_period_hours=48, min_views=1000, now=now
        )
        by_id = {c.post_id: c for c in cands}
        self.assertIn("export/low", by_id)
        self.assertEqual(by_id["export/low"].reasons, [REASON_LOW_VIEWS])
        self.assertNotIn("export/hot", by_id)
        self.assertNotIn("export/new", by_id)


if __name__ == "__main__":
    unittest.main()

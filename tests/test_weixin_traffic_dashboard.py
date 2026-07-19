"""概览页流量看板：聚合与描述末段剧集提取单测"""

import unittest
from datetime import datetime, timedelta

from src.publishing.weixin.channel_post import ChannelPost
from src.publishing.weixin.traffic_dashboard import (
    aggregate_account_stats,
    aggregate_drama_stats,
    build_snapshot_from_account_results,
    extract_drama_link_from_description,
    filter_posts_in_window,
)


class TestTrafficDashboardAgg(unittest.TestCase):
    def test_filter_posts_in_window(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        posts = [
            ChannelPost("a", "t1", now - timedelta(hours=1), 10),
            ChannelPost("b", "t2", now - timedelta(hours=30), 20),
        ]
        got = filter_posts_in_window(posts, hours=24, now=now)
        self.assertEqual([p.post_id for p in got], ["a"])

    def test_extract_drama_link_from_description(self):
        self.assertEqual(
            extract_drama_link_from_description("#ys点击上方❤【免费剧集】0元看全集    剧集甲"),
            "剧集甲",
        )
        self.assertEqual(
            extract_drama_link_from_description("其余描述    剧集乙"),
            "剧集乙",
        )
        self.assertEqual(
            extract_drama_link_from_description("只有剧集链接"),
            "只有剧集链接",
        )
        self.assertIsNone(extract_drama_link_from_description("  "))
        self.assertIsNone(extract_drama_link_from_description(None))

    def test_aggregate_and_build_snapshot(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        posts1 = [
            ChannelPost("p1", "#ys点击上方    剧集甲", now - timedelta(hours=1), 80),
            ChannelPost("p2", "另一条    剧集甲", now - timedelta(hours=2), 20),
        ]
        posts2 = [
            ChannelPost("p3", "剧集乙", now - timedelta(hours=3), 200),
            ChannelPost("p4", "#ys只有描述无剧集", now - timedelta(hours=1), 50),
        ]
        acc1 = aggregate_account_stats(1, "账号A", posts1)
        acc2 = aggregate_account_stats(2, "账号B", posts2)
        self.assertEqual(acc1["total_views"], 100)
        self.assertEqual(acc2["max_views"], 200)

        d1 = aggregate_drama_stats(posts1, 1)
        d2 = aggregate_drama_stats(posts2, 2)
        snap = build_snapshot_from_account_results(
            hours=24,
            account_rows=[acc1, acc2],
            drama_partials=[d1, d2],
            errors=[],
            refreshed_at=now,
        )
        self.assertEqual(snap["top_account"]["account_name"], "账号B")
        self.assertEqual(snap["dramas"][0]["drama_link"], "剧集乙")
        self.assertEqual(snap["dramas"][0]["total_views"], 200)
        drama_jia = next(d for d in snap["dramas"] if d["drama_link"] == "剧集甲")
        self.assertEqual(drama_jia["post_count"], 2)
        self.assertEqual(drama_jia["account_count"], 1)
        # 无空白分隔时整段描述会作为末段键
        self.assertTrue(any(d["drama_link"] == "#ys只有描述无剧集" for d in snap["dramas"]))


if __name__ == "__main__":
    unittest.main()

"""概览页流量看板：聚合与剧集匹配单测"""

import unittest
from datetime import datetime, timedelta

from src.publishing.weixin.channel_post import ChannelPost
from src.publishing.weixin.traffic_dashboard import (
    aggregate_account_stats,
    aggregate_drama_stats,
    build_snapshot_from_account_results,
    filter_posts_in_window,
    match_posts_to_drama_tasks,
    normalize_drama_link,
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

    def test_normalize_drama_link(self):
        self.assertEqual(normalize_drama_link("  剧A  "), "剧A")
        self.assertIsNone(normalize_drama_link("  "))
        self.assertIsNone(normalize_drama_link(None))

    def test_match_posts_to_drama_tasks_nearest_one_to_one(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        posts = [
            ChannelPost("p1", "v1", now - timedelta(minutes=10), 100),
            ChannelPost("p2", "v2", now - timedelta(hours=1), 50),
        ]
        tasks = [
            {
                "id": 1,
                "drama_link": "剧集甲",
                "completed_at": (now - timedelta(minutes=5)).isoformat(),
            },
            {
                "id": 2,
                "drama_link": "剧集乙",
                "completed_at": (now - timedelta(hours=1, minutes=5)).isoformat(),
            },
            {
                "id": 3,
                "drama_link": "剧集丙",
                "completed_at": (now - timedelta(hours=10)).isoformat(),
            },
        ]
        mapping = match_posts_to_drama_tasks(posts, tasks)
        self.assertEqual(mapping["p1"], "剧集甲")
        self.assertEqual(mapping["p2"], "剧集乙")
        self.assertNotIn("p3", mapping)

    def test_aggregate_and_build_snapshot(self):
        now = datetime(2026, 7, 19, 12, 0, 0)
        posts1 = [
            ChannelPost("p1", "v1", now - timedelta(hours=1), 80),
            ChannelPost("p2", "v2", now - timedelta(hours=2), 20),
        ]
        posts2 = [
            ChannelPost("p3", "v3", now - timedelta(hours=3), 200),
        ]
        acc1 = aggregate_account_stats(1, "账号A", posts1)
        acc2 = aggregate_account_stats(2, "账号B", posts2)
        self.assertEqual(acc1["total_views"], 100)
        self.assertEqual(acc2["max_views"], 200)

        mapping1 = {"p1": "剧集甲", "p2": "剧集甲"}
        mapping2 = {"p3": "剧集乙"}
        d1 = aggregate_drama_stats(posts1, mapping1, 1)
        d2 = aggregate_drama_stats(posts2, mapping2, 2)
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


if __name__ == "__main__":
    unittest.main()

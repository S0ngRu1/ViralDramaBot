"""
低流量视频清理定时调度
"""

import threading
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .dao import WeixinDAO
from .low_traffic_cleaner import LowTrafficCleaner
from src.core.logger import logger

# 调度器全局 tick 间隔（分钟）：取各账号规则间隔的最小粒度，用于轮询「是否到期」
TICK_INTERVAL_MINUTES = 5


class LowTrafficScheduler:
    """每 TICK_INTERVAL_MINUTES 分钟轮询；各账号按自身 check_interval_minutes 决定是否执行"""

    def __init__(
        self,
        dao: Optional[WeixinDAO] = None,
        cleaner: Optional[LowTrafficCleaner] = None,
    ):
        self.dao = dao or WeixinDAO()
        self.cleaner = cleaner or LowTrafficCleaner(self.dao)
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._lock = threading.Lock()
        self._last_run: dict[int, datetime] = {}

    def start(self, interval_minutes: int = TICK_INTERVAL_MINUTES):
        with self._lock:
            tick = max(5, interval_minutes)
            if self.scheduler.running:
                self.scheduler.reschedule_job(
                    "low_traffic_checker",
                    trigger="interval",
                    minutes=tick,
                )
                return
            self.scheduler.add_job(
                self._tick,
                "interval",
                minutes=tick,
                id="low_traffic_checker",
                replace_existing=True,
                next_run_time=None,
            )
            self.scheduler.start()
            logger.info(
                f"[低流量调度] 已启动，轮询间隔 {tick} 分钟（各账号按规则间隔执行）"
            )

    def stop(self):
        with self._lock:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("[低流量调度] 已停止")

    def _is_due(self, account_id: int, interval_minutes: int) -> bool:
        last = self._last_run.get(account_id)
        if last is None:
            return True
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= max(5, interval_minutes) * 60

    def _tick(self):
        try:
            enabled = self.dao.list_enabled_low_traffic_rules()
            if not enabled:
                return
            due_count = 0
            for rule in enabled:
                account_id = int(rule["account_id"])
                interval = int(rule.get("check_interval_minutes") or 60)
                if not self._is_due(account_id, interval):
                    continue
                due_count += 1
                logger.info(f"[低流量调度] 执行账号 {account_id}（间隔 {interval} 分钟）")
                self.cleaner.run_for_account(account_id)
                self._last_run[account_id] = datetime.now()
            if due_count:
                logger.info(f"[低流量调度] 本轮实际执行 {due_count} 个账号")
        except Exception as e:
            logger.error(f"[低流量调度] 执行异常: {e}")

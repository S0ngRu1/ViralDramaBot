"""
定时调度模块

使用 APScheduler 实现视频定时发布
"""

import threading
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from .config import WeixinConfig
from .dao import WeixinDAO
from .metadata import MetadataResolver
from .schemas import TaskStatus
from .uploader import Uploader
from src.core.logger import logger


class UploadScheduler:
    """上传定时调度器"""

    def __init__(self, dao: Optional[WeixinDAO] = None):
        self.dao = dao or WeixinDAO()
        self.uploader = Uploader(self.dao)
        self.scheduler = BackgroundScheduler(timezone=WeixinConfig.SCHEDULER_TIMEZONE)
        self._lock = threading.Lock()
        self._running_tasks: set = set()  # 正在运行的任务ID

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("定时调度器已启动")
            # 恢复已有的定时计划
            self._restore_schedules()

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("定时调度器已停止")

    def add_schedule(
        self,
        schedule_id: int,
        account_id: int,
        video_paths: list[str],
        cron_expr: Optional[str] = None,
        interval_minutes: Optional[int] = None,
        titles: Optional[list[str]] = None,
        descriptions: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        metadata_source: str = "manual",
    ) -> str:
        """
        添加定时计划

        Returns:
            str: APScheduler job ID
        """
        job_id = f"weixin_schedule_{schedule_id}"

        # 构建上传任务数据
        task_data = {
            "schedule_id": schedule_id,
            "account_id": account_id,
            "video_paths": video_paths,
            "titles": titles,
            "descriptions": descriptions,
            "tags": tags,
            "metadata_source": metadata_source,
            "current_index": 0,
        }

        if cron_expr:
            trigger = CronTrigger.from_crontab(cron_expr)
            logger.info(f"添加 Cron 定时计划: {cron_expr}")
        elif interval_minutes:
            trigger = IntervalTrigger(minutes=interval_minutes)
            logger.info(f"添加间隔定时计划: 每 {interval_minutes} 分钟")
        else:
            logger.error("必须指定 cron_expr 或 interval_minutes")
            return None

        self.scheduler.add_job(
            self._execute_schedule,
            trigger=trigger,
            id=job_id,
            args=[task_data],
            replace_existing=True,
            next_run_time=None,  # 不立即执行，由 cron 控制
        )

        logger.info(f"定时计划已添加: job_id={job_id}")
        return job_id

    def add_one_time_task(
        self,
        task_id: int,
        account_id: int,
        video_path: str,
        scheduled_at: datetime,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata_source: str = "manual",
    ) -> str:
        """
        添加单次定时任务

        Returns:
            str: APScheduler job ID
        """
        job_id = f"weixin_task_{task_id}"

        task_data = {
            "task_id": task_id,
            "account_id": account_id,
            "video_path": video_path,
            "title": title,
            "description": description,
            "tags": tags,
            "metadata_source": metadata_source,
            "scheduled_at": scheduled_at,
        }

        trigger = DateTrigger(run_date=scheduled_at)

        self.scheduler.add_job(
            self._execute_one_time,
            trigger=trigger,
            id=job_id,
            args=[task_data],
            replace_existing=True,
        )

        logger.info(f"单次定时任务已添加: task_id={task_id}, 执行时间={scheduled_at}")
        return job_id

    def remove_job(self, job_id: str):
        """移除定时任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"定时任务已移除: {job_id}")
        except Exception as e:
            logger.warning(f"移除定时任务失败: {e}")

    def get_jobs(self) -> list[dict]:
        """获取所有定时任务"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
            if job.id.startswith("weixin_")
        ]

    def _execute_schedule(self, task_data: dict):
        """执行定时计划中的一个视频"""
        schedule_id = task_data["schedule_id"]
        current_index = task_data.get("current_index", 0)
        video_paths = task_data["video_paths"]

        if current_index >= len(video_paths):
            logger.info(f"定时计划 #{schedule_id} 所有视频已上传完毕")
            self.dao.deactivate_schedule(schedule_id)
            return

        with self._lock:
            if schedule_id in self._running_tasks:
                logger.info(f"定时计划 #{schedule_id} 上一个任务还在运行，跳过本次")
                return
            self._running_tasks.add(schedule_id)

        try:
            video_path = video_paths[current_index]
            title = None
            description = None

            if task_data.get("titles") and current_index < len(task_data["titles"]):
                title = task_data["titles"][current_index]
            if task_data.get("descriptions") and current_index < len(task_data["descriptions"]):
                description = task_data["descriptions"][current_index]

            # 创建上传任务（tags 已下线，固定写 None）
            task_id = self.dao.create_task(
                account_id=task_data["account_id"],
                video_path=video_path,
                title=title,
                description=description,
                tags=None,
                metadata_source=task_data.get("metadata_source", "manual"),
            )

            # 执行上传
            result = self.uploader.upload_video(
                task_id=task_id,
                account_id=task_data["account_id"],
                video_path=video_path,
                title=title,
                description=description,
                metadata_source=task_data.get("metadata_source", "manual"),
            )

            if result["status"] == "success":
                # 更新索引，处理下一个视频
                task_data["current_index"] = current_index + 1
                # 重新注册 job 以更新 task_data
                job_id = f"weixin_schedule_{schedule_id}"
                job = self.scheduler.get_job(job_id)
                if job:
                    job.args = [task_data]
                logger.info(f"定时计划 #{schedule_id} 视频 {current_index + 1}/{len(video_paths)} 上传成功")
            else:
                logger.error(f"定时计划 #{schedule_id} 视频上传失败: {result['message']}")

        except Exception as e:
            logger.error(f"定时计划 #{schedule_id} 执行异常: {e}")
        finally:
            with self._lock:
                self._running_tasks.discard(schedule_id)

    def _execute_one_time(self, task_data: dict):
        """执行单次定时任务"""
        task_id = task_data["task_id"]
        logger.info(f"执行定时任务 #{task_id}")

        try:
            result = self.uploader.upload_video(
                task_id=task_id,
                account_id=task_data["account_id"],
                video_path=task_data["video_path"],
                title=task_data.get("title"),
                description=task_data.get("description"),
                metadata_source=task_data.get("metadata_source", "manual"),
            )

            if result["status"] == "success":
                logger.info(f"定时任务 #{task_id} 执行成功")
            else:
                logger.error(f"定时任务 #{task_id} 执行失败: {result['message']}")

        except Exception as e:
            logger.error(f"定时任务 #{task_id} 执行异常: {e}")

    def _restore_schedules(self):
        """恢复数据库中的定时计划"""
        schedules = self.dao.get_active_schedules()
        for schedule in schedules:
            try:
                self.add_schedule(
                    schedule_id=schedule["id"],
                    account_id=schedule["account_id"],
                    video_paths=schedule["video_paths"],
                    cron_expr=schedule.get("cron_expr"),
                    interval_minutes=schedule.get("interval_minutes"),
                    titles=schedule.get("titles"),
                    descriptions=schedule.get("descriptions"),
                    tags=schedule.get("tags"),
                    metadata_source=schedule.get("metadata_source", "manual"),
                )
                logger.info(f"恢复定时计划: #{schedule['id']}")
            except Exception as e:
                logger.warning(f"恢复定时计划 #{schedule['id']} 失败: {e}")


# 全局调度器实例
upload_scheduler = UploadScheduler()

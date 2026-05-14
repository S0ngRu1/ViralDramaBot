"""
批量上传任务队列

保证每次「批量上传」请求都按提交顺序串行执行：
前一个批量任务完成（所有视频上传完毕）之后，才会开始下一个批量任务。
"""

from __future__ import annotations

import threading
import time
import queue
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from src.core.logger import logger


@dataclass
class BatchJob:
    """单次「批量上传」任务（由前端一次提交产生）"""

    job_id: int
    label: str
    runner: Callable[[], None]
    submitted_at: datetime = field(default_factory=datetime.now)


class BatchUploadQueue:
    """
    单 worker 串行执行批量上传任务。

    - submit(): 入队后立即返回，前端不会被阻塞。
    - worker 线程按 FIFO 顺序执行；前一个批量任务（含其中所有视频）完成后才会取下一个。
    """

    def __init__(self):
        self._queue: "queue.Queue[Optional[BatchJob]]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._next_job_id = 1
        self._stopped = False
        self._current_job: Optional[BatchJob] = None
        self._state_lock = threading.Lock()

    def start(self) -> None:
        """启动单 worker 线程（幂等）"""
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stopped = False
            self._worker = threading.Thread(
                target=self._run,
                name="WeixinBatchUploadWorker",
                daemon=True,
            )
            self._worker.start()
            logger.info("批量上传队列 worker 已启动")

    def stop(self) -> None:
        """通知 worker 停止并退出"""
        with self._lock:
            self._stopped = True
            self._queue.put(None)
        if self._worker:
            self._worker.join(timeout=2)
            self._worker = None

    def submit(self, runner: Callable[[], None], label: str = "") -> dict:
        """
        入队一次批量上传任务。

        Args:
            runner: 真正执行批量上传的可调用对象，应自带异常处理。
            label: 友好描述，用于日志。

        Returns:
            dict: {job_id, queue_position, queued_at}
        """
        self.start()
        with self._lock:
            job_id = self._next_job_id
            self._next_job_id += 1
        job = BatchJob(job_id=job_id, label=label or f"batch#{job_id}", runner=runner)
        self._queue.put(job)
        position = self._queue.qsize()
        logger.info(
            f"批量上传任务已入队：job_id={job_id}, label={job.label!r}, 当前队列长度={position}"
        )
        return {
            "job_id": job_id,
            "queue_position": position,
            "queued_at": job.submitted_at.isoformat(),
        }

    def snapshot(self) -> dict:
        """返回当前队列状态（用于调试 / 任务列表展示）"""
        with self._state_lock:
            current = (
                {
                    "job_id": self._current_job.job_id,
                    "label": self._current_job.label,
                    "started_at": self._current_job.submitted_at.isoformat(),
                }
                if self._current_job
                else None
            )
        return {
            "current": current,
            "pending": self._queue.qsize(),
        }

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                logger.info("批量上传队列 worker 收到停止信号，退出")
                return
            with self._state_lock:
                self._current_job = job
            try:
                logger.info(f"开始执行批量上传任务：job_id={job.job_id}, label={job.label!r}")
                start = time.time()
                job.runner()
                elapsed = time.time() - start
                logger.info(
                    f"批量上传任务已完成：job_id={job.job_id}, label={job.label!r}, 耗时={elapsed:.1f}s"
                )
            except Exception as e:
                logger.error(
                    f"批量上传任务异常：job_id={job.job_id}, label={job.label!r}, error={e}"
                )
            finally:
                with self._state_lock:
                    self._current_job = None
                self._queue.task_done()


batch_upload_queue = BatchUploadQueue()

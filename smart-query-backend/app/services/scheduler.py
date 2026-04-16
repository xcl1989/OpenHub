import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app import database

_scheduler: AsyncIOScheduler | None = None


class TaskScheduler:
    def __init__(self):
        self._scheduler = AsyncIOScheduler(
            job_defaults={"max_instances": 3, "coalesce": True}
        )
        self._initialized = False

    async def start(self):
        tasks = await asyncio.to_thread(database.get_all_enabled_tasks)
        for task in tasks:
            self._add_job(task)
        self._scheduler.start()
        self._initialized = True
        print(f"[Scheduler] 已启动，加载 {len(tasks)} 个定时任务")

    async def shutdown(self):
        if self._initialized:
            self._scheduler.shutdown(wait=False)
            print("[Scheduler] 已关闭")

    def _add_job(self, task: dict):
        try:
            trigger = CronTrigger.from_crontab(task["cron_expression"])
            self._scheduler.add_job(
                _execute_task_wrapper,
                trigger,
                args=[task["id"]],
                id=f"task_{task['id']}",
                replace_existing=True,
            )
        except Exception as e:
            print(f"[Scheduler] 注册任务失败 id={task['id']}: {e}")

    def add_job(self, task: dict):
        if not task.get("enabled"):
            return
        self._add_job(task)

    def remove_job(self, task_id: int):
        try:
            self._scheduler.remove_job(f"task_{task_id}")
        except Exception:
            pass

    def pause_job(self, task_id: int):
        try:
            self._scheduler.pause_job(f"task_{task_id}")
        except Exception:
            pass


async def _execute_task_wrapper(task_id: int):
    from app.services.task_executor import execute_task

    await execute_task(task_id)


_scheduler_instance: TaskScheduler | None = None


def get_scheduler() -> TaskScheduler | None:
    return _scheduler_instance


def create_scheduler() -> TaskScheduler:
    global _scheduler_instance
    _scheduler_instance = TaskScheduler()
    return _scheduler_instance

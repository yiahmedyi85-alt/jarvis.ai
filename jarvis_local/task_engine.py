from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class TaskStep:
    id: str
    title: str
    status: str = "pending"
    result: Any = None
    error: str = ""
    verified: bool = False


@dataclass
class Task:
    id: str
    objective: str
    status: str = "queued"
    current_step: int = -1
    steps: list[TaskStep] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    message: str = ""


class TaskEngine:
    """Small local execution engine used by the API and future adapters.

    Executors must return a mapping with state='completed' or state='failed'.
    A task is never reported completed without a successful executor result.
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def create(self, objective: str, steps: list[str]) -> Task:
        task = Task(str(uuid.uuid4()), objective, steps=[TaskStep(str(uuid.uuid4()), title) for title in steps])
        with self._lock:
            self._tasks[task.id] = task
            self._cancel[task.id] = threading.Event()
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(task) for task in self._tasks.values()]

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            event = self._cancel.get(task_id)
            task = self._tasks.get(task_id)
            if not event or not task:
                return False
            event.set()
            task.status = "cancelled"
            task.message = "Task cancelled by user"
            task.updated_at = datetime.now().isoformat(timespec="seconds")
            return True

    def run(self, task_id: str, executor: Callable[[TaskStep], dict[str, Any]]) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            return {"state": "failed", "message": "Task not found"}
        cancel = self._cancel[task_id]
        task.status = "running"
        for index, step in enumerate(task.steps):
            if cancel.is_set():
                task.status = "cancelled"
                return {"state": "cancelled", "task": asdict(task)}
            task.current_step = index
            step.status = "running"
            task.updated_at = datetime.now().isoformat(timespec="seconds")
            try:
                result = executor(step) or {}
                step.result = result
                step.verified = result.get("state") == "completed" and bool(result.get("verified", True))
                if not step.verified:
                    step.status = "failed"
                    task.status = "failed"
                    task.message = result.get("message", "Step was not verified")
                    return {"state": "failed", "task": asdict(task)}
                step.status = "completed"
            except Exception as exc:
                step.status = "failed"
                step.error = str(exc)
                task.status = "failed"
                task.message = str(exc)
                return {"state": "failed", "task": asdict(task)}
        task.status = "completed"
        task.message = "Task completed and verified"
        task.updated_at = datetime.now().isoformat(timespec="seconds")
        return {"state": "completed", "task": asdict(task), "verified": True}


engine = TaskEngine()

"""
钉钉机器人消息队列管理器
"""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path


class QueueManager:
    def __init__(self, queue_dir: str):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.queue_dir / "tasks.json"
        self.results_file = self.queue_dir / "results.json"
        self._init_files()

    def _init_files(self):
        if not self.tasks_file.exists():
            self._write_json(self.tasks_file, {})
        if not self.results_file.exists():
            self._write_json(self.results_file, {})

    def _read_json(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _write_json(self, path: Path, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_task(
        self,
        user_id: str,
        user_nick: str,
        message: str,
        conv_type: str = "1",
        conv_id: str = "",
        task_data: dict = None,
    ) -> str:
        tasks = self._read_json(self.tasks_file)
        task_id = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
        tasks[task_id] = {
            "id": task_id,
            "user_id": user_id,
            "user_nick": user_nick,
            "message": message,
            "conv_type": conv_type,
            "conv_id": conv_id,
            "status": "pending",
            "result": None,
            "created_at": datetime.now().isoformat(),
        }
        if task_data:
            tasks[task_id].update(task_data)
        self._write_json(self.tasks_file, tasks)
        return task_id

    def get_pending_tasks(self) -> dict:
        tasks = self._read_json(self.tasks_file)
        return {k: v for k, v in tasks.items() if v.get("status") == "pending"}

    def complete_task(self, task_id: str, result: str) -> bool:
        tasks = self._read_json(self.tasks_file)
        if task_id in tasks:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["result"] = result
            tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self._write_json(self.tasks_file, tasks)
            return True
        return False

    def add_result(
        self,
        task_id: str,
        user_id: str,
        response: str,
        conv_id: str = "",
        conv_type: str = "1",
        images=None,
    ):
        results = self._read_json(self.results_file)
        results[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "conv_id": conv_id,
            "conv_type": conv_type,
            "response": response,
            "images": images or [],
            "created_at": datetime.now().isoformat(),
        }
        self._write_json(self.results_file, results)

    def get_pending_results(self) -> dict:
        results = self._read_json(self.results_file)
        return {k: v for k, v in results.items()}

    def clear_result(self, task_id: str):
        results = self._read_json(self.results_file)
        if task_id in results:
            del results[task_id]
            self._write_json(self.results_file, results)


if __name__ == "__main__":
    qm = QueueManager("/tmp/test_queue")
    tid = qm.add_task("test", "测试", "你好")
    print(f"Task: {tid}")
    print(f"Pending: {qm.get_pending_tasks()}")

import uuid
import time
from typing import Dict, List, Optional
from pydantic import BaseModel

class TaskLog(BaseModel):
    timestamp: float
    level: str
    message: str
    screenshot: Optional[str] = None

class AgentTask(BaseModel):
    id: str
    device_id: str
    type: str  # 'chat' or 'background'
    name: str
    role: Optional[str] = None
    details: Optional[str] = None # The goal/instruction
    status: str = "idle" # idle, running, stopped, completed, error
    created_at: float
    logs: List[TaskLog] = []

class TaskManager:
    _instance = None
    
    def __init__(self):
        self.tasks: Dict[str, AgentTask] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_task(self, device_id: str, type: str, name: str, role: str = None, details: str = None, id: str = None) -> AgentTask:
        task_id = id if id else str(uuid.uuid4())
        task = AgentTask(
            id=task_id,
            device_id=device_id,
            type=type,
            name=name,
            role=role,
            details=details,
            created_at=time.time()
        )
        self.tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self.tasks.get(task_id)

    def list_tasks(self, device_id: str) -> List[AgentTask]:
        # Sort by creation time desc
        tasks = [t for t in self.tasks.values() if t.device_id == device_id]
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        return tasks

    def delete_task(self, task_id: str):
        if task_id in self.tasks:
            del self.tasks[task_id]

    def add_log(self, task_id: str, level: str, message: str, screenshot: str = None):
        if task_id in self.tasks:
            self.tasks[task_id].logs.append(TaskLog(
                timestamp=time.time(),
                level=level,
                message=message,
                screenshot=screenshot
            ))

    def update_status(self, task_id: str, status: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = status

    def update_task(self, task_id: str, name: str = None, details: str = None):
        if task_id in self.tasks:
            if name is not None:
                self.tasks[task_id].name = name
            if details is not None:
                self.tasks[task_id].details = details
            return self.tasks[task_id]
        return None

task_manager = TaskManager.get_instance()

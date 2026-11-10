import os
import tomllib

from src.task_config import TaskConfig


class Config:
    def __init__(self, config_path="config/config.toml"):
        self.config_path = config_path
        self.data = self._load_config()
        self._validate()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"在 {self.config_path} 中找不到配置文件。")

        with open(self.config_path, "rb") as f:
            return tomllib.load(f)

    @property
    def global_config(self):
        return self.data.get("global", {})

    @property
    def tasks(self):
        return [TaskConfig.from_dict(t, i) for i, t in enumerate(self.data.get("tasks", []))]

    def _validate(self):
        if "global" not in self.data:
            raise ValueError("配置文件中缺失必要的 [global] 块。")

        if not self.data.get("tasks"):
            raise ValueError("配置文件中没有任何任务。")

        tasks = self.tasks
        if not tasks:
            raise ValueError("配置文件中没有任何有效任务。")

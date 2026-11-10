from dataclasses import dataclass

from src.filter import FileFilter


@dataclass
class TaskConfig:
    name: str
    source_dir: str
    dest_dir: str
    backup_dir: str
    remove_source: bool
    source_expired_minutes: int
    stable_duration: int
    failure_count: int
    fallback_count: int
    ffmpeg_cmd: str
    ffmpeg_cmd_fallback: str
    filter: FileFilter

    @classmethod
    def from_dict(cls, task_dict: dict, index: int = 0):
        task_dict.setdefault("remove_source", False)
        task_dict.setdefault("source_expired_minutes", 0)

        required_keys = ["source_dir", "dest_dir", "ffmpeg_cmd"]

        for key in required_keys:
            if key not in task_dict:
                raise ValueError(f"任务 {index} 中缺失了必要项: {key}")

        task_dict.setdefault("filter", {})
        f_config = task_dict["filter"]

        f_config.setdefault("file_mtime", 0)
        f_config.setdefault("include_patterns", [])
        f_config.setdefault("exclude_patterns", [])
        f_config.setdefault("passthrough_patterns", [])

        task_dict.setdefault("stable_duration", 0)
        task_dict.setdefault("failure_count", 3)
        task_dict.setdefault("fallback_count", 0)
        task_dict.setdefault("ffmpeg_cmd_fallback", "")
        task_dict.setdefault("name", f"Task {index}")

        for key in ("include_patterns", "exclude_patterns", "passthrough_patterns"):
            patterns = f_config[key]
            if not isinstance(patterns, list) or any(not isinstance(p, str) for p in patterns):
                raise ValueError(f"任务 {index} 中 {key} 必须是字符串列表")

        return cls(
            name=task_dict["name"],
            source_dir=task_dict["source_dir"],
            dest_dir=task_dict["dest_dir"],
            backup_dir=task_dict.get("backup_dir", ""),
            remove_source=task_dict["remove_source"],
            source_expired_minutes=task_dict["source_expired_minutes"],
            stable_duration=task_dict["stable_duration"],
            failure_count=task_dict["failure_count"],
            fallback_count=task_dict["fallback_count"],
            ffmpeg_cmd=task_dict["ffmpeg_cmd"],
            ffmpeg_cmd_fallback=task_dict["ffmpeg_cmd_fallback"],
            filter=FileFilter(f_config),
        )

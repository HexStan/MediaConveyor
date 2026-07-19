import os
import time
from dataclasses import dataclass, field

from src.utils import get_media_info


@dataclass
class ScanEntry:
    filepath: str
    action: str
    size: int
    media_info: dict | None = None


@dataclass
class ScanReport:
    entries: list = field(default_factory=list)
    expired_files: list = field(default_factory=list)


class Scanner:
    def __init__(self):
        self._warned_dirs = set()

    def scan(self, task_config, db_manager, logger):
        source_dir = task_config.source_dir
        file_filter = task_config.filter
        failure_count = task_config.failure_count
        remove_source = task_config.remove_source
        source_expired_minutes = task_config.source_expired_minutes

        report = ScanReport()

        if not os.path.exists(source_dir):
            if source_dir not in self._warned_dirs:
                logger.warning(f"目录不存在: {source_dir}")
                self._warned_dirs.add(source_dir)
            return report

        current_time = time.time()
        task_name = task_config.name

        for root, _, files in os.walk(source_dir):
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, source_dir)

                classification = file_filter.classify(rel_path)
                if classification == "skip":
                    logger.debug(
                        f"【{task_name}】跳过 {rel_path}，原因: 文件名不匹配过滤规则"
                    )
                    continue

                logger.debug(f"【{task_name}】扫描到文件: {rel_path}")

                success_time = db_manager.get_success_time(filepath)
                if success_time is not None:
                    if remove_source and source_expired_minutes > 0:
                        if current_time - success_time >= source_expired_minutes * 60:
                            report.expired_files.append(filepath)
                    logger.debug(
                        f"【{task_name}】跳过 {rel_path}，原因: 文件已成功处理过"
                    )
                    continue

                failures = db_manager.get_failure_count(filepath)
                if failures >= failure_count:
                    logger.debug(
                        f"【{task_name}】跳过 {rel_path}，原因: 失败次数 ({failures}) 已达到上限 ({failure_count})"
                    )
                    continue

                try:
                    stat = os.stat(filepath)
                    file_mtime = stat.st_mtime

                    if not file_filter.check_mtime(file_mtime, current_time):
                        logger.debug(
                            f"【{task_name}】跳过 {rel_path}，原因: 文件修改时间未满 {file_filter.file_mtime} 秒 (mtime={file_mtime}, now={current_time})"
                        )
                        continue

                    media_info = None

                    if classification != "passthrough":
                        if file_filter.requires_media_info():
                            logger.debug(f"【{task_name}】正在获取媒体信息: {rel_path}")
                            media_info = get_media_info(filepath)
                            media_info["size"] = stat.st_size
                        else:
                            media_info = {"size": stat.st_size}

                        if not file_filter.match(
                            media_info, logger, rel_path, task_name
                        ):
                            continue

                    entry = ScanEntry(
                        filepath=filepath,
                        action=classification,
                        size=stat.st_size,
                        media_info=media_info,
                    )
                    report.entries.append(entry)
                    logger.info(
                        f"【{task_name}】在 {source_dir} 中监测到新文件: {rel_path}"
                    )
                    logger.debug(
                        f"【{task_name}】{rel_path} 进入处理队列 (动作: {classification})"
                    )
                except OSError as e:
                    logger.error(f"读取文件失败: {filepath}\n{e}")

        return report

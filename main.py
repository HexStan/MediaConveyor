import sys
import time

from src.config import Config
from src.db_manager import DBManager
from src.logger import setup_logger
from src.processor import cleanup_expired_files, process_file
from src.scanner import Scanner

try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

LOCK_FILE = "/tmp/media_conveyor.lock"


def acquire_lock():
    if not HAS_FCNTL:
        print(
            "Warning: fcntl module not found. File locking is only supported on Linux/Unix."
        )
        return None

    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except IOError:
        print("另一个实例正在运行，已退出。")
        sys.exit(1)


def run_task(
    task_config, scanner, db_manager, logger, scan_interval, monitoring_logged
):
    report = scanner.scan(task_config, db_manager, logger)

    if report.expired_files:
        cleanup_expired_files(report.expired_files, db_manager, logger)

    task_name = task_config.name
    source_dir = task_config.source_dir

    if not report.entries:
        if task_name not in monitoring_logged:
            logger.info(
                f"【{task_name}】正在以 {scan_interval} 秒的间隔持续监听 {source_dir}"
            )
            monitoring_logged.add(task_name)
        return False

    monitoring_logged.discard(task_name)

    for entry in report.entries:
        process_file(entry, task_config, db_manager, logger)

    return True


def main():
    _lock_fd = acquire_lock()

    try:
        config = Config()
    except Exception as e:
        print(f"加载配置失败，原因:\n{e}")
        sys.exit(1)

    global_cfg = config.global_config

    log_dir = global_cfg.get("log_dir", "logs")
    log_level = global_cfg.get("log_level", "INFO")
    logger = setup_logger(
        log_dir=log_dir,
        max_log_files=global_cfg.get("max_log_files", 7),
        log_level=log_level,
    )

    db_manager = DBManager()
    scanner = Scanner()
    tasks = config.tasks

    logger.info("MediaConveyor 已启动。")

    scan_interval = global_cfg.get("scan_interval", 0)
    monitoring_logged = set()

    if scan_interval == 0:
        logger.info("全局扫描间隔为 0，作为一次性任务执行。")
        for task_config in tasks:
            run_task(
                task_config,
                scanner,
                db_manager,
                logger,
                scan_interval,
                monitoring_logged,
            )
        logger.info("所有任务完成。")
    else:
        logger.info("MediaConveyor 已进入监听模式。")
        try:
            while True:
                for task_config in tasks:
                    run_task(
                        task_config,
                        scanner,
                        db_manager,
                        logger,
                        scan_interval,
                        monitoring_logged,
                    )
                time.sleep(scan_interval)
        except KeyboardInterrupt:
            logger.info("MediaConveyor 接收到退出信号，正在退出……")


if __name__ == "__main__":
    main()

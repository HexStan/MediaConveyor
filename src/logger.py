import glob
import logging
import os
from datetime import datetime


class DailyRotatingFileHandler(logging.FileHandler):
    """
    按天滚动的日志处理器，每天生成一个新的日志文件，并清理旧日志。
    """

    def __init__(self, log_dir, max_log_files, encoding="utf-8"):
        self.log_dir = log_dir
        self.max_log_files = max_log_files
        self.current_date = datetime.now().strftime("%Y%m%d")
        filename = os.path.join(log_dir, f"mediaconveyor-{self.current_date}.log")
        super().__init__(filename, encoding=encoding)

    def emit(self, record):
        new_date = datetime.now().strftime("%Y%m%d")
        if new_date != self.current_date:
            self.current_date = new_date
            self.close()
            filename = os.path.join(
                self.log_dir, f"mediaconveyor-{self.current_date}.log"
            )
            self.baseFilename = os.path.abspath(filename)
            self.stream = self._open()

            # 日期变化时，执行旧日志清理
            if self.max_log_files > 0:
                _cleanup_old_logs(self.log_dir, self.max_log_files)

        super().emit(record)


def setup_logger(log_dir="logs", max_log_files=7, log_level="INFO"):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger("MediaConveyor")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 避免重复添加 handler
    if not logger.handlers:
        # 文件输出
        fh = DailyRotatingFileHandler(log_dir, max_log_files, encoding="utf-8")
        fh.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # 控制台输出
        ch = logging.StreamHandler()
        ch.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # 格式化
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    # 清理旧日志文件
    _cleanup_old_logs(log_dir, max_log_files)

    return logger


def _cleanup_old_logs(log_dir, max_log_files):
    try:
        log_files = glob.glob(os.path.join(log_dir, "mediaconveyor-*.log"))

        # 提取文件名中的日期并排序
        def get_date_from_filename(filepath):
            filename = os.path.basename(filepath)
            # 假设文件名格式为 mediaconveyor-YYYYMMDD.log
            try:
                date_str = filename.replace("mediaconveyor-", "").replace(".log", "")
                return datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                # 如果解析失败，返回一个很早的时间
                return datetime.min

        # 按日期排序，最旧的在前面
        log_files.sort(key=get_date_from_filename)

        while len(log_files) > max_log_files:
            oldest_file = log_files.pop(0)
            try:
                os.remove(oldest_file)
            except OSError:
                pass
    except Exception:
        pass

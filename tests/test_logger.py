import glob
import logging
import os
from datetime import datetime, timedelta
from unittest.mock import patch

from src.logger import (
    DailyRotatingFileHandler,
    _cleanup_old_logs,
    setup_logger,
)


class TestDailyRotatingFileHandler:
    def test_init_creates_handler(self, temp_dir):
        handler = DailyRotatingFileHandler(temp_dir, 7)
        today = datetime.now().strftime("%Y%m%d")
        # expected_filename = os.path.join(temp_dir, f"mediaconveyor-{today}.log")
        assert handler.current_date == today
        assert handler.max_log_files == 7
        handler.close()

    def test_emit_same_day_no_rotation(self, temp_dir):
        handler = DailyRotatingFileHandler(temp_dir, 7)
        original_filename = handler.baseFilename
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test message", (), None
        )
        handler.emit(record)
        assert handler.baseFilename == original_filename
        handler.close()

    def test_emit_date_change_triggers_rotation(self, temp_dir):
        handler = DailyRotatingFileHandler(temp_dir, 7)
        today = datetime.now().strftime("%Y%m%d")

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        yesterday_file = os.path.join(temp_dir, f"mediaconveyor-{yesterday}.log")
        with open(yesterday_file, "w") as f:
            f.write("old log")

        handler.current_date = yesterday
        handler.baseFilename = yesterday_file

        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test message", (), None
        )
        handler.emit(record)
        assert handler.current_date == today
        handler.close()

    def test_cleanup_triggered_on_rotation(self, temp_dir):
        handler = DailyRotatingFileHandler(temp_dir, 2)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        yesterday_file = os.path.join(temp_dir, f"mediaconveyor-{yesterday}.log")
        with open(yesterday_file, "w") as f:
            f.write("old log")

        handler.current_date = yesterday
        handler.baseFilename = yesterday_file

        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "test message", (), None
        )
        handler.emit(record)
        handler.close()


class TestSetupLogger:
    def test_creates_log_dir(self, temp_dir):
        log_dir = os.path.join(temp_dir, "custom_logs")
        logger = setup_logger(log_dir, 7, "INFO")
        assert os.path.exists(log_dir)
        for handler in logger.handlers:
            handler.close()

    def test_returns_logger_instance(self, temp_dir):
        logger = setup_logger(temp_dir, 7, "INFO")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "MediaConveyor"
        for handler in logger.handlers:
            handler.close()

    def test_sets_log_level(self, temp_dir):
        logger = setup_logger(temp_dir, 7, "DEBUG")
        assert logger.level == logging.DEBUG
        for handler in logger.handlers:
            handler.close()

    def test_invalid_log_level_falls_back_to_info(self, temp_dir):
        logger = setup_logger(temp_dir, 7, "INVALID_LEVEL")
        assert logger.level == logging.INFO
        for handler in logger.handlers:
            handler.close()

    def test_no_duplicate_handlers(self, temp_dir):
        logger1 = setup_logger(temp_dir, 7, "INFO")
        initial_handler_count = len(logger1.handlers)
        logger2 = setup_logger(temp_dir, 7, "INFO")
        assert len(logger2.handlers) == initial_handler_count
        for handler in logger2.handlers:
            handler.close()

    def test_file_and_console_handlers(self, temp_dir):
        logger = setup_logger(temp_dir, 7, "INFO")
        handler_types = [type(h) for h in logger.handlers]
        assert DailyRotatingFileHandler in handler_types
        assert logging.StreamHandler in handler_types or any(
            issubclass(t, logging.StreamHandler) for t in handler_types
        )
        for handler in logger.handlers:
            handler.close()


class TestCleanupOldLogs:
    def test_no_logs_no_error(self, temp_dir):
        _cleanup_old_logs(temp_dir, 7)

    def test_keeps_within_limit(self, temp_dir):
        for i in range(5):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            path = os.path.join(temp_dir, f"mediaconveyor-{date}.log")
            with open(path, "w") as f:
                f.write("log")

        _cleanup_old_logs(temp_dir, 3)

        log_files = glob.glob(os.path.join(temp_dir, "mediaconveyor-*.log"))
        assert len(log_files) <= 3

    def test_removes_oldest_first(self, temp_dir):
        dates = []
        for i in range(5):
            date = (datetime.now() - timedelta(days=5 - i)).strftime("%Y%m%d")
            dates.append(date)
            path = os.path.join(temp_dir, f"mediaconveyor-{date}.log")
            with open(path, "w") as f:
                f.write("log")

        _cleanup_old_logs(temp_dir, 2)

        log_files = glob.glob(os.path.join(temp_dir, "mediaconveyor-*.log"))
        assert len(log_files) == 2
        remaining_dates = [
            os.path.basename(f).replace("mediaconveyor-", "").replace(".log", "")
            for f in log_files
        ]
        assert dates[-1] in remaining_dates
        assert dates[-2] in remaining_dates

    def test_exactly_at_limit_no_deletion(self, temp_dir):
        for i in range(3):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            path = os.path.join(temp_dir, f"mediaconveyor-{date}.log")
            with open(path, "w") as f:
                f.write("log")

        _cleanup_old_logs(temp_dir, 3)

        log_files = glob.glob(os.path.join(temp_dir, "mediaconveyor-*.log"))
        assert len(log_files) == 3

    def test_max_zero_deletes_all(self, temp_dir):
        for i in range(3):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            path = os.path.join(temp_dir, f"mediaconveyor-{date}.log")
            with open(path, "w") as f:
                f.write("log")

        _cleanup_old_logs(temp_dir, 0)

        log_files = glob.glob(os.path.join(temp_dir, "mediaconveyor-*.log"))
        assert len(log_files) == 0

    def test_invalid_filename_handled_gracefully(self, temp_dir):
        valid_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        with open(os.path.join(temp_dir, f"mediaconveyor-{valid_date}.log"), "w") as f:
            f.write("log")
        with open(os.path.join(temp_dir, "mediaconveyor-invalid-date.log"), "w") as f:
            f.write("log")

        _cleanup_old_logs(temp_dir, 3)

    def test_oserror_during_removal_handled(self, temp_dir):
        for i in range(5):
            date = (datetime.now() - timedelta(days=5 - i)).strftime("%Y%m%d")
            path = os.path.join(temp_dir, f"mediaconveyor-{date}.log")
            with open(path, "w") as f:
                f.write("log")

        with patch("os.remove", side_effect=[OSError, None, None]):
            _cleanup_old_logs(temp_dir, 2)

    def test_exception_caught(self, temp_dir):
        with patch("glob.glob", side_effect=Exception("glob failed")):
            _cleanup_old_logs(temp_dir, 7)

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.scanner import ScanEntry, ScanReport, Scanner
from src.task_config import TaskConfig


def _make_basic_task_config(source_dir, filter_config=None):
    return TaskConfig(
        name="Test Task",
        source_dir=source_dir,
        dest_dir="./dest",
        backup_dir="./backup",
        remove_source=False,
        source_expired_minutes=0,
        stable_duration=0,
        failure_count=3,
        fallback_count=0,
        ffmpeg_cmd="ffmpeg -i {input} {output}.mp4",
        ffmpeg_cmd_fallback="",
        filter=MagicMock() if filter_config is None else filter_config,
    )


class TestScanEntry:
    def test_create_scan_entry(self):
        entry = ScanEntry(filepath="/test/file.mp4", action="process", size=1024)
        assert entry.filepath == "/test/file.mp4"
        assert entry.action == "process"
        assert entry.size == 1024
        assert entry.media_info is None

    def test_create_scan_entry_with_media_info(self):
        mi = {"duration": 120.0, "size": 1024}
        entry = ScanEntry(
            filepath="/test/file.mp4", action="process", size=1024, media_info=mi
        )
        assert entry.media_info == mi


class TestScanReport:
    def test_default_init(self):
        report = ScanReport()
        assert report.entries == []
        assert report.expired_files == []


class TestScanner:
    @pytest.fixture
    def scanner(self):
        return Scanner()

    def test_nonexistent_directory_warns_once(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({})
        tc = _make_basic_task_config(
            os.path.join(temp_dir, "nonexistent"), filter_config=ff
        )
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        report = scanner.scan(tc, sm, mock_logger)
        assert report.entries == []
        assert report.expired_files == []
        mock_logger.warning.assert_called_once()

        report2 = scanner.scan(tc, sm, mock_logger)
        assert report2.entries == []
        mock_logger.warning.assert_called_once()

    def test_empty_directory(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({})
        source = os.path.join(temp_dir, "source")
        os.makedirs(source)
        tc = _make_basic_task_config(source, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        report = scanner.scan(tc, sm, mock_logger)
        assert report.entries == []

    def test_file_skipped(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        with open(os.path.join(temp_dir, "test.avi"), "w") as f:
            f.write("data")

        report = scanner.scan(tc, sm, mock_logger)
        assert report.entries == []

    def test_already_processed_skipped(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("data")
        sm.mark_success(filepath, time.time())

        report = scanner.scan(tc, sm, mock_logger)
        assert report.entries == []

    def test_expired_file_added_to_report(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        tc.remove_source = True
        tc.source_expired_minutes = 1
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("data")
        sm.mark_success(filepath, time.time() - 120)

        report = scanner.scan(tc, sm, mock_logger)
        assert filepath in report.expired_files

    def test_not_yet_expired_not_added(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        tc.remove_source = True
        tc.source_expired_minutes = 60
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("data")
        sm.mark_success(filepath, time.time())

        report = scanner.scan(tc, sm, mock_logger)
        assert filepath not in report.expired_files
        assert len(report.entries) == 0

    def test_failures_exceeded_skipped(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("data")
        for _ in range(3):
            sm.increment_failure(filepath)

        report = scanner.scan(tc, sm, mock_logger)
        assert report.entries == []

    def test_mtime_too_recent_skipped(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"], "file_mtime": 60})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("data")

        with patch("time.time", return_value=os.path.getmtime(filepath) + 30):
            report = scanner.scan(tc, sm, mock_logger)
            assert report.entries == []

    def test_filter_match_failure_skipped(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"], "size": {"min": "1GB"}})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("small")

        report = scanner.scan(tc, sm, mock_logger)
        assert report.entries == []

    def test_successful_file_adds_entry(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1024)

        report = scanner.scan(tc, sm, mock_logger)
        assert len(report.entries) == 1
        assert report.entries[0].filepath == filepath
        assert report.entries[0].action == "process"
        assert report.entries[0].size == 1024

    def test_passthrough_adds_entry(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter(
            {
                "include_patterns": ["*.mp4", "*.txt"],
                "passthrough_patterns": ["*.txt"],
            }
        )
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.txt")
        with open(filepath, "w") as f:
            f.write("text")

        report = scanner.scan(tc, sm, mock_logger)
        assert len(report.entries) == 1
        assert report.entries[0].action == "passthrough"

    def test_oserror_during_stat_handled(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("data")

        original_stat = os.stat
        call_count = [0]

        def mock_stat(path):
            call_count[0] += 1
            if path == filepath:
                raise OSError("stat failed")
            return original_stat(path)

        with patch("os.stat", side_effect=mock_stat):
            report = scanner.scan(tc, sm, mock_logger)
            assert report.entries == []
            mock_logger.error.assert_called()

    def test_subdirectory_recursion(self, scanner, mock_logger, temp_dir):
        from src.filter import FileFilter

        ff = FileFilter({"include_patterns": ["*.mp4"]})
        tc = _make_basic_task_config(temp_dir, filter_config=ff)
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        sub = os.path.join(temp_dir, "subdir")
        os.makedirs(sub)
        with open(os.path.join(sub, "test.mp4"), "w") as f:
            f.write("d" * 100)

        report = scanner.scan(tc, sm, mock_logger)
        assert len(report.entries) == 1
        assert report.entries[0].filepath == os.path.join(sub, "test.mp4")

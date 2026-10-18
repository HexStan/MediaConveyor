import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.processor import cleanup_expired_files, process_file
from src.scanner import ScanEntry
from src.task_config import TaskConfig


def _make_task_config(**overrides):
    defaults = {
        "name": "Test Task",
        "source_dir": "./source",
        "dest_dir": "./dest",
        "backup_dir": "./backup",
        "remove_source": False,
        "source_expired_minutes": 0,
        "stable_duration": 0,
        "failure_count": 3,
        "fallback_count": 0,
        "ffmpeg_cmd": "ffmpeg -i {input} {output}.mp4",
        "ffmpeg_cmd_fallback": "",
        "filter": MagicMock(),
    }
    defaults.update(overrides)
    return TaskConfig(**defaults)


class TestCleanupExpiredFiles:
    def test_deletes_file_and_removes_record(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))
        filepath = os.path.join(temp_dir, "expired.mp4")
        with open(filepath, "w") as f:
            f.write("data")
        sm.mark_success(filepath, time.time())

        cleanup_expired_files([filepath], sm, mock_logger)
        assert not os.path.exists(filepath)
        assert sm.get_success_time(filepath) is None

    def test_handles_oserror(self, mock_logger):

        sm = MagicMock()
        with patch("os.remove", side_effect=OSError("permission denied")):
            cleanup_expired_files(["/fake/file.mp4"], sm, mock_logger)
            mock_logger.error.assert_called()

    def test_handles_empty_list(self, mock_logger):
        sm = MagicMock()
        cleanup_expired_files([], sm, mock_logger)
        sm.delete_record.assert_not_called()


class TestProcessFileStabilityCheck:
    @pytest.fixture
    def mock_state(self, temp_dir):
        from src.db_manager import DBManager

        return DBManager(os.path.join(temp_dir, "state.json"))

    def test_stability_check_passes_when_size_unchanged(
        self, temp_dir, mock_logger, mock_state
    ):
        filepath = os.path.join(temp_dir, "stable.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=temp_dir,
            dest_dir=os.path.join(temp_dir, "dest"),
            backup_dir=os.path.join(temp_dir, "backup"),
            stable_duration=0.01,
        )

        entry = ScanEntry(filepath=filepath, action="passthrough", size=1000)

        with patch("shutil.move") as mock_move:
            process_file(entry, tc, mock_state, mock_logger)
            mock_move.assert_called_once()

    def test_stability_check_fails_when_size_changed(
        self, temp_dir, mock_logger, mock_state
    ):
        filepath = os.path.join(temp_dir, "changing.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=temp_dir,
            dest_dir=os.path.join(temp_dir, "dest"),
            backup_dir=os.path.join(temp_dir, "backup"),
            stable_duration=0.01,
        )

        entry = ScanEntry(filepath=filepath, action="process", size=1000)

        sizes = [1000, 2000]

        def mock_getsize(path):
            return sizes.pop(0)

        with patch("os.path.getsize", side_effect=mock_getsize):
            process_file(entry, tc, mock_state, mock_logger)

    def test_stability_check_file_missing_before(
        self, temp_dir, mock_logger, mock_state
    ):
        tc = _make_task_config(
            source_dir=temp_dir,
            dest_dir=os.path.join(temp_dir, "dest"),
            backup_dir=os.path.join(temp_dir, "backup"),
            stable_duration=0.01,
        )

        entry = ScanEntry(
            filepath=os.path.join(temp_dir, "gone.mp4"), action="process", size=1000
        )
        process_file(entry, tc, mock_state, mock_logger)

    def test_stability_check_file_missing_after(
        self, temp_dir, mock_logger, mock_state
    ):
        filepath = os.path.join(temp_dir, "temp.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=temp_dir,
            dest_dir=os.path.join(temp_dir, "dest"),
            backup_dir=os.path.join(temp_dir, "backup"),
            stable_duration=0.01,
        )

        entry = ScanEntry(filepath=filepath, action="process", size=1000)

        call_count = [0]

        def mock_getsize(path):
            call_count[0] += 1
            if call_count[0] == 1:
                return 1000
            raise OSError("file gone")

        with patch("os.path.getsize", side_effect=mock_getsize):
            process_file(entry, tc, mock_state, mock_logger)


class TestProcessFilePassthrough:
    def test_passthrough_success(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)

        filepath = os.path.join(src_dir, "test.txt")
        with open(filepath, "w") as f:
            f.write("content")

        tc = _make_task_config(
            source_dir=src_dir,
            dest_dir=dst_dir,
            backup_dir=os.path.join(temp_dir, "backup"),
        )
        entry = ScanEntry(filepath=filepath, action="passthrough", size=7)

        process_file(entry, tc, sm, mock_logger)
        assert not os.path.exists(filepath)
        assert os.path.exists(os.path.join(dst_dir, "test.txt"))

    def test_passthrough_failure(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        filepath = os.path.join(temp_dir, "test.txt")
        with open(filepath, "w") as f:
            f.write("content")

        tc = _make_task_config(source_dir=temp_dir)
        entry = ScanEntry(filepath=filepath, action="passthrough", size=7)

        with patch("shutil.move", side_effect=Exception("move failed")):
            process_file(entry, tc, sm, mock_logger)
            assert sm.get_failure_count(filepath) == 1


class TestProcessFileFfmpegProcessing:
    def test_ffmpeg_success(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        bak_dir = os.path.join(temp_dir, "backup")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        os.makedirs(bak_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(source_dir=src_dir, dest_dir=dst_dir, backup_dir=bak_dir)
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = b""
        mock_process.poll.return_value = 0

        with patch("subprocess.Popen", return_value=mock_process):
            process_file(entry, tc, sm, mock_logger)

        assert not os.path.exists(filepath)
        assert os.path.exists(os.path.join(bak_dir, "test.mp4"))

    def test_ffmpeg_failure_increments_failures(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        bak_dir = os.path.join(temp_dir, "backup")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        os.makedirs(bak_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(source_dir=src_dir, dest_dir=dst_dir, backup_dir=bak_dir)
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.side_effect = [b"time=00:00:01\r\n", b"", b""]
        mock_process.poll.side_effect = [None, 1]

        with patch("subprocess.Popen", return_value=mock_process):
            process_file(entry, tc, sm, mock_logger)

        assert sm.get_failure_count(filepath) == 1

    def test_ffmpeg_fallback_used(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        bak_dir = os.path.join(temp_dir, "backup")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        os.makedirs(bak_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=src_dir,
            dest_dir=dst_dir,
            backup_dir=bak_dir,
            fallback_count=2,
            ffmpeg_cmd_fallback="fallback_cmd {input} {output}",
        )
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        sm.increment_ffmpeg_failure(filepath)
        sm.increment_ffmpeg_failure(filepath)

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = b""
        mock_process.poll.return_value = 0

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_process
            process_file(entry, tc, sm, mock_logger)
            args, _kwargs = mock_popen.call_args
            assert "fallback_cmd" in args[0]

    def test_ffmpeg_exception_increments_failure(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        bak_dir = os.path.join(temp_dir, "backup")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        os.makedirs(bak_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(source_dir=src_dir, dest_dir=dst_dir, backup_dir=bak_dir)
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        with patch("subprocess.Popen", side_effect=Exception("command not found")):
            process_file(entry, tc, sm, mock_logger)

        assert sm.get_failure_count(filepath) == 1

    def test_remove_source_immediate_delete(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=src_dir,
            dest_dir=dst_dir,
            backup_dir=os.path.join(temp_dir, "backup"),
            remove_source=True,
        )
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = b""
        mock_process.poll.return_value = 0

        with patch("subprocess.Popen", return_value=mock_process):
            process_file(entry, tc, sm, mock_logger)

        assert not os.path.exists(filepath)

    def test_remove_source_delayed(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=src_dir,
            dest_dir=dst_dir,
            backup_dir=os.path.join(temp_dir, "backup"),
            remove_source=True,
            source_expired_minutes=60,
        )
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = b""
        mock_process.poll.return_value = 0

        with patch("subprocess.Popen", return_value=mock_process):
            process_file(entry, tc, sm, mock_logger)

        assert os.path.exists(filepath)
        assert sm.get_success_time(filepath) is not None

    def test_partial_output_cleanup_on_failure(self, temp_dir, mock_logger):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        bak_dir = os.path.join(temp_dir, "backup")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        os.makedirs(bak_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(source_dir=src_dir, dest_dir=dst_dir, backup_dir=bak_dir)
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        partial_file1 = os.path.join(dst_dir, "test-encoded.mp4")
        partial_file2 = os.path.join(dst_dir, "test.log")
        other_file = os.path.join(dst_dir, "other-encoded.mp4")

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.side_effect = [b"time=00:00:01\r\n", b"", b""]
        mock_process.poll.side_effect = [None, 1]

        def create_partial_outputs(*args, **kwargs):
            with open(partial_file1, "w") as f:
                f.write("partial")
            with open(partial_file2, "w") as f:
                f.write("log")
            with open(other_file, "w") as f:
                f.write("other")
            return mock_process

        with patch("subprocess.Popen", side_effect=create_partial_outputs):
            process_file(entry, tc, sm, mock_logger)

        assert not os.path.exists(partial_file1)
        assert not os.path.exists(partial_file2)
        assert os.path.exists(other_file)
        assert sm.get_failure_count(filepath) == 1

    def test_remove_source_false_no_backup_dir_keeps_file_in_place(
        self, temp_dir, mock_logger
    ):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=src_dir,
            dest_dir=dst_dir,
            backup_dir="",
            remove_source=False,
        )
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.return_value = b""
        mock_process.poll.return_value = 0

        with patch("subprocess.Popen", return_value=mock_process):
            process_file(entry, tc, sm, mock_logger)

        assert os.path.exists(filepath)
        assert sm.get_success_time(filepath) is not None

    def test_ffmpeg_fallback_failure_increments_normal_failure(
        self, temp_dir, mock_logger
    ):
        from src.db_manager import DBManager

        sm = DBManager(os.path.join(temp_dir, "state.json"))

        src_dir = os.path.join(temp_dir, "source")
        dst_dir = os.path.join(temp_dir, "dest")
        bak_dir = os.path.join(temp_dir, "backup")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        os.makedirs(bak_dir)

        filepath = os.path.join(src_dir, "test.mp4")
        with open(filepath, "w") as f:
            f.write("d" * 1000)

        tc = _make_task_config(
            source_dir=src_dir,
            dest_dir=dst_dir,
            backup_dir=bak_dir,
            fallback_count=1,
            ffmpeg_cmd_fallback="fallback_cmd {input} {output}",
        )
        entry = ScanEntry(
            filepath=filepath,
            action="process",
            size=1000,
            media_info={"duration": 30.0, "size": 1000},
        )

        sm.increment_ffmpeg_failure(filepath)

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = MagicMock()
        mock_process.stderr.read.side_effect = [b"time=00:00:01\r\n", b"", b""]
        mock_process.poll.side_effect = [None, 1]

        with patch("subprocess.Popen", return_value=mock_process):
            process_file(entry, tc, sm, mock_logger)

        assert sm.get_failure_count(filepath) == 1

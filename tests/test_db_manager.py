import os
import time

from src.db_manager import DBManager


class TestDBManagerInit:
    def test_default_path_creates_db(self, temp_dir):
        db_path = os.path.join(temp_dir, "media-conveyor.db")
        DBManager(db_path)
        assert os.path.exists(db_path)

    def test_loads_existing_db(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        assert sm.get_failure_count("/test/file1.mp4") == 2
        assert sm.get_ffmpeg_failure_count("/test/file1.mp4") == 1
        assert sm.get_success_time("/test/file2.mp4") == 1234567890.0

    def test_creates_parent_dirs(self, temp_dir):
        deep_path = os.path.join(temp_dir, "deep", "nested", "media-conveyor.db")
        DBManager(deep_path)
        assert os.path.exists(deep_path)


class TestDBManagerGetVersion:
    def test_new_db_auto_detects_version(self, sample_db):
        sm = DBManager(sample_db)
        assert sm.get_version() >= 1

    def test_set_and_get_version(self, sample_db):
        sm = DBManager(sample_db)
        sm.set_version(5)
        assert sm.get_version() == 5

    def test_version_persists(self, sample_db):
        sm = DBManager(sample_db)
        sm.set_version(5)
        sm2 = DBManager(sample_db)
        assert sm2.get_version() == 5


class TestDBManagerGetFailureCount:
    def test_new_file_returns_zero(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        assert sm.get_failure_count("/new/file.mp4") == 0

    def test_existing_file_returns_count(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        assert sm.get_failure_count("/test/file1.mp4") == 2

    def test_empty_db_returns_zero(self, sample_db):
        sm = DBManager(sample_db)
        assert sm.get_failure_count("/test/file.mp4") == 0


class TestDBManagerGetFfmpegFailureCount:
    def test_new_file_returns_zero(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        assert sm.get_ffmpeg_failure_count("/new/file.mp4") == 0

    def test_existing_file_returns_count(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        assert sm.get_ffmpeg_failure_count("/test/file1.mp4") == 1


class TestDBManagerIncrementFailure:
    def test_first_failure_increments(self, sample_db):
        sm = DBManager(sample_db)
        sm.increment_failure("/test/file.mp4")
        assert sm.get_failure_count("/test/file.mp4") == 1

    def test_subsequent_failures_increment(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        sm.increment_failure("/test/file1.mp4")
        assert sm.get_failure_count("/test/file1.mp4") == 3

    def test_persists_to_disk(self, sample_db):
        sm = DBManager(sample_db)
        sm.increment_failure("/test/file.mp4")
        sm2 = DBManager(sample_db)
        assert sm2.get_failure_count("/test/file.mp4") == 1


class TestDBManagerIncrementFfmpegFailure:
    def test_first_ffmpeg_failure(self, sample_db):
        sm = DBManager(sample_db)
        sm.increment_ffmpeg_failure("/test/file.mp4")
        assert sm.get_ffmpeg_failure_count("/test/file.mp4") == 1

    def test_subsequent_ffmpeg_failures(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        sm.increment_ffmpeg_failure("/test/file1.mp4")
        assert sm.get_ffmpeg_failure_count("/test/file1.mp4") == 2


class TestDBManagerMarkSuccess:
    def test_sets_success_time(self, sample_db):
        sm = DBManager(sample_db)
        ts = time.time()
        sm.mark_success("/test/file.mp4", ts)
        assert sm.get_success_time("/test/file.mp4") == ts

    def test_clears_failures(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        sm.mark_success("/test/file1.mp4", 999.0)
        assert sm.get_failure_count("/test/file1.mp4") == 0
        assert sm.get_ffmpeg_failure_count("/test/file1.mp4") == 0

    def test_persists_mark(self, sample_db):
        sm = DBManager(sample_db)
        sm.mark_success("/test/file.mp4", 1234567890.0)
        sm2 = DBManager(sample_db)
        assert sm2.get_success_time("/test/file.mp4") == 1234567890.0


class TestDBManagerGetSuccessTime:
    def test_new_file_returns_none(self, sample_db):
        sm = DBManager(sample_db)
        assert sm.get_success_time("/new/file.mp4") is None

    def test_after_mark_returns_time(self, sample_db):
        sm = DBManager(sample_db)
        sm.mark_success("/test/file.mp4", 999.0)
        assert sm.get_success_time("/test/file.mp4") == 999.0

    def test_file_in_failures_only_returns_none(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        assert sm.get_success_time("/test/file1.mp4") is None


class TestDBManagerDeleteRecord:
    def test_deletes_existing_record(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        sm.delete_record("/test/file1.mp4")
        assert sm.get_failure_count("/test/file1.mp4") == 0
        assert sm.get_ffmpeg_failure_count("/test/file1.mp4") == 0

    def test_delete_nonexistent_no_error(self, sample_db):
        sm = DBManager(sample_db)
        sm.delete_record("/nonexistent/file.mp4")

    def test_persists_deletion(self, sample_db_with_data):
        sm = DBManager(sample_db_with_data)
        sm.delete_record("/test/file1.mp4")
        sm2 = DBManager(sample_db_with_data)
        assert sm2.get_failure_count("/test/file1.mp4") == 0
